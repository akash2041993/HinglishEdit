"""Small text helpers shared by cuts and captions."""
import re
import unicodedata

_PUNCT = re.compile(r"[\s\.,!?;:\"'“”‘’()\[\]{}…\-–—।॥|/\\*_~`]+")
_ELONG = re.compile(r"(.)\1{2,}")


def norm(word):
    """Lowercase, strip punctuation and zero-width marks: used to compare words."""
    w = unicodedata.normalize("NFC", word or "")
    w = w.replace("‌", "").replace("‍", "").replace("़", "")
    w = _PUNCT.sub("", w).lower()
    return w


def squash(word):
    """Like norm(), but collapses long letter runs: 'ummmm' -> 'umm', 'हम्म्म' stays."""
    return _ELONG.sub(r"\1\1", norm(word))


def ends_sentence(word):
    w = (word or "").rstrip("\"'”’)")
    return w.endswith((".", "?", "!", "।", "॥"))


def ends_clause(word):
    w = (word or "").rstrip("\"'”’)")
    return w.endswith((",", ";", ":", "—", "–")) or ends_sentence(word)
