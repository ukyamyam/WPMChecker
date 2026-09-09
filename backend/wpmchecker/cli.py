from __future__ import annotations

import argparse
import asyncio
import json
import time

from .audio import make_capture
from .server import RuntimeConfig, WpmEngine, WpmWebSocketServer
from .vad import WebRtcVadSegmenter
from .whispering import FasterWhisperRecognizer, MockRecognizer, WhisperConfig
from .words import WordDeduplicator
from .wpm import WpmCalculator


async def stage1(args) -> None:
    capture = make_capture(args.source, args.backend)
    print("Stage 1: audio level check. Play audio or speak; Ctrl+C to stop.")
    async for chunk in capture.chunks():
        bars = "█" * int(chunk.level * 30)
        print(f"{chunk.source:6s} {chunk.device_name[:35]:35s} level={chunk.level:0.3f} {bars}")


async def stage2(args) -> None:
    capture = make_capture(args.source, args.backend)
    segmenter = WebRtcVadSegmenter()
    recognizer = MockRecognizer() if args.mock_whisper else FasterWhisperRecognizer(WhisperConfig(model_size=args.model))
    deduper = WordDeduplicator()
    words = []
    print("Stage 2: VAD + Whisper words. Ctrl+C to stop.")
    async for chunk in capture.chunks():
        _speech, audio, interval = segmenter.accept(chunk)
        if audio is not None and interval is not None:
            new_words = recognizer.transcribe_words(audio, chunk.sample_rate, interval.start)
            unique = deduper.add_unique(words, new_words)
            words.extend(unique)
            for word in unique:
                print(f"{word.start:10.2f}-{word.end:10.2f} {word.word}")


async def stage3(args) -> None:
    capture = make_capture(args.source, args.backend)
    segmenter = WebRtcVadSegmenter()
    recognizer = MockRecognizer() if args.mock_whisper else FasterWhisperRecognizer(WhisperConfig(model_size=args.model))
    deduper = WordDeduplicator()
    calculator = WpmCalculator(args.window, args.mode)
    words = []
    intervals = []
    print("Stage 3: console WPM. Ctrl+C to stop.")
    async for chunk in capture.chunks():
        speech, audio, interval = segmenter.accept(chunk)
        if interval is not None:
            intervals.append(interval)
        if audio is not None and interval is not None:
            unique = deduper.add_unique(words, recognizer.transcribe_words(audio, chunk.sample_rate, interval.start))
            words.extend(unique)
        snapshot = calculator.compute(time.monotonic(), words, intervals)
        print(f"WPM={snapshot.display:>3} mode={snapshot.mode} source={chunk.source} level={chunk.level:0.2f} speech={speech}")


async def stage4(args) -> None:
    config = RuntimeConfig(source=args.source, backend=args.backend, model=args.model, mode=args.mode, window_seconds=args.window, mock_whisper=args.mock_whisper)
    engine = WpmEngine(config)
    server = WpmWebSocketServer(engine, args.host, args.port, args.auth_token)
    await server.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpmchecker")
    parser.add_argument("--source", choices=["system", "mic"], default="system")
    parser.add_argument("--backend", choices=["auto", "soundcard", "pyaudiowpatch", "synthetic"], default="auto")
    parser.add_argument("--model", default="base", help="faster-whisper model size (base or small recommended)")
    parser.add_argument("--mode", choices=["effective", "elapsed"], default="effective")
    parser.add_argument("--window", type=float, default=5.0, help="WPM window seconds, 3-10")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--auth-token", help=argparse.SUPPRESS)
    parser.add_argument("--mock-whisper", action="store_true", help="Use deterministic fake words for UI/pipeline testing")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("level", help="Stage 1: capture level meter")
    sub.add_parser("words", help="Stage 2: VAD + Whisper console words")
    sub.add_parser("wpm", help="Stage 3: console WPM")
    sub.add_parser("serve", help="Stage 4/5: WebSocket backend")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {"level": stage1, "words": stage2, "wpm": stage3, "serve": stage4}
    try:
        asyncio.run(dispatch[args.command](args))
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
