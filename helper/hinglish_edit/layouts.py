"""Multi-size "viral" caption layouts: one key word big, the rest small, stacked in lines.

Layouts
  stack      small words / BIG WORD / small words   ("this / person / can't do this", "bold / text")
  glow       thin line / GLOWING CAPS word           ("Do you want your / CAPTIONS")
  aesthetic  LABEL pill / SERIF CAPS / italic + line ("THE TRUTH / MOST PEOPLE / have no idea.")
  justified  every word on its own line, all lines the same width, one script accent word
             ("IF / YOU / DON'T / USE / THESE / Captions / YOU'RE BEHIND")
  twotone    heavy italic, key word bigger in a second color, brush streak under it ("How To / edit")

The key word is picked automatically (longest word that is not a filler like "hai", "the"),
or the user marks it in the caption text with *stars*: "most *people* have no idea".
"""
from . import fontmetrics as fm
from .ass_style_util import ass_color, inline_color, esc, ass_time
from .textnorm import norm

STOP = set("""
a an the and or but if so to of in on at for with from by is am are was were be been it this that these those
i you he she we they me my your our his her their its do does did not no yes ok okay just very really
hai hain ho tha thi the hoon hun ka ki ke ko se me mein main mai par pe aur ya bhi to toh hi na nahi kya
ye yeh wo woh is us iss uss ek ab jo ki jab tab kar karo raha rahi rahe gaya gayi
है हैं हो था थी थे हूँ हूं का की के को से में मैं पर पे और या भी तो ही ना न नहीं क्या ये यह वो वह इस उस एक अब जो जब तब कर रहा रही रहे गया गई
""".split())


def _is_deva(t):
    return any("ऀ" <= ch <= "ॿ" for ch in t)


def apply_case(text, case):
    if case == "upper":
        return text.upper()
    if case == "lower":
        return text.lower()
    return text


def strip_marks(words):
    """'*most', 'people*' -> marked indices. Returns (clean texts, marked set)."""
    marked, inside, clean = set(), False, []
    for i, w in enumerate(words):
        t = w
        starts, ends = t.startswith("*"), t.endswith("*") and len(t) > 1
        if starts:
            inside = True
        if inside:
            marked.add(i)
        if ends or (starts and t.count("*") >= 2):
            inside = False
        clean.append(t.replace("*", ""))
    return clean, marked


def pick_emphasis(texts, marked, count=1):
    if marked:
        return sorted(marked)
    best, best_s = None, None
    n = len(texts)
    for i, t in enumerate(texts):
        k = norm(t)
        if not k:
            continue
        s = len(k) + (0.6 * i / max(1, n - 1))
        if k in STOP or len(k) <= 2:
            s -= 20
        if best_s is None or s > best_s:
            best, best_s = i, s
    if best is None:
        return [0]
    out = [best]
    if count > 1 and best + 1 < n and norm(texts[best + 1]) not in STOP:
        out.append(best + 1)
    return out


def _chunks(idx, size):
    return [idx[i:i + size] for i in range(0, len(idx), size)]


def recipe(layout, texts, emph):
    n = len(texts)
    e0, e1 = emph[0], emph[-1]
    pre = list(range(0, e0))
    span = list(range(e0, e1 + 1))
    post = list(range(e1 + 1, n))
    if layout == "aesthetic":
        lines = []
        if pre:
            lines.append(("label", pre[-4:]))
            if len(pre) > 4:
                lines.insert(0, ("label", pre[:-4]))
        lines.append(("main", span))
        for ch in _chunks(post, 4):
            lines.append(("italic", ch))
        return lines
    if layout == "justified":
        size = 1 if n <= 7 else 2
        lines = []
        for ch in _chunks(pre, size):
            lines.append(("stack", ch))
        lines.append(("accent", span))
        for ch in _chunks(post, size):
            lines.append(("stack", ch))
        return lines
    size = 5 if layout == "glow" else 3
    lines = [("small", ch) for ch in _chunks(pre, size)]
    lines.append(("emph", span))
    lines += [("small", ch) for ch in _chunks(post, size)]
    return lines


def _font(name):
    from .ass_style import FONTS
    return FONTS.get(name, FONTS["Poppins ExtraBold"])


