from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


Mode = Literal["effective", "elapsed"]


@dataclass(frozen=True)
class WordEvent:
    """A recognized word with absolute timestamps in seconds."""

    word: str
    start: float
    end: float
    final: bool = True


@dataclass(frozen=True)
class SpeechInterval:
    """A VAD speech interval in absolute monotonic seconds."""

    start: float
    end: float


@dataclass(frozen=True)
class SpeedZone:
    name: str
    color: str


@dataclass(frozen=True)
class WpmSnapshot:
    wpm: int | None
    raw_wpm: int | None
    display: str
    mode: Mode
    window_seconds: float
    word_count: int
    speech_seconds: float
    active: bool
    zone: SpeedZone


def zone_for_wpm(wpm: int | None) -> SpeedZone:
    if wpm is None:
        return SpeedZone("idle", "#64748b")
    if wpm < 120:
        return SpeedZone("slow", "#38bdf8")
    if wpm < 180:
        return SpeedZone("natural", "#22c55e")
    if wpm < 240:
        return SpeedZone("fast", "#facc15")
    return SpeedZone("very fast", "#ef4444")


def _overlap_seconds(interval: SpeechInterval, start: float, end: float) -> float:
    left = max(interval.start, start)
    right = min(interval.end, end)
    return max(0.0, right - left)


class WpmCalculator:
    """Sliding-window WPM calculator.

    The default "effective" mode divides word count by VAD-confirmed speech
    seconds instead of wall-clock seconds. This matches language-learning usage:
    a long pause should make the display go idle, not imply that the speaker's
    articulated speech suddenly became extremely slow.
    """

    def __init__(self, window_seconds: float = 5.0, mode: Mode = "effective", ema_alpha: float = 0.3):
        if not 3 <= window_seconds <= 10:
            raise ValueError("window_seconds must be in [3, 10]")
        if mode not in ("effective", "elapsed"):
            raise ValueError("mode must be 'effective' or 'elapsed'")
        if not 0 < ema_alpha <= 1:
            raise ValueError("ema_alpha must be in (0, 1]")
        self.window_seconds = float(window_seconds)
        self.mode: Mode = mode
        self.ema_alpha = float(ema_alpha)
        self._ema: float | None = None

    def set_mode(self, mode: Mode) -> None:
        if mode not in ("effective", "elapsed"):
            raise ValueError("mode must be 'effective' or 'elapsed'")
        self.mode = mode
        self._ema = None

    def set_window_seconds(self, seconds: float) -> None:
        if not 3 <= seconds <= 10:
            raise ValueError("window_seconds must be in [3, 10]")
        self.window_seconds = float(seconds)
        self._ema = None

    def compute(
        self,
        now: float,
        words: Iterable[WordEvent],
        speech_intervals: Iterable[SpeechInterval],
    ) -> WpmSnapshot:
        window_start = now - self.window_seconds
        recent_words = [w for w in words if window_start <= w.start <= now and w.word.strip()]
        speech = [s for s in speech_intervals if s.end >= window_start and s.start <= now]
        speech_seconds = sum(_overlap_seconds(s, window_start, now) for s in speech)
        last_speech_end = max((s.end for s in speech), default=None)
        active = last_speech_end is not None and now - last_speech_end <= 3.0

        if not active:
            return WpmSnapshot(
                wpm=None,
                raw_wpm=None,
                display="--",
                mode=self.mode,
                window_seconds=self.window_seconds,
                word_count=len(recent_words),
                speech_seconds=round(speech_seconds, 3),
                active=False,
                zone=zone_for_wpm(None),
            )

        denominator = speech_seconds if self.mode == "effective" else self.window_seconds
        if denominator <= 0 or not recent_words:
            raw = None
            smoothed = None
            display = "--"
        else:
            raw_float = len(recent_words) / denominator * 60.0
            self._ema = raw_float if self._ema is None else self.ema_alpha * raw_float + (1 - self.ema_alpha) * self._ema
            raw = int(round(raw_float))
            smoothed = int(round(self._ema))
            display = str(smoothed)

        return WpmSnapshot(
            wpm=smoothed,
            raw_wpm=raw,
            display=display,
            mode=self.mode,
            window_seconds=self.window_seconds,
            word_count=len(recent_words),
            speech_seconds=round(speech_seconds, 3),
            active=active,
            zone=zone_for_wpm(smoothed),
        )
