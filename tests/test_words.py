from wpmchecker.words import count_words, normalize_word, WordDeduplicator
from wpmchecker.wpm import WordEvent


def test_count_words_ignores_punctuation_and_counts_real_words():
    assert count_words("Hello, learner! it's a fast-paced clip.") == 6


def test_deduplicator_drops_overlap_by_word_and_timestamp():
    existing = [WordEvent("hello", 1.0, 1.2), WordEvent("world", 1.4, 1.7)]
    candidates = [WordEvent("Hello", 1.1, 1.25), WordEvent("again", 2.0, 2.2)]

    accepted = WordDeduplicator().add_unique(existing, candidates)

    assert accepted == [WordEvent("again", 2.0, 2.2)]


def test_normalize_word_returns_empty_for_non_word_tokens():
    assert normalize_word("...") == ""
