from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import webrtcvad

from .audio import AudioChunk
from .wpm import SpeechInterval


@dataclass(frozen=True)
class VadFrame:
    chunk: AudioChunk
    speech: bool


def float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


class WebRtcVadSegmenter:
    """Groups 30 ms chunks into utterance segments.

    WebRTC VAD is intentionally used before Whisper so the model only receives
    speech-rich segments. That lowers CPU use and defines the speech intervals
    used by effective-WPM calculation.
    """

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30, aggressiveness: int = 2, silence_ms: int = 600, min_speech_ms: int = 240):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.vad = webrtcvad.Vad(aggressiveness)
        self.silence_frames_to_close = max(1, silence_ms // frame_ms)
        self.min_speech_frames = max(1, min_speech_ms // frame_ms)
        self._buffer: list[AudioChunk] = []
        self._speech_frames = 0
        self._trailing_silence = 0

    def accept(self, chunk: AudioChunk) -> tuple[bool, np.ndarray | None, SpeechInterval | None]:
        frame_len = int(chunk.sample_rate * self.frame_ms / 1000)
        samples = chunk.samples[:frame_len]
        if samples.size < frame_len:
            samples = np.pad(samples, (0, frame_len - samples.size))
        speech = self.vad.is_speech(float_to_pcm16(samples), chunk.sample_rate)
        if speech or self._buffer:
            self._buffer.append(chunk)
        if speech:
            self._speech_frames += 1
            self._trailing_silence = 0
        elif self._buffer:
            self._trailing_silence += 1

        if self._buffer and self._trailing_silence >= self.silence_frames_to_close:
            segment_chunks = self._buffer
            speech_frames = self._speech_frames
            self._buffer = []
            self._speech_frames = 0
            self._trailing_silence = 0
            if speech_frames < self.min_speech_frames:
                return speech, None, None
            audio = np.concatenate([c.samples for c in segment_chunks])
            start = segment_chunks[0].timestamp
            end = segment_chunks[-1].timestamp + len(segment_chunks[-1].samples) / segment_chunks[-1].sample_rate
            return speech, audio, SpeechInterval(start, end)
        return speech, None, None


def speech_seconds(intervals: Iterable[SpeechInterval]) -> float:
    return sum(max(0.0, i.end - i.start) for i in intervals)
