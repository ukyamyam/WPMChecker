from wpmchecker.wpm import SpeechInterval, WordEvent, WpmCalculator, zone_for_wpm


def test_effective_wpm_uses_only_speech_seconds_and_ema():
    calc = WpmCalculator(window_seconds=5, mode="effective", ema_alpha=1.0)
    now = 10.0
    words = [WordEvent("hello", 6.1, 6.3), WordEvent("world", 6.5, 6.7), WordEvent("again", 8.0, 8.2)]
    speech = [SpeechInterval(6.0, 7.0), SpeechInterval(8.0, 9.0)]

    snapshot = calc.compute(now, words, speech)

    assert snapshot.raw_wpm == 90
    assert snapshot.wpm == 90
    assert snapshot.word_count == 3
    assert snapshot.speech_seconds == 2.0


def test_elapsed_wpm_uses_window_seconds_including_silence():
    calc = WpmCalculator(window_seconds=5, mode="elapsed", ema_alpha=1.0)
    words = [WordEvent("one", 8.0, 8.1), WordEvent("two", 9.0, 9.1)]
    speech = [SpeechInterval(8.0, 9.5)]

    snapshot = calc.compute(10.0, words, speech)

    assert snapshot.raw_wpm == 24
    assert snapshot.wpm == 24


def test_no_recent_speech_for_three_seconds_fades_to_dash():
    calc = WpmCalculator(window_seconds=5, mode="effective", ema_alpha=1.0)
    words = [WordEvent("old", 4.0, 4.2)]
    speech = [SpeechInterval(4.0, 4.5)]

    snapshot = calc.compute(10.0, words, speech)

    assert snapshot.display == "--"
    assert snapshot.active is False


def test_zone_thresholds_match_product_requirement():
    assert zone_for_wpm(119).name == "slow"
    assert zone_for_wpm(120).name == "natural"
    assert zone_for_wpm(180).name == "fast"
    assert zone_for_wpm(240).name == "very fast"
