"""Find cuts: long pauses, silences, filler words and repeated words.

All times are in seconds on the sequence timeline. A cut is a range to REMOVE.

Safety rules that keep speech natural:
  * a cut never overlaps a word we keep (checked again at the end);
  * a short natural pause is always left between words (keep_pause);
  * cut edges are moved to the quietest point nearby, so no clicks or chopped word tails;
  * loud sound inside a "silence" (speech the transcript missed, laughter) is never cut.
"""
from .fillers import FillerMatcher
from .textnorm import squash

HOP = 0.01  # envelope frame length in seconds (10 ms)

PRESETS = {
    # intensity:  gentle (0)   normal (50)   aggressive (100)
    "min_pause": (1.20, 0.70, 0.40),
    "keep_pause": (0.45, 0.30, 0.18),
    "pad_before": (0.14, 0.10, 0.06),
    "pad_after": (0.22, 0.16, 0.10),
}


def _lerp3(vals, x):
    g, n, a = vals
    if x <= 50:
        return g + (n - g) * (x / 50.0)
    return n + (a - n) * ((x - 50) / 50.0)


def params_for(intensity=50, overrides=None):
    x = max(0.0, min(100.0, float(intensity)))
    p = {k: round(_lerp3(v, x), 3) for k, v in PRESETS.items()}
    p.update({
        "intensity": x,
        "cut_silence": True,
        "cut_sounds": True,                 # umm, uh, hmm
        "cut_ambiguous": x >= 35,           # aa, haan, ok (only when isolated by pauses)
        "cut_phrases": x >= 85,             # basically, matlab, you know (isolated)
        "cut_repeats": x >= 35,             # "main main", "I think I think"
        "cut_lead_tail": True,              # silence before the first and after the last word
        "isolation": 0.22,                  # pause needed around ambiguous fillers / phrases
        "edge_search": 0.04,
        "min_cut": 0.15,
        "protect_loud": True,
    })
    if overrides:
        for k, v in overrides.items():
            if v is not None and k in p:
                p[k] = v
    return p


# ------------------------------------------------------------------ envelope helpers
class Envelope:
    def __init__(self, db_values, hop=HOP):
        self.db = list(db_values or [])
        self.hop = hop
        vals = sorted(v for v in self.db if v > -120)
        self.noise_floor = vals[int(len(vals) * 0.15)] if vals else -60.0

    def __bool__(self):
        return bool(self.db)

    def idx(self, t):
        return max(0, min(len(self.db) - 1, int(round(t / self.hop))))

    def level(self, t):
        return self.db[self.idx(t)] if self.db else -120.0

    def quietest(self, t, lo, hi, search):
        """Time of the quietest frame within +-search of t, kept inside [lo, hi]."""
        if not self.db:
            return min(max(t, lo), hi)
        a = max(lo, t - search)
        b = min(hi, t + search)
        if b <= a:
            return min(max(t, lo), hi)
        i0, i1 = self.idx(a), self.idx(b)
        best_i, best_v = self.idx(t), None
        for i in range(i0, i1 + 1):
            v = self.db[i]
            # prefer the frame closest to t when levels are equal (within 1 dB)
            if best_v is None or v < best_v - 1.0 or (abs(v - best_v) <= 1.0 and abs(i * self.hop - t) < abs(best_i * self.hop - t)):
                best_i, best_v = i, v
        return min(max(best_i * self.hop, a), b)

    def loud_runs(self, start, end, threshold, min_len=0.2):
        """Ranges inside [start, end] where the level stays above threshold (speech the transcript missed)."""
        if not self.db or end <= start:
            return []
        runs, run_start = [], None
        i0, i1 = self.idx(start), self.idx(end)
        for i in range(i0, i1 + 1):
            loud = self.db[i] > threshold
            if loud and run_start is None:
                run_start = i
            elif not loud and run_start is not None:
                if (i - run_start) * self.hop >= min_len:
                    runs.append((run_start * self.hop, i * self.hop))
                run_start = None
        if run_start is not None and (i1 + 1 - run_start) * self.hop >= min_len:
            runs.append((run_start * self.hop, (i1 + 1) * self.hop))
        return runs


def _speech_level(env, words):
    vals = []
    for w in words:
        for i in range(env.idx(w["start"]), env.idx(w["end"]) + 1):
            if env.db[i] > -120:
                vals.append(env.db[i])
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


# ------------------------------------------------------------------ main
def _context(words, i0, i1, before=4, after=4):
    left = " ".join(w["text"] for w in words[max(0, i0 - before):i0])
    mid = " ".join(w["text"] for w in words[i0:i1])
    right = " ".join(w["text"] for w in words[i1:i1 + after])
    return left, mid, right