def roles(s, layout, base):
    """Style of each kind of line, from the flat options the panel edits."""
    size = float(s["size"]) * base
    big = size * float(s.get("emph_scale") or 2.4)
    up = bool(s.get("uppercase"))
    r = {}
    if layout == "aesthetic":
        r["label"] = dict(font=s["font"], em=size * 0.5, color=s["color"], case="upper", tracking=size * 0.12, pill=True)
        r["main"] = dict(font=s.get("emph_font") or "Playfair Display SemiBold", em=big, color=s["color"], case="upper")
        r["italic"] = dict(font=s.get("accent_font") or "Playfair Display Italic", em=big * 0.82,
                           color=s.get("accent_color") or s["color"], case="none", underline=bool(s.get("underline", True)))
    elif layout == "justified":
        r["stack"] = dict(font=s.get("emph_font") or "Anton", em=size, color=s["color"], case="upper", justify=True)
        r["accent"] = dict(font=s.get("accent_font") or "Great Vibes", em=big, color=s.get("accent_color") or s["highlight"],
                           case="none", rotate=-7, overlap=True)
    elif layout == "glow":
        r["small"] = dict(font=s["font"], em=size, color=s["color"], case=s.get("small_case") or "none",
                          tracking=float(s.get("tracking") or 0) * base * 0.1)
        r["emph"] = dict(font=s.get("emph_font") or s["font"], em=big, color=s["highlight"], case="upper",
                         glow=bool(s.get("glow", True)), gradient=s.get("gradient") or "")
    else:  # stack, twotone
        r["small"] = dict(font=s["font"], em=size, color=s["color"], case=s.get("small_case") or "none",
                          tracking=float(s.get("tracking") or 0) * base * 0.1)
        r["emph"] = dict(font=s.get("emph_font") or s["font"], em=big, color=s["highlight"],
                         case="upper" if up else (s.get("emph_case") or "lower"),
                         glow=bool(s.get("glow")), gradient=s.get("gradient") or "",
                         streak=layout == "twotone" and bool(s.get("underline", True)))
    return r


def _measure(role, text, em):
    fam, bold = _font(role["font"])
    return fm.width(fam, bold, apply_case(text, role["case"]), em, role.get("tracking", 0))


def _rounded_rect(w, h, r):
    r = min(r, h / 2, w / 2)
    k = r * 0.45
    return (f"m {r:.1f} 0 l {w - r:.1f} 0 b {w - k:.1f} 0 {w:.1f} {k:.1f} {w:.1f} {r:.1f} "
            f"l {w:.1f} {h - r:.1f} b {w:.1f} {h - k:.1f} {w - k:.1f} {h:.1f} {w - r:.1f} {h:.1f} "
            f"l {r:.1f} {h:.1f} b {k:.1f} {h:.1f} 0 {h - k:.1f} 0 {h - r:.1f} l 0 {r:.1f} b 0 {k:.1f} {k:.1f} 0 {r:.1f} 0")


