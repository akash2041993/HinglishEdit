"""Render every caption design to one picture (gallery.png) to check how they look.
Run: python tests/gallery.py [out.png] [portrait|landscape]"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hinglish_edit import ass_style  # noqa: E402
from hinglish_edit.config import fonts_dir  # noqa: E402
from hinglish_edit.render import _filter_path  # noqa: E402

SAMPLES = {
    "viral_bigword": "bold text",
    "viral_keyword": "this person can't do this",
    "viral_glow": "Do you want your *captions*",
    "aesthetic_serif": "the truth *most people* have no idea.",
    "viral_justified": "if you don't use these *captions* you're behind",
    "viral_twotone": "How to *edit*",
    "hook_pop": "KYA AAP VIRAL",
    "hook_box": "सबसे बड़ा राज़",
    "hook_karaoke": "आज हम सीखेंगे",
    "hook_one_word": "WAIT",
    "full_clean": "aaj hum baat karenge video editing ke baare mein",
    "full_boxed": "आज हम बात करेंगे वीडियो एडिटिंग के बारे में",
    "full_active_word": "toh chaliye shuru karte hain bina time waste kiye",
    "full_minimal": "this is a calm, minimal subtitle line",
}


def caption_for(text, t0=0.0, per_word=0.35):
    words = []
    t = t0
    for tok in text.split():
        words.append({"text": tok, "start": t, "end": t + per_word * 0.9})
        t += per_word
    return {"start": t0, "end": t + 0.5, "text": text, "lines": [text.replace("*", "")], "words": words}


def render_one(style_id, text, w, h, out_png, tmp):
    s = ass_style.style_options(style_id)
    cap = caption_for(text)
    if s.get("lines", 1) == 2 and len(cap["words"]) > 5:
        toks = text.replace("*", "").split()
        k = (len(toks) + 1) // 2
        cap["lines"] = [" ".join(toks[:k]), " ".join(toks[k:])]
    ass = os.path.join(tmp, style_id + ".ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_style.build_ass([cap], w, h, s))
    at = cap["end"] - 0.3  # all words visible
    bg = (f"gradients=s={w}x{h}:c0=0x2b3440:c1=0x5b4636:x0=0:y0=0:x1={w}:y1={h}:d=10,format=rgb24")
    vf = f"ass=filename={_filter_path(ass)}:fontsdir={_filter_path(fonts_dir())}"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", bg, "-vf", vf, "-ss", f"{at:.2f}",
                    "-frames:v", "1", out_png], check=True)


HINDI = {
    "viral_bigword": "सबसे *बड़ा* सच",
    "viral_keyword": "ये *गलती* मत करना",
    "viral_glow": "kya aap *viral* hona chahte ho",
    "aesthetic_serif": "sach ye hai ki *zyada log* nahi jaante.",
    "viral_justified": "agar aap ye *captions* use nahi karte",
    "viral_twotone": "aise karo *edit*",
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "gallery.png"
    portrait = (sys.argv[2] if len(sys.argv) > 2 else "portrait") == "portrait"
    w, h = (1080, 1920) if portrait else (1920, 1080)
    from PIL import Image, ImageDraw
    tmp = tempfile.mkdtemp()
    tiles = []
    samples = HINDI if (len(sys.argv) > 3 and sys.argv[3] == "hindi") else SAMPLES
    for sid, text in samples.items():
        p = os.path.join(tmp, sid + ".png")
        render_one(sid, text, w, h, p, tmp)
        im = Image.open(p).convert("RGB")
        im.thumbnail((360, 640) if portrait else (480, 270))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0))
        d.text((4, 3), ass_style.STYLES[sid]["name"][:60], fill=(255, 255, 255))
        tiles.append(im)
    cols = 5 if portrait else 4
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
