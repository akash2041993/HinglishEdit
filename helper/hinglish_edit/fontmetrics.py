"""Measure caption text with the bundled fonts (data from fonts/metrics.json).

libass sizes a font so that (winAscent + winDescent) equals the ASS font size, so we work in
"em pixels" and convert. Widths are a sum of character advances: close enough for centering,
fitting lines to the frame and drawing underlines (Hindi conjuncts can differ by a few %)."""
import json
import os

from .config import fonts_dir

_DATA = None

# Fonts without Devanagari: Hindi words in these fall back to a matching Hindi font.
DEVA_FALLBACK = {
    "Anton": ("Teko SemiBold", 0),
    "Great Vibes": ("Kalam", 1),
    "Playfair Display SemiBold": ("Tiro Devanagari Hindi", 0),
    "Playfair Display Italic": ("Tiro Devanagari Hindi Italic", 0),
}


def _data():
    global _DATA
    if _DATA is None:
        try:
            with open(os.path.join(fonts_dir(), "metrics.json"), "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            raw = {}
        for v in raw.values():
            v["adv"] = {int(k): a for k, a in v["adv"].items()}
        _DATA = raw
    return _DATA


def info(family, bold=0):
    d = _data()
    return d.get(f"{family}|{bold}") or d.get(f"{family}|0") or d.get(f"{family}|1") or {
        "upm": 1000, "win_ascent": 1000, "win_descent": 300, "cap": 700, "xh": 500, "deva": True, "adv": {}}


def has_deva(family, bold=0):
    return info(family, bold).get("deva", True)


def ass_size(family, bold, em_px):
    m = info(family, bold)
    return em_px * (m["win_ascent"] + m["win_descent"]) / m["upm"]


def descent_px(family, bold, em_px):
    m = info(family, bold)
    return em_px * m["win_descent"] / m["upm"]


def cap_px(family, bold, em_px):
    m = info(family, bold)
    return em_px * m["cap"] / m["upm"]


def width(family, bold, text, em_px, spacing=0.0):
    m = info(family, bold)
    adv = m["adv"]
    default = m["upm"] * 0.55
    total = 0
    for ch in text:
        cp = ord(ch)
        a = adv.get(cp)
        if a is None:
            if 0x900 <= cp < 0x980 and not m.get("deva", True):
                fam2, b2 = DEVA_FALLBACK.get(family, ("Hind SemiBold", 0))
                m2 = info(fam2, b2)
                a = m2["adv"].get(cp, m2["upm"] * 0.5) * m["upm"] / m2["upm"]
            else:
                a = 0 if 0x900 <= cp < 0x980 else default
        total += a
    return total * em_px / m["upm"] + spacing * max(0, len(text) - 1)
