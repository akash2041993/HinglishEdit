"""Build helper/fonts/metrics.json from the bundled fonts (run once when fonts change; needs fontTools).
The helper uses it to measure text width/height for caption layouts without needing fontTools itself."""
import glob
import json
import os
import sys

from fontTools.ttLib import TTFont

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "helper", "fonts")
RANGES = [(0x20, 0x250), (0x900, 0x980), (0x2000, 0x2070), (0x20B9, 0x20BA)]
out = {}
for p in sorted(glob.glob(os.path.join(D, "*.ttf"))):
    f = TTFont(p)
    n = f["name"]
    fam = n.getName(1, 3, 1, 0x409) or n.getName(1, 1, 0, 0)
    sub = str(n.getName(2, 3, 1, 0x409) or n.getName(2, 1, 0, 0) or "Regular")
    os2 = f["OS/2"]
    bold = 1 if ("Bold" in sub and "Semi" not in sub and "Extra" not in sub) else 0
    cmap = f.getBestCmap()
    hmtx = f["hmtx"].metrics
    adv = {}
    for a, b in RANGES:
        for cp in range(a, b):
            g = cmap.get(cp)
            if g:
                adv[cp] = hmtx[g][0]
    key = f"{fam}|{bold}"
    out[key] = {
        "file": os.path.basename(p), "family": str(fam), "bold": bold,
        "upm": f["head"].unitsPerEm, "win_ascent": os2.usWinAscent, "win_descent": os2.usWinDescent,
        "cap": getattr(os2, "sCapHeight", 0) or int(0.7 * f["head"].unitsPerEm),
        "xh": getattr(os2, "sxHeight", 0) or int(0.5 * f["head"].unitsPerEm),
        "deva": 0x915 in cmap,
        "adv": adv,
    }
with open(os.path.join(D, "metrics.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, separators=(",", ":"))
print(len(out), "fonts ->", os.path.join(D, "metrics.json"))
