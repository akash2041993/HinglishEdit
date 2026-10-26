"""Caption designs. Captions are written as an ASS subtitle file and drawn by libass (inside
ffmpeg), which shapes Hindi (Devanagari) correctly and supports per-word animation.

Sizes are "em" sizes in % of the frame's short side, so a design looks the same on 16:9 and 9:16."""
from . import fontmetrics as fm
from .ass_style_util import ass_color, ass_time, esc, inline_color

FONTS = {
    # name shown in the panel: (font family inside the file, bold flag)
    "Poppins ExtraBold": ("Poppins ExtraBold", 0),
    "Poppins Black": ("Poppins Black", 0),
    "Poppins Bold": ("Poppins", 1),
    "Poppins SemiBold": ("Poppins SemiBold", 0),
    "Poppins Medium": ("Poppins Medium", 0),
    "Poppins Regular": ("Poppins", 0),
    "Poppins Light": ("Poppins Light", 0),
    "Poppins Black Italic": ("Poppins Black Italic", 0),
    "Poppins ExtraBold Italic": ("Poppins ExtraBold Italic", 0),
    "Anton (condensed)": ("Anton", 0),
    "Teko SemiBold (condensed)": ("Teko SemiBold", 0),
    "Playfair Display SemiBold": ("Playfair Display SemiBold", 0),
    "Playfair Display Italic": ("Playfair Display Italic", 0),
    "Tiro Devanagari Hindi": ("Tiro Devanagari Hindi", 0),
    "Tiro Devanagari Hindi Italic": ("Tiro Devanagari Hindi Italic", 0),
    "Great Vibes (script)": ("Great Vibes", 0),
    "Baloo 2 ExtraBold": ("Baloo 2 ExtraBold", 0),
    "Mukta ExtraBold": ("Mukta ExtraBold", 0),
    "Mukta Bold": ("Mukta", 1),
    "Mukta Medium": ("Mukta Medium", 0),
    "Hind Bold": ("Hind", 1),
    "Hind SemiBold": ("Hind SemiBold", 0),
    "Hind Medium": ("Hind Medium", 0),
    "Rajdhani Bold": ("Rajdhani", 1),
    "Rozha One": ("Rozha One", 0),
    "Kalam Bold": ("Kalam", 1),
}
PANEL_FONTS = list(FONTS.keys())
# short names used inside designs
FONTS.update({"Anton": ("Anton", 0), "Great Vibes": ("Great Vibes", 0)})

_COMMON = {
    "layout": "line", "font": "Poppins ExtraBold", "size": 6.0, "color": "#FFFFFF", "highlight": "#FFD60A",
    "outline": 0, "outline_color": "#000000", "shadow": 0, "shadow_color": "#000000",
    "box": False, "box_color": "#000000", "box_opacity": 60, "position": "middle", "y": 66,
    "animation": "none", "max_words": 6, "lines": 1, "max_chars": 30, "uppercase": False,
    "emph_font": "", "emph_scale": 2.4, "accent_font": "", "accent_color": "", "gradient": "", "glow": False,
    "underline": False, "tracking": 0, "small_case": "none", "emph_case": "lower",
}


def _s(**kw):
    d = dict(_COMMON)
    d.update(kw)
    return d


