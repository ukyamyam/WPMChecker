from __future__ import annotations

import asyncio
import math
import platform
import queue
import threading
import time
from dataclasses import dataclass
from typing import AsyncIterator, Iterator, Literal, Protocol

import numpy as np


AudioSourceKind = Literal["mic", "system"]


@dataclass(frozen=True)
class AudioChunk:
    samples: np.ndarray  # mono float32 in [-1, 1]
    sample_rate: int
    timestamp: float
    source: AudioSourceKind
    device_name: str

    @property
    def level(self) -> float:
        if self.samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(self.samples))))
        return min(1.0, rms * 8.0)


class AudioCapture(Protocol):
    source: AudioSourceKind

    async def chunks(self) -> AsyncIterator[AudioChunk]:
        ...


class SyntheticAudioCapture:
    """Cross-platform fallback/test source.

    It emits a low-level sine wave so the WebSocket/UI pipeline can be tested on
    non-Windows CI machines where WASAPI loopback is unavailable.
    """

    def __init__(self, source: AudioSourceKind = "system", sample_rate: int = 16000, chunk_ms: int = 30):
        self.source = source
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.device_name = "synthetic"
        self._phase = 0.0

    async def chunks(self) -> AsyncIterator[AudioChunk]:
        chunk_len = int(self.sample_rate * self.chunk_ms / 1000)
        while True:
            t = (np.arange(chunk_len) + self._phase) / self.sample_rate
            samples = (0.04 * np.sin(2 * math.pi * 440 * t)).astype(np.float32)
            self._phase += chunk_len
            yield AudioChunk(samples, self.sample_rate, time.monotonic(), self.source, self.device_name)
            await asyncio.sleep(self.chunk_ms / 1000)


class SoundCardCapture:
    """WASAPI capture using soundcard.

    For system audio, the recorder is opened on the current OS default speaker
    with loopback=True. The default device is re-resolved periodically so AirPods
    or other Bluetooth output changes are followed instead of recording silence
    from a stale endpoint.
    """

    def __init__(self, source: AudioSourceKind, sample_rate: int = 16000, chunk_ms: int = 30, refresh_seconds: float = 2.0):
        self.source = source
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.refresh_seconds = refresh_seconds
        self._stop = threading.Event()

    def _open_recorder(self):
        import soundcard as sc

        if self.source == "system":
            device = sc.default_speaker()
            return device.name, device.recorder(samplerate=self.sample_rate, channels=1, blocksize=int(self.sample_rate * self.chunk_ms / 1000), loopback=True)
        mic = sc.default_microphone()
        return mic.name, mic.recorder(samplerate=self.sample_rate, channels=1, blocksize=int(self.sample_rate * self.chunk_ms / 1000))

    def _worker(self, out: "queue.Queue[AudioChunk | Exception]") -> None:
        block = int(self.sample_rate * self.chunk_ms / 1000)
        while not self._stop.is_set():
            try:
                device_name, recorder = self._open_recorder()
                opened = time.monotonic()
                with recorder as rec:
                    while not self._stop.is_set():
                        data = rec.record(numframes=block)
                        mono = np.asarray(data, dtype=np.float32).reshape(-1)
                        out.put(AudioChunk(mono, self.sample_rate, time.monotonic(), self.source, device_name))
                        if time.monotonic() - opened > self.refresh_seconds:
                            break
            except Exception as exc:  # device removed / package backend issue
                out.put(exc)
                time.sleep(0.5)

    async def chunks(self) -> AsyncIterator[AudioChunk]:
        out: "queue.Queue[AudioChunk | Exception]" = queue.Queue(maxsize=32)
        thread = threading.Thread(target=self._worker, args=(out,), daemon=True)
        thread.start()
        try:
            while True:
                item = await asyncio.to_thread(out.get)
                if isinstance(item, Exception):
                    await asyncio.sleep(0.1)
                    continue
                yield item
        finally:
            self._stop.set()


class PyAudioWPatchCapture:
    """WASAPI capture using pyaudiowpatch fallback.

    pyaudiowpatch exposes Windows loopback devices explicitly. We select the
    current default WASAPI speaker and open its loopback endpoint; each reconnect
    re-queries defaults to follow device changes.
    """

    def __init__(self, source: AudioSourceKind, sample_rate: int = 16000, chunk_ms: int = 30, refresh_seconds: float = 2.0):
        self.source = source
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.refresh_seconds = refresh_seconds
        self._stop = threading.Event()

    def _worker(self, out: "queue.Queue[AudioChunk | Exception]") -> None:
        import pyaudiowpatch as pyaudio

        pa = pyaudio.PyAudio()
        frames = int(self.sample_rate * self.chunk_ms / 1000)
        try:
            while not self._stop.is_set():
                try:
                    if self.source == "system":
                        info = pa.get_default_wasapi_loopback()
                    else:
                        info = pa.get_default_input_device_info()
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=self.sample_rate,
                        input=True,
                        frames_per_buffer=frames,
                        input_device_index=info["index"],
                    )
                    opened = time.monotonic()
                    with stream:
                        while not self._stop.is_set():
                            raw = stream.read(frames, exception_on_overflow=False)
                            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                            out.put(AudioChunk(samples, self.sample_rate, time.monotonic(), self.source, info.get("name", "WASAPI")))
                            if time.monotonic() - opened > self.refresh_seconds:
                                break
                except Exception as exc:
                    out.put(exc)
                    time.sleep(0.5)
        finally:
            pa.terminate()

    async def chunks(self) -> AsyncIterator[AudioChunk]:
        out: "queue.Queue[AudioChunk | Exception]" = queue.Queue(maxsize=32)
        threading.Thread(target=self._worker, args=(out,), daemon=True).start()
        while True:
            item = await asyncio.to_thread(out.get)
            if isinstance(item, Exception):
                await asyncio.sleep(0.1)
                continue
            yield item


def make_capture(source: AudioSourceKind = "system", backend: str = "auto") -> AudioCapture:
    if backend == "synthetic" or platform.system() != "Windows":
        return SyntheticAudioCapture(source=source)
    if backend in ("auto", "soundcard"):
        try:
            import soundcard  # noqa: F401

            return SoundCardCapture(source=source)
        except Exception:
            if backend == "soundcard":
                raise
    if backend in ("auto", "pyaudiowpatch"):
        try:
            import pyaudiowpatch  # noqa: F401

            return PyAudioWPatchCapture(source=source)
        except Exception:
            if backend == "pyaudiowpatch":
                raise
    return SyntheticAudioCapture(source=source)