def build_events(captions, W, H, s, offset):
    layout = s.get("layout") or "stack"
    base = min(W, H) / 100.0
    rs = roles(s, layout, base)
    cx = W / 2.0
    max_w = W * 0.9
    outline = float(s.get("outline") or 0)
    shadow = float(s.get("shadow") or 0)
    anim = s.get("animation") or "pop"
    events = []

    def ev(layer, t0, t1, text):
        a, b = t0 - offset, t1 - offset
        if b <= 0 or b - a < 0.01:
            return
        events.append(f"Dialogue: {layer},{ass_time(a)},{ass_time(b)},Cap,,0,0,0,,{text}")

    for c in captions:
        words = c.get("words") or []
        if not words:
            continue
        texts, marked = strip_marks([w["text"] for w in words])
        emph = pick_emphasis(texts, marked, 1)
        lines = recipe(layout, texts, emph)

        # ---- sizes: fit width, justify stacks
        L = []
        for role_name, idx in lines:
            role = rs[role_name]
            txt = " ".join(texts[i] for i in idx)
            em = role["em"]
            w = _measure(role, txt, em)
            if role.get("justify") and w > 0:
                target = max_w * 0.80
                em = min(em * 2.6, em * target / w)
                w = _measure(role, txt, em)
            if w > max_w:
                em *= max_w / w
                w = max_w
            L.append({"role": role, "name": role_name, "idx": idx, "em": em, "w": w, "text": txt})

        stack_em = max([x["em"] for x in L if x["role"].get("justify")] or [0])
        for x in L:
            if x["role"].get("overlap") and stack_em:
                x["em"] = max(x["em"], stack_em * 0.95)
                x["w"] = _measure(x["role"], x["text"], x["em"])
                if x["w"] > max_w:
                    x["em"] *= max_w / x["w"]
                    x["w"] = max_w

        # ---- vertical stacking (block centered on y)
        heights = []
        for ln in L:
            fam, bold = _font(ln["role"]["font"])
            capp = fm.cap_px(fam, bold, ln["em"])
            if ln["role"].get("overlap"):
                h, asc = ln["em"] * 0.42, ln["em"] * 0.42
            elif ln["role"]["case"] == "upper":
                gap = 0.10 if ln["role"].get("justify") else 0.32
                h, asc = capp * (1 + gap), capp * (1 + gap * 0.5)
            else:
                h, asc = ln["em"] * 1.02, ln["em"] * 0.80
            if ln["role"].get("pill"):
                h, asc = ln["em"] * 2.2, ln["em"] * 1.45
            heights.append((h, asc))
        total = sum(h for h, _ in heights)
        top = H * float(s.get("y") or 62) / 100.0 - total / 2.0
        top = max(H * 0.03, min(top, H * 0.97 - total))
        for ln, (h, asc) in zip(L, heights):
            ln["baseline"] = top + asc
            ln["top"] = top
            top += h

        # ---- time slices (words appear as they are spoken)
        reveal = anim in ("reveal", "word_color")
        cuts = [c["start"]] + ([w["start"] for w in words[1:]] if reveal else [])
        cuts = [max(c["start"], min(t, c["end"])) for t in cuts]
        for k, t0 in enumerate(cuts):
            t1 = cuts[k + 1] if k + 1 < len(cuts) else c["end"]
            if t1 - t0 < 0.01:
                continue
            first, last = k == 0, k == len(cuts) - 1
            visible = (lambda i: words[i]["start"] <= t0 + 1e-3 or i == 0) if anim == "reveal" else (lambda i: True)
            newly = (lambda i: k > 0 and abs(words[i]["start"] - t0) < 1e-3) if anim == "reveal" else (lambda i: False)
            active = (lambda i: abs(words[i]["start"] - t0) < 1e-3 or (k == 0 and i == 0)) if anim == "word_color" else (lambda i: False)
            entry = ""
            if first and anim in ("pop", "reveal", "word_color"):
                entry = r"\fscx86\fscy86\t(0,140,\fscx100\fscy100)"
            elif first and anim == "fade":
                entry = r"\fad(110,0)"
            exit_ = r"\fad(0,90)" if last and anim != "none" else ""

            for ln in L:
                role = ln["role"]
                fam, bold = _font(role["font"])
                em = ln["em"]
                size = fm.ass_size(fam, bold, em)
                desc = fm.descent_px(fam, bold, em)
                y = ln["baseline"] + desc
                rot = rf"\frz{role['rotate']}" if role.get("rotate") else ""
                spc = rf"\fsp{role.get('tracking', 0):.1f}" if role.get("tracking") else ""
                base_tags = rf"\an2\fn{fam}\fs{size:.1f}\b{bold}\i0{spc}{rot}"

                def body(alpha_hex, color_override=None):
                    parts = []
                    for j, i in enumerate(ln["idx"]):
                        t = esc(apply_case(texts[i], role["case"]))
                        tag = ""
                        if _is_deva(t) and not fm.has_deva(fam, bold):
                            f2, b2 = fm.DEVA_FALLBACK.get(fam, ("Hind SemiBold", 0))
                            tag += rf"\fn{f2}\b{b2}\fs{fm.ass_size(f2, b2, em):.1f}"
                        if not visible(i):
                            tag += r"\alpha&HFF&"
                        elif newly(i):
                            tag += rf"\alpha&HFF&\t(0,90,\alpha&H{alpha_hex}&)"
                        else:
                            tag += rf"\alpha&H{alpha_hex}&"
                        if active(i) and color_override is None and role is rs.get("small"):
                            tag += rf"\c&H{inline_color(s['highlight'])}&"
                        elif color_override:
                            tag += rf"\c&H{color_override}&"
                        else:
                            tag += rf"\c&H{inline_color(role['color'])}&"
                        reset = rf"\fn{fam}\b{bold}\fs{size:.1f}" if "\\fn" in tag else ""
                        parts.append(("" if j == 0 else " ") + "{" + tag + "}" + t + ("{" + reset + "}" if reset else ""))
                    return "".join(parts)

                # soft drop shadow
                if shadow > 0:
                    dx, dy = shadow * 0.5 * base / 10, shadow * 0.9 * base / 10
                    sc = inline_color(s.get("shadow_color") or "#000000")
                    ev(0, t0, t1, "{" + base_tags + rf"\pos({cx + dx:.1f},{y + dy:.1f})\bord{outline:.1f}\shad0"
                       rf"\3c&H{sc}&\blur{max(2.0, shadow * base / 6):.1f}" + entry + exit_ + "}" + body("70", sc))
                # glow
                if role.get("glow"):
                    gc = inline_color(role["color"])
                    ev(1, t0, t1, "{" + base_tags + rf"\pos({cx:.1f},{y:.1f})\bord{em * 0.10:.1f}\shad0"
                       rf"\3c&H{gc}&\blur{em * 0.22:.1f}" + entry + exit_ + "}" + body("40", gc))
                # main text
                oc = inline_color(s.get("outline_color") or "#000000")
                ev(2, t0, t1, "{" + base_tags + rf"\pos({cx:.1f},{y:.1f})\bord{outline:.1f}\shad0\3c&H{oc}&"
                   + entry + exit_ + "}" + body("00"))
                # vertical gradient on the key word: color bands clipped over the main text
                if role.get("gradient"):
                    top_y = ln["baseline"] - (fm.cap_px(fam, bold, em) * 1.05 if role["case"] == "upper" else em * 0.78)
                    bot_y = ln["baseline"] + em * 0.24
                    n = 8
                    c1, c2 = role["color"], role["gradient"]
                    for b in range(n):
                        f = (b + 0.5) / n
                        col = _mix(c1, c2, f)
                        y1 = top_y + (bot_y - top_y) * b / n
                        y2 = top_y + (bot_y - top_y) * (b + 1) / n + 1
                        ev(3, t0, t1, "{" + base_tags + rf"\pos({cx:.1f},{y:.1f})\bord0\shad0"
                           rf"\clip(0,{y1:.0f},{W},{y2:.0f})" + entry + exit_ + "}" + body("00", inline_color(col)))
                # label pill outline
                if role.get("pill") and (anim != "reveal" or all(visible(i) for i in ln["idx"])):
                    pw, ph = ln["w"] + em * 1.6, em * 1.75
                    px, py = cx - pw / 2, ln["baseline"] - em * 1.18
                    ev(2, t0, t1, "{" + rf"\an7\pos({px:.1f},{py:.1f})\bord{max(1.0, em * 0.06):.1f}\shad0"
                       rf"\3c&H{inline_color(role['color'])}&\1a&HFF&\p1" + exit_ + "}" + _rounded_rect(pw, ph, ph / 2) + r"{\p0}")
                # elegant underline under the italic line
                if role.get("underline") and ln is L[-1] and all(visible(i) for i in ln["idx"]):
                    uw, th = ln["w"] * 0.9, max(2.0, em * 0.045)
                    ux, uy = cx - uw / 2 + em * 0.3, ln["baseline"] + em * 0.18
                    shape = (f"m 0 {th:.1f} b {uw * 0.3:.1f} {-th:.1f} {uw * 0.7:.1f} {-th * 0.6:.1f} {uw:.1f} {th * 0.4:.1f} "
                             f"l {uw:.1f} {th * 1.4:.1f} b {uw * 0.7:.1f} {th * 0.5:.1f} {uw * 0.3:.1f} {th * 0.2:.1f} 0 {th * 2:.1f}")
                    ev(2, t0, t1, "{" + rf"\an7\pos({ux:.1f},{uy:.1f})\bord0\shad0\1c&H{inline_color(role['color'])}&\p1"
                       + exit_ + "}" + shape + r"{\p0}")
                # brush streak behind the key word (two-tone)
                if role.get("streak") and all(visible(i) for i in ln["idx"]):
                    sw, sh = ln["w"] * 1.08, em * 0.16
                    sx, sy = cx - sw / 2, ln["baseline"] + em * 0.10
                    skew = sh * 1.2
                    shape = f"m {skew:.1f} 0 l {sw:.1f} {sh * 0.2:.1f} l {sw - skew:.1f} {sh:.1f} l 0 {sh * 0.85:.1f}"
                    ev(1, t0, t1, "{" + rf"\an7\pos({sx:.1f},{sy:.1f})\bord0\shad0\1c&H{inline_color(role['color'])}&\p1"
                       + exit_ + "}" + shape + r"{\p0}")
    return events


def _mix(c1, c2, f):
    def rgb(h):
        h = (h or "#FFFFFF").lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    a, b = rgb(c1), rgb(c2)
    return "#" + "".join(f"{int(round(x + (y - x) * f)):02X}" for x, y in zip(a, b))