STYLES = {
    # ---- multi-size "viral" designs (like the reference thumbnails)
    "viral_bigword": _s(name="Viral · Big word (bold / text)", group="viral", layout="stack",
                        font="Poppins SemiBold", size=5.6, emph_font="Poppins ExtraBold", emph_scale=2.9,
                        color="#FFFFFF", highlight="#FFFFFF", gradient="#B4AEF2", shadow=6, y=55,
                        animation="pop", max_words=4, max_chars=24),
    "viral_keyword": _s(name="Viral · Key word stack (this person)", group="viral", layout="stack",
                        font="Poppins Bold", size=5.0, emph_font="Poppins ExtraBold", emph_scale=2.6,
                        color="#FFFFFF", highlight="#FFFFFF", shadow=6, y=62, animation="reveal",
                        max_words=5, max_chars=26),
    "viral_glow": _s(name="Viral · Glow caps (CAPTIONS)", group="viral", layout="glow",
                     font="Poppins Light", size=5.2, tracking=4, emph_font="Poppins ExtraBold", emph_scale=2.0,
                     color="#FFFFFF", highlight="#FFF04A", glow=True, shadow=3, y=60, animation="reveal",
                     max_words=5, max_chars=26),
    "aesthetic_serif": _s(name="Aesthetic · Serif (MOST PEOPLE have no idea)", group="viral", layout="aesthetic",
                          font="Poppins Medium", size=5.2, emph_font="Playfair Display SemiBold", emph_scale=2.0,
                          accent_font="Playfair Display Italic", color="#F4EFE6", highlight="#F4EFE6",
                          underline=True, shadow=4, y=62, animation="fade", max_words=6, max_chars=30),
    "viral_justified": _s(name="Viral · Big stack + script word (IF YOU DON'T…)", group="viral", layout="justified",
                          font="Anton (condensed)", size=7.0, emph_font="Anton", emph_scale=1.6,
                          accent_font="Great Vibes", accent_color="#FFD43B", color="#FFFFFF", highlight="#FFD43B",
                          shadow=7, y=50, animation="pop", max_words=6, max_chars=40, uppercase=True),
    "viral_twotone": _s(name="Viral · Two-tone italic (How To edit)", group="viral", layout="twotone",
                        font="Poppins Black Italic", size=5.6, emph_font="Poppins Black Italic", emph_scale=2.3,
                        color="#FFFFFF", highlight="#E3262B", underline=True, shadow=6, y=62,
                        animation="reveal", max_words=4, max_chars=24),
    # ---- one-line hook designs
    "hook_pop": _s(name="Hook · Word pop", group="hook", font="Poppins ExtraBold", size=7.0,
                   highlight="#FFD60A", outline=7, shadow=3, position="middle", y=66, animation="word_pop",
                   max_words=3, max_chars=18, uppercase=True),
    "hook_box": _s(name="Hook · Boxed", group="hook", font="Baloo 2 ExtraBold", size=6.2, highlight="#FFE600",
                   outline=14, outline_color="#E5262B", box=True, box_color="#E5262B", box_opacity=100,
                   y=68, animation="word_color", max_words=3, max_chars=20, uppercase=True),
    "hook_karaoke": _s(name="Hook · Karaoke fill", group="hook", font="Mukta ExtraBold", size=6.4,
                       highlight="#2BE36B", outline=6, shadow=2, y=66, animation="karaoke", max_words=4,
                       max_chars=22, uppercase=True),
    "hook_one_word": _s(name="Hook · One word", group="hook", font="Poppins Black", size=9.5, highlight="#FFFFFF",
                        outline=8, shadow=4, y=60, animation="one_word", max_words=1, max_chars=14, uppercase=True),
    # ---- full-length subtitle designs
    "full_clean": _s(name="Full · Clean subtitle", group="full", font="Poppins SemiBold", size=3.0, outline=3,
                     shadow=2, position="bottom", y=90, animation="fade", max_words=8, lines=2, max_chars=36),
    "full_boxed": _s(name="Full · Boxed subtitle", group="full", font="Hind SemiBold", size=3.0, outline=12,
                     box=True, box_color="#000000", box_opacity=62, position="bottom", y=90, animation="fade",
                     max_words=8, lines=2, max_chars=38),
    "full_active_word": _s(name="Full · Active word color", group="full", font="Mukta Bold", size=3.3,
                           highlight="#FFD60A", outline=3, shadow=2, position="bottom", y=89,
                           animation="word_color", max_words=7, lines=2, max_chars=34),
    "full_minimal": _s(name="Full · Minimal", group="full", font="Hind Medium", size=2.7, outline=0, shadow=3,
                       position="bottom", y=92, animation="none", max_words=9, lines=1, max_chars=44),
}

POSITIONS = {"top": 18, "middle": 62, "bottom": 90}


def style_options(style_id, overrides=None):
    s = dict(STYLES.get(style_id) or STYLES["full_clean"])
    for k, v in (overrides or {}).items():
        if v is not None and k in s:
            s[k] = v
    return s


def _line_breaks(caption):
    """For each word index, True if a line break comes before it."""
    words = caption["words"]
    breaks = [False] * len(words)
    lines = caption.get("lines") or [caption["text"]]
    if len(lines) > 1:
        pos = 0
        for ln in lines[:-1]:
            pos += len(ln.split())
            if 0 < pos < len(words):
                breaks[pos] = True
    return breaks


def _join(tokens, breaks):
    out = ""
    for i, tok in enumerate(tokens):
        if i:
            out += r"\N" if breaks[i] else " "
        out += tok
    return out


