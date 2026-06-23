from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .wpm import WordEvent
from .words import normalize_word


@dataclass(frozen=True)
class WhisperConfig:
    model_size: str = "base"
    compute_type: str = "int8"
    language: str = "en"


def choose_device() -> str:
    try:
        import ctranslate2

        cuda_count = ctranslate2.get_cuda_device_count()
        return "cuda" if cuda_count else "cpu"
    except Exception:
        return "cpu"


class FasterWhisperRecognizer:
    """Thin faster-whisper wrapper returning absolute WordEvent objects."""

    def __init__(self, config: WhisperConfig = WhisperConfig(), progress: bool = True):
        if importlib.util.find_spec("faster_whisper") is None:
            raise RuntimeError("faster-whisper is not installed. Run: pip install -e .")
        from faster_whisper import WhisperModel

        self.config = config
        self.device = choose_device()
        if progress:
            print(f"Loading Whisper model '{config.model_size}' on {self.device} ({config.compute_type}); first run downloads it...", file=sys.stderr)
        self.model = WhisperModel(config.model_size, device=self.device, compute_type=config.compute_type)

    def transcribe_words(self, audio: np.ndarray, sample_rate: int, absolute_start: float) -> list[WordEvent]:
        segments, _info = self.model.transcribe(
            audio.astype(np.float32),
            language=self.config.language,
            vad_filter=False,
            word_timestamps=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        words: list[WordEvent] = []
        for segment in segments:
            for word in segment.words or []:
                text = normalize_word(word.word)
                if text:
                    words.append(WordEvent(text, absolute_start + float(word.start), absolute_start + float(word.end), final=True))
        return words


class MockRecognizer:
    """Deterministic recognizer for pipeline/UI tests without downloading Whisper."""

    def __init__(self, words: Iterable[str] | None = None):
        self.words = list(words or "this is a synthetic english practice sentence".split())
        self._cursor = 0

    def transcribe_words(self, audio: np.ndarray, sample_rate: int, absolute_start: float) -> list[WordEvent]:
        duration = max(0.3, len(audio) / sample_rate)
        count = min(len(self.words), max(1, int(duration * 2.6)))
        result = []
        for i in range(count):
            word = self.words[(self._cursor + i) % len(self.words)]
            start = absolute_start + i * duration / max(1, count)
            result.append(WordEvent(word, start, min(start + 0.25, absolute_start + duration), final=True))
        self._cursor += count
        return result
