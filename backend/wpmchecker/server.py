from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import asdict, dataclass
from typing import Callable, Literal
from urllib.parse import parse_qs, urlsplit

import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

from .audio import AudioCapture, AudioSourceKind, make_capture
from .vad import WebRtcVadSegmenter
from .whispering import FasterWhisperRecognizer, MockRecognizer, WhisperConfig
from .words import WordDeduplicator
from .wpm import Mode, SpeechInterval, WordEvent, WpmCalculator, WpmSnapshot


def is_authorized_path(path: str, auth_token: str | None) -> bool:
    if auth_token is None:
        return True
    tokens = parse_qs(urlsplit(path).query).get("token", [])
    return len(tokens) == 1 and secrets.compare_digest(tokens[0], auth_token)


@dataclass
class RuntimeConfig:
    source: AudioSourceKind = "system"
    backend: str = "auto"
    model: str = "base"
    mode: Mode = "effective"
    window_seconds: float = 5.0
    mock_whisper: bool = False


class WpmEngine:
    """Owns all non-UI logic: capture, VAD, Whisper, de-dupe, WPM."""

    def __init__(self, config: RuntimeConfig, capture_factory: Callable[[AudioSourceKind, str], AudioCapture] = make_capture):
        self.config = config
        self.capture_factory = capture_factory
        self.calculator = WpmCalculator(config.window_seconds, config.mode)
        self.segmenter = WebRtcVadSegmenter()
        self.words: list[WordEvent] = []
        self.speech_intervals: list[SpeechInterval] = []
        self.deduper = WordDeduplicator()
        self.level = 0.0
        self.device_name = ""
        self.recognizer = MockRecognizer() if config.mock_whisper else FasterWhisperRecognizer(WhisperConfig(model_size=config.model))
        self._mock_audio = []

    def set_source(self, source: AudioSourceKind) -> None:
        self.config.source = source

    def set_mode(self, mode: Mode) -> None:
        self.config.mode = mode
        self.calculator.set_mode(mode)

    def set_window_seconds(self, seconds: float) -> None:
        self.config.window_seconds = seconds
        self.calculator.set_window_seconds(seconds)

    async def run(self, broadcast: Callable[[dict], None]) -> None:
        while True:
            source = self.config.source
            capture = self.capture_factory(source, self.config.backend)
            async for chunk in capture.chunks():
                if source != self.config.source:
                    break
                self.level = chunk.level
                self.device_name = chunk.device_name
                speech, audio, interval = self.segmenter.accept(chunk)
                if self.config.mock_whisper:
                    # Development/demo mode: synthesize utterance segments so the
                    # WebSocket and Electron UI can be verified on machines
                    # without speech audio or a downloaded Whisper model.
                    self._mock_audio.append(chunk)
                    buffered = sum(len(c.samples) for c in self._mock_audio) / chunk.sample_rate
                    if buffered >= 1.0:
                        interval = SpeechInterval(self._mock_audio[0].timestamp, self._mock_audio[-1].timestamp + len(chunk.samples) / chunk.sample_rate)
                        audio = np.concatenate([c.samples for c in self._mock_audio])
                        speech = True
                        self._mock_audio = []
                if interval is not None:
                    self.speech_intervals.append(interval)
                if audio is not None and interval is not None:
                    recognized = await asyncio.to_thread(self.recognizer.transcribe_words, audio, chunk.sample_rate, interval.start)
                    self.words.extend(self.deduper.add_unique(self.words, recognized))
                snapshot = self.calculator.compute(time.monotonic(), self.words, self.speech_intervals)
                broadcast(self.payload(snapshot, speech))

    def payload(self, snapshot: WpmSnapshot, speech: bool = False) -> dict:
        return {
            "type": "wpm",
            "display": snapshot.display,
            "wpm": snapshot.wpm,
            "rawWpm": snapshot.raw_wpm,
            "mode": snapshot.mode,
            "windowSeconds": snapshot.window_seconds,
            "source": self.config.source,
            "device": self.device_name,
            "level": self.level,
            "speech": speech,
            "wordCount": snapshot.word_count,
            "speechSeconds": snapshot.speech_seconds,
            "active": snapshot.active,
            "zone": asdict(snapshot.zone),
        }


class WpmWebSocketServer:
    def __init__(self, engine: WpmEngine, host: str = "127.0.0.1", port: int = 8765, auth_token: str | None = None):
        self.engine = engine
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.clients: set[WebSocketServerProtocol] = set()
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=4)

    def broadcast_later(self, payload: dict) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(payload)

    async def handler(self, ws: WebSocketServerProtocol):
        request = getattr(ws, "request", None)
        path = getattr(request, "path", getattr(ws, "path", "/"))
        if not is_authorized_path(path, self.auth_token):
            await ws.close(code=1008, reason="Unauthorized")
            return
        self.clients.add(ws)
        try:
            async for message in ws:
                await self.apply_command(message)
        finally:
            self.clients.discard(ws)

    async def apply_command(self, message: str) -> None:
        data = json.loads(message)
        if data.get("type") == "setSource":
            self.engine.set_source(data["source"])
        elif data.get("type") == "setMode":
            self.engine.set_mode(data["mode"])
        elif data.get("type") == "setWindow":
            self.engine.set_window_seconds(float(data["seconds"]))

    async def fanout(self) -> None:
        while True:
            payload = await self.queue.get()
            if not self.clients:
                continue
            dead = []
            encoded = json.dumps(payload)
            for client in self.clients:
                try:
                    await client.send(encoded)
                except Exception:
                    dead.append(client)
            for client in dead:
                self.clients.discard(client)

    async def run(self) -> None:
        async with websockets.serve(self.handler, self.host, self.port):
            print(f"WPMChecker WebSocket listening on ws://{self.host}:{self.port}")
            await asyncio.gather(self.engine.run(self.broadcast_later), self.fanout())
