"""Filler words for Hindi, English and Hinglish speech.

Three groups:
  SOUNDS     - "umm", "uh", "hmm", "अं". Almost always safe to remove.
  AMBIGUOUS  - "aa", "आ", "haan", "ok": also real words ("आ जाओ" = come), so they are only
               treated as fillers when there is a pause on both sides of them.
  PHRASES    - "basically", "matlab", "you know": meaningful in many sentences, so they are
               only suggested at the Aggressive setting and also need pauses around them.
All lists can be changed by the user in the panel (Settings).
"""
from .textnorm import squash

SOUNDS = [
    "um", "umm", "uh", "uhh", "uhm", "hmm", "hm", "mm", "mmm", "er", "erm", "eh", "ehh", "ah", "ahh",
    "उम", "उम्म", "अं", "अंअ", "उं", "ऊं", "हम्म", "हम्मम", "हं", "ह्म", "म्म", "अम्म", "अह", "एह",
]
AMBIGUOUS = ["aa", "aaa", "a", "o", "oh", "haan", "han", "ok", "okay", "so", "आ", "आआ", "अ", "ओ", "हां", "हाँ", "तो", "ना"]
PHRASES = [
    "basically", "actually", "literally", "like", "you know", "i mean", "right", "so basically",
    "matlab", "yaani", "मतलब", "यानी", "यानि", "बेसिकली", "एक्चुअली", "लाइक", "यू नो", "आई मीन",
    "kind of", "sort of", "you see",
]


def _phrase_tokens(lst):
    out = []
    for p in lst:
        toks = [squash(t) for t in p.split() if squash(t)]
        if toks:
            out.append(toks)
    out.sort(key=len, reverse=True)
    return out


class FillerMatcher:
    def __init__(self, sounds=None, ambiguous=None, phrases=None):
        self.sounds = {squash(w) for w in (sounds if sounds is not None else SOUNDS) if squash(w)}
        self.ambiguous = {squash(w) for w in (ambiguous if ambiguous is not None else AMBIGUOUS) if squash(w)}
        self.phrases = _phrase_tokens(phrases if phrases is not None else PHRASES)

    def is_sound(self, word):
        w = squash(word)
        if not w:
            return False
        if w in self.sounds:
            return True
        # stretched variants: "ummmmm", "hmmmm", "uhhhh"
        base = w.rstrip("m").rstrip("h")
        return base in ("u", "um", "uh", "h", "e", "a") and len(w) >= 2 and w[0] in "uhe" and set(w) <= set("umhe")

    def is_ambiguous(self, word):
        return squash(word) in self.ambiguous

    def match_phrase(self, tokens, i):
        """Length of a filler phrase starting at tokens[i] (list of normalized words), else 0."""
        for p in self.phrases:
            if tokens[i:i + len(p)] == p:
                return len(p)
        return 0
