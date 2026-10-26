"""Turn word timings into readable captions, in the script the user wants, and write SRT."""
import re

from . import translit
from .cuts import remap_time
from .fillers import FillerMatcher
from .textnorm import ends_clause, ends_sentence

DEFAULTS = {
    "script": "roman",          # original | devanagari | roman
    "max_words": 7,
    "max_chars": 32,            # per line
    "lines": 2,
    "min_dur": 0.7,
    "max_dur": 5.0,
    "pause_split": 0.45,        # a pause this long starts a new caption
    "linger": 0.25,             # keep a caption on screen a bit after the last word
    "offset": 0.0,              # move every caption earlier (-) or later (+), seconds
    "uppercase": False,
    "drop_fillers": True,       # don't show "umm/uh" in captions
    "punctuation": True,        # keep commas/full stops
}

_LATIN = re.compile(r"[A-Za-z]")
_TRAIL_PUNCT = re.compile(r"[\.,!?;:।॥…]+$")


def _convert_words(texts, script, sarvam_key=None, cache=None):
    if script == "roman":
        return translit.words_to_roman(texts, sarvam_key=sarvam_key, cache=cache)
    return list(texts)


def _clean(text, keep_punct):
    t = text.strip()
    if not keep_punct:
        t = _TRAIL_PUNCT.sub("", t)
        t = t.strip("\"'“”‘’")
    return t


def timeline_words(words, cuts=None):
    """Words on the timeline the captions are for. With cuts (edited sequence), words inside a
    cut are dropped and the rest are moved earlier."""
    out = []
    for w in words:
        if w.get("kind", "word") != "word":
            continue
        if not cuts:
            out.append(dict(w))
            continue
        s = remap_time(w["start"], cuts)
        e = remap_time(w["end"], cuts)
        if s is None or e is None:
            # word touches a cut: keep only if most of it survives
            mid = remap_time((w["start"] + w["end"]) / 2, cuts)
            if mid is None:
                continue
            s = mid - 0.05 if s is None else s
            e = mid + 0.05 if e is None else e
        out.append(dict(w, start=s, end=max(e, s + 0.04)))
    return out


def _split_lines(tokens, max_chars, lines):
    """Split a caption's words into up to `lines` lines, as balanced as possible."""
    text = " ".join(tokens)
    if lines <= 1 or len(text) <= max_chars:
        return [text]
    best, best_score = [text], None
    for k in range(1, len(tokens)):
        a, b = " ".join(tokens[:k]), " ".join(tokens[k:])
        over = max(0, len(a) - max_chars) + max(0, len(b) - max_chars)
        score = over * 100 + abs(len(a) - len(b))
        if best_score is None or score < best_score:
            best, best_score = [a, b], score
    return best


def build(words, opts=None, cuts=None, sarvam_key=None, cache=None):
    o = dict(DEFAULTS)
    o.update({k: v for k, v in (opts or {}).items() if v is not None})
    matcher = FillerMatcher()
    ws = timeline_words(words, cuts)
    if o["drop_fillers"]:
        ws = [w for w in ws if not matcher.is_sound(w["text"])]
    if not ws:
        return []
    english = o["script"] == "english"
    shown = _convert_words([w["text"] for w in ws], "original" if english else o["script"], sarvam_key, cache)
    for w, t in zip(ws, shown):
        t = _clean(t, o["punctuation"])
        if o["uppercase"] and not english:
            t = t.upper() if _LATIN.search(t) else t
        w["show"] = t

    caps, cur = [], []

    def flush():
        if cur:
            caps.append(list(cur))
            cur.clear()

    for i, w in enumerate(ws):
        if not w["show"]:
            continue
        if cur:
            prev = cur[-1]
            text_len = len(" ".join(x["show"] for x in cur + [w]))
            too_long = text_len > o["max_chars"] * o["lines"]
            too_many = len(cur) >= o["max_words"]
            pause = w["start"] - prev["end"] >= o["pause_split"]
            too_slow = w["end"] - cur[0]["start"] > o["max_dur"]
            sentence = o["punctuation"] is not None and ends_sentence(ws[i - 1]["text"])
            clause = ends_clause(ws[i - 1]["text"]) and len(cur) >= max(2, o["max_words"] // 2)
            if too_long or too_many or pause or too_slow or sentence or clause:
                flush()
        cur.append(w)
    flush()

    out = []
    for n, group in enumerate(caps):
        start = group[0]["start"] + o["offset"]
        end = group[-1]["end"] + o["linger"] + o["offset"]
        out.append({
            "i": n,
            "start": max(0.0, start),
            "end": end,
            "text": " ".join(w["show"] for w in group),
            "lines": _split_lines([w["show"] for w in group], o["max_chars"], o["lines"]),
            "words": [{"text": w["show"], "start": max(0.0, w["start"] + o["offset"]),
                       "end": w["end"] + o["offset"]} for w in group],
        })
    # minimum duration and no overlaps
    for k, c in enumerate(out):
        nxt = out[k + 1]["start"] if k + 1 < len(out) else None
        if c["end"] - c["start"] < o["min_dur"]:
            c["end"] = c["start"] + o["min_dur"]
        if nxt is not None and c["end"] > nxt - 0.02:
            c["end"] = max(c["start"] + 0.2, nxt - 0.02)
        c["start"], c["end"] = round(c["start"], 3), round(c["end"], 3)
    if english and out:
        from .translate import translate_lines
        texts = translate_lines([c["text"] for c in out], sarvam_key=sarvam_key, cache=cache)
        for c, en in zip(out, texts):
            en = _clean(en, o["punctuation"])
            if o["uppercase"]:
                en = en.upper()
            c["original"] = c["text"]
            c["text"] = en
            c["words"] = []  # re-timed below: translated words follow the speech evenly
            c["max_chars"], c["line_count"] = o["max_chars"], o["lines"]
            c.pop("lines", None)
        apply_edits(out)
    return out


def apply_edits(captions):
    """The panel may send edited text. When the words changed, spread word times again."""
    for c in captions:
        toks = c.get("text", "").split()
        words = c.get("words") or []
        if [w.get("text") for w in words] != toks:
            if not toks:
                c["words"] = []
                continue
            total = sum(len(t) for t in toks) or 1
            t0, t1 = c["start"], max(c["start"] + 0.1, c["end"] - 0.15)
            pos = t0
            new = []
            for t in toks:
                d = (t1 - t0) * len(t) / total
                new.append({"text": t, "start": pos, "end": pos + d})
                pos += d
            c["words"] = new
        if "lines" not in c or " ".join(c["lines"]).split() != toks:
            c["lines"] = _split_lines(toks, int(c.get("max_chars", 32)), int(c.get("line_count", 2)))
    return captions


def _ts(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(captions):
    out = []
    for n, c in enumerate(captions, 1):
        out.append(str(n))
        out.append(f"{_ts(c['start'])} --> {_ts(c['end'])}")
        out.extend(ln.replace("*", "") for ln in (c.get("lines") or [c["text"]]))
        out.append("")
    return "\n".join(out)