def build_ass(captions, width, height, style, offset=0.0):
    """Write a complete .ass file. `offset` is subtracted from every time (render a range)."""
    s = style
    fam, bold = FONTS.get(s["font"], FONTS["Poppins ExtraBold"])
    base = min(width, height) / 100.0
    size = max(8.0, fm.ass_size(fam, bold, float(s["size"]) * base))
    primary = ass_color(s["color"])
    secondary = ass_color(s["color"])
    if s.get("box"):
        border_style, outline_col = 3, ass_color(s["box_color"], s["box_opacity"])
        outline = max(4, int(s["outline"]))
    else:
        border_style, outline_col, outline = 1, ass_color(s["outline_color"]), int(s["outline"])
    back = ass_color(s["shadow_color"], 70)
    if s["animation"] == "karaoke":
        primary, secondary = ass_color(s["highlight"]), ass_color(s["color"])

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{fam},{size:.1f},{primary},{secondary},{outline_col},{back},{-1 if bold else 0},0,0,0,100,100,0,0,{border_style},{outline},{int(s["shadow"])},2,{int(width * 0.06)},{int(width * 0.06)},{int(height * 0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if s.get("layout") and s["layout"] != "line":
        from .layouts import build_events
        return head + "\n".join(build_events(captions, width, height, s, offset)) + "\n"

    ev = []

    def add(start, end, text):
        st, en = start - offset, end - offset
        if en <= 0 or en - st < 0.01:
            return
        ev.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},Cap,,0,0,0,,{text}")

    y_pct = float(s.get("y") or POSITIONS.get(s.get("position"), 90))
    x, y = width // 2, int(round(height * y_pct / 100.0))
    pos = rf"\an2\pos({x},{y})"
    hi = inline_color(s["highlight"])
    basec = inline_color(s["color"])
    anim = s["animation"]
    for c in captions:
        words = c.get("words") or []
        toks = [esc(w["text"].replace("*", "")) for w in words]
        if not toks:
            continue
        breaks = _line_breaks(c)
        if anim in ("none", "fade", "pop", "reveal"):
            fx = r"\fad(90,70)" if anim == "fade" else (r"\fscx86\fscy86\t(0,140,\fscx100\fscy100)" if anim == "pop" else "")
            add(c["start"], c["end"], "{" + pos + fx + "}" + _join(toks, breaks))
        elif anim == "karaoke":
            parts = []
            for i, w in enumerate(words):
                nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"]
                dur_cs = max(1, int(round((nxt - w["start"]) * 100)))
                lead = ""
                if i == 0 and w["start"] > c["start"]:
                    lead = r"{\k%d}" % int(round((w["start"] - c["start"]) * 100))
                sep = (r"\N" if breaks[i] else " ") if i else ""
                parts.append(sep + lead + r"{\kf%d}" % dur_cs + toks[i])
            add(c["start"], c["end"], "{" + pos + r"\fad(60,60)}" + "".join(parts))
        elif anim == "one_word":
            for i, w in enumerate(words):
                end = words[i + 1]["start"] if i + 1 < len(words) else c["end"]
                pop = r"\fscx70\fscy70\t(0,110,\fscx112\fscy112)\t(110,190,\fscx100\fscy100)"
                add(w["start"], end, "{" + pos + pop + "}" + toks[i])
        else:  # word_color / word_pop: one event per active word
            for i, w in enumerate(words):
                st = c["start"] if i == 0 else w["start"]
                end = words[i + 1]["start"] if i + 1 < len(words) else c["end"]
                out = []
                for j, tok in enumerate(toks):
                    if j == i:
                        if anim == "word_pop":
                            tag = r"{\c&H%s&\fscx100\fscy100\t(0,90,\fscx118\fscy118)\t(90,170,\fscx110\fscy110)}" % hi
                            out.append(tag + tok + r"{\c&H%s&\fscx100\fscy100}" % basec)
                        else:
                            out.append(r"{\c&H%s&}" % hi + tok + r"{\c&H%s&}" % basec)
                    else:
                        out.append(tok)
                entry = ""
                if i == 0:
                    entry = r"\fscx88\fscy88\t(0,120,\fscx100\fscy100)" if anim == "word_pop" else r"\fad(70,0)"
                text = "".join(((r"\N" if breaks[j] else " ") if j else "") + out[j] for j in range(len(out)))
                add(st, end, "{" + pos + entry + "}" + text)
    return head + "\n".join(ev) + "\n"
