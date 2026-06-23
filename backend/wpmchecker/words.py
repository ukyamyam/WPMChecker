from __future__ import annotations

import re
from dataclasses import dataclass


_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?")


@dataclass
class WordDeduplicator:
    """Deduplicates Whisper words from overlapping chunks by timestamp.

    Sliding recognition windows can return the same spoken token more than once.
    We treat a word as duplicate when both normalized text and start timestamp
    are nearly identical to an already finalized word. This keeps WPM counts from
    jumping while preserving genuinely repeated words such as "very very".
    """

    tolerance_seconds: float = 0.35

    def add_unique(self, existing, candidates):
        accepted = []
        for candidate in candidates:
            text = normalize_word(candidate.word)
            if not text:
                continue
            duplicate = False
            for word in [*existing, *accepted]:
                if normalize_word(word.word) == text and abs(word.start - candidate.start) <= self.tolerance_seconds:
                    duplicate = True
                    break
            if not duplicate:
                accepted.append(candidate)
        return accepted


def normalize_word(word: str) -> str:
    match = _WORD_RE.search(word.strip().lower())
    return match.group(0) if match else ""


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))