def plan_cuts(words, duration, envelope=None, params=None, matcher=None):
    p = params or params_for(50)
    env = envelope if isinstance(envelope, Envelope) else Envelope(envelope or [])
    matcher = matcher or FillerMatcher()
    duration = float(duration)

    ws = [dict(w) for w in words if w.get("start") is not None and w.get("end") is not None]
    for w in ws:
        w["start"] = max(0.0, min(float(w["start"]), duration))
        w["end"] = max(w["start"], min(float(w["end"]), duration))
    ws.sort(key=lambda w: (w["start"], w["end"]))
    speech = [w for w in ws if w.get("kind", "word") in ("word", "event")]
    talk = [w for w in speech if w.get("kind", "word") == "word"]
    toks = [squash(w["text"]) for w in talk]

    removed_word = [False] * len(talk)  # words removed on purpose (fillers, repeats)
    cuts = []

    def add(start, end, kind, label, i0=None, i1=None):
        if end - start <= 0:
            return
        c = {"start": start, "end": end, "kinds": [kind], "label": label}
        if i0 is not None:
            left, mid, right = _context(talk, i0, i1)
            c.update({"before": left, "text": mid, "after": right})
        cuts.append(c)

    def gap_before(i):
        return talk[i]["start"] - (talk[i - 1]["end"] if i > 0 else 0.0)

    def gap_after(i):
        return (talk[i + 1]["start"] if i + 1 < len(talk) else duration) - talk[i]["end"]

    def remove_span(i0, i1, kind, label):
        """Remove words i0..i1-1, leaving a natural pause between the neighbours."""
        prev_end = talk[i0 - 1]["end"] if i0 > 0 else max(0.0, talk[i0]["start"] - 1.0)
        next_start = talk[i1]["start"] if i1 < len(talk) else min(duration, talk[i1 - 1]["end"] + 1.0)
        a = max(p["pad_after"], p["keep_pause"] / 2)
        b = max(p["pad_before"], p["keep_pause"] / 2)
        s = prev_end + a
        e = next_start - b
        ws0, we0 = talk[i0]["start"], talk[i1 - 1]["end"]
        if s > ws0 - 0.01:
            s = max(prev_end + 0.02, ws0 - 0.01)
        if e < we0 + 0.01:
            e = min(next_start - 0.02, we0 + 0.01)
        if e - s < (we0 - ws0) * 0.8:
            return False  # no room to remove it cleanly
        for k in range(i0, i1):
            removed_word[k] = True
        add(s, e, kind, label, i0, i1)
        return True

    # 1) filler words and phrases
    iso = p["isolation"]
    i = 0
    while i < len(talk):
        n = matcher.match_phrase(toks, i) if p["cut_phrases"] else 0
        if n:
            j = i + n
            if gap_before(i) >= iso and ((talk[j]["start"] if j < len(talk) else duration) - talk[j - 1]["end"]) >= iso:
                if remove_span(i, j, "filler", "Filler phrase"):
                    i = j
                    continue
        w = talk[i]["text"]
        if p["cut_sounds"] and matcher.is_sound(w):
            remove_span(i, i + 1, "filler", "Filler sound")
        elif p["cut_ambiguous"] and matcher.is_ambiguous(w) and gap_before(i) >= iso and gap_after(i) >= iso:
            remove_span(i, i + 1, "filler", "Filler")
        i += 1

    # 2) repeated words / restarts: cut the first copy ("main main" -> "main")
    if p["cut_repeats"]:
        i = 0
        while i < len(talk):
            done = False
            for n in (3, 2, 1):
                a, b = toks[i:i + n], toks[i + n:i + 2 * n]
                if len(a) < n or len(b) < n or a != b or not all(a):
                    continue
                if any(removed_word[k] for k in range(i, i + 2 * n)):
                    continue
                pause = talk[i + n]["start"] - talk[i + n - 1]["end"]
                triple = n == 1 and toks[i + 2:i + 3] == a
                # Hindi doubles words on purpose ("dheere dheere", "bahut bahut"), said without a pause.
                if n == 1 and pause < 0.2 and not triple:
                    continue
                s = talk[i]["start"] - 0.02
                e = talk[i + n]["start"] - 0.02
                if i > 0:
                    s = max(s, talk[i - 1]["end"] + 0.02)
                for k in range(i, i + n):
                    removed_word[k] = True
                add(s, e, "repeat", "Repeated words", i, i + n)
                i += n
                done = True
                break
            if not done:
                i += 1

    # 3) silences and long pauses
    keep = [w for k, w in enumerate(talk) if not removed_word[k]] + [w for w in speech if w.get("kind") == "event"]
    keep.sort(key=lambda w: w["start"])
    speech_db = _speech_level(env, keep) if env else None
    loud_thr = None
    if env and p["protect_loud"] and speech_db is not None:
        loud_thr = max(env.noise_floor + 10.0, speech_db - 14.0)

    if p["cut_silence"]:
        bounds = [(0.0, 0.0)] + [(w["start"], w["end"]) for w in keep] + [(duration, duration)]
        for k in range(len(bounds) - 1):
            g0 = bounds[k][1]
            g1 = bounds[k + 1][0]
            first, last = k == 0, k == len(bounds) - 2
            if g1 - g0 < p["min_pause"] and not ((first or last) and p["cut_lead_tail"] and g1 - g0 > p["min_cut"] + 0.3):
                continue
            if first:
                s, e = 0.0, g1 - p["pad_before"]
            elif last:
                s, e = g0 + p["pad_after"], duration
            else:
                s = g0 + max(p["pad_after"], p["keep_pause"] / 2)
                e = g1 - max(p["pad_before"], p["keep_pause"] / 2)
            if e - s < p["min_cut"]:
                continue
            pieces = [(s, e)]
            if loud_thr is not None:
                for r0, r1 in env.loud_runs(s, e, loud_thr):
                    nxt = []
                    for a, b in pieces:
                        if r1 <= a or r0 >= b:
                            nxt.append((a, b))
                            continue
                        if r0 - p["pad_before"] > a:
                            nxt.append((a, r0 - p["pad_before"]))
                        if r1 + p["pad_after"] < b:
                            nxt.append((r1 + p["pad_after"], b))
                    pieces = nxt
            label = "Silence" if (first or last) else ("Long pause" if g1 - g0 >= 1.5 else "Pause")
            for a, b in pieces:
                if b - a >= p["min_cut"]:
                    add(a, b, "silence", label)

    # 4) quiet edges, merge, and final safety check against kept words
    lo_hi = [(w["start"], w["end"]) for w in keep]
    cuts.sort(key=lambda c: c["start"])
    merged = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"] + 0.06:
            m = merged[-1]
            m["end"] = max(m["end"], c["end"])
            for kd in c["kinds"]:
                if kd not in m["kinds"]:
                    m["kinds"].append(kd)
            if c.get("text"):
                m["text"] = (m.get("text", "") + " " + c["text"]).strip()
                m.setdefault("before", c.get("before", ""))
                m["after"] = c.get("after", m.get("after", ""))
            if c["label"] != m["label"]:
                m["label"] = "Filler + pause" if "filler" in m["kinds"] else m["label"]
        else:
            merged.append(dict(c, kinds=list(c["kinds"])))

    final = []
    for c in merged:
        s, e = c["start"], c["end"]
        # never touch a kept word
        for ws_, we_ in lo_hi:
            if we_ <= s or ws_ >= e:
                continue
            if ws_ <= s < we_:
                s = we_ + 0.02
            if ws_ < e <= we_:
                e = ws_ - 0.02
            if s < ws_ and e > we_:
                # a kept word inside the cut: split around it
                if ws_ - 0.02 - s >= p["min_cut"]:
                    final.append(dict(c, start=s, end=ws_ - 0.02))
                s = we_ + 0.02
        if e - s < p["min_cut"]:
            continue
        # move edges to the quietest nearby point, staying clear of kept words
        prev_end = max([we_ for ws_, we_ in lo_hi if we_ <= s] or [0.0])
        next_start = min([ws_ for ws_, we_ in lo_hi if ws_ >= e] or [duration])
        if s > 0:
            s = env.quietest(s, prev_end + 0.03, e - p["min_cut"], p["edge_search"])
        if e < duration:
            e = env.quietest(e, s + p["min_cut"], next_start - 0.03, p["edge_search"])
        final.append(dict(c, start=round(s, 3), end=round(e, 3)))

    final = [c for c in final if c["end"] - c["start"] >= p["min_cut"]]
    final.sort(key=lambda c: c["start"])
    for n, c in enumerate(final):
        c["id"] = "c%04d_%d" % (n, int(c["start"] * 1000))
        c["key"] = "%s@%d" % ("+".join(sorted(c["kinds"])), int(round(c["start"] * 10)))
        c["duration"] = round(c["end"] - c["start"], 3)
    return final


def keep_ranges(cuts, duration):
    """Turn a list of cuts into the list of ranges we keep."""
    out, t = [], 0.0
    for c in sorted(cuts, key=lambda c: c["start"]):
        if c["start"] > t:
            out.append((t, c["start"]))
        t = max(t, c["end"])
    if t < duration:
        out.append((t, duration))
    return out


def summarize(cuts, duration):
    removed = sum(c["end"] - c["start"] for c in cuts)
    by = {}
    for c in cuts:
        for k in c["kinds"]:
            by[k] = by.get(k, 0) + 1
    return {
        "count": len(cuts),
        "removed": round(removed, 2),
        "original": round(duration, 2),
        "new_duration": round(duration - removed, 2),
        "by_kind": by,
    }


def remap_time(t, cuts):
    """Where time t (original timeline) lands after the cuts. None if t is inside a cut."""
    shift = 0.0
    for c in sorted(cuts, key=lambda c: c["start"]):
        if t >= c["end"]:
            shift += c["end"] - c["start"]
        elif t > c["start"]:
            return None
        else:
            break
    return t - shift
