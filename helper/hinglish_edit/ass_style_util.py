"""Small ASS (Advanced SubStation) helpers shared by the caption designs."""


def ass_color(hex_color, opacity=100):
    """'#RRGGBB' + opacity (0-100) -> '&HAABBGGRR'."""
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        r, g, b = 255, 255, 255
    a = 255 - int(round(255 * max(0, min(100, opacity)) / 100))
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


def inline_color(hex_color):
    """'#RRGGBB' -> 'BBGGRR' for \\c&H..& tags."""
    return ass_color(hex_color)[4:]


def ass_time(sec):
    sec = max(0.0, sec)
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(text):
    return text.replace("\\", "＼").replace("{", "(").replace("}", ")")
