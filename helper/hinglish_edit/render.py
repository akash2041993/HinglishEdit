"""Draw designed captions: a transparent video layer for Premiere, and still previews for the panel."""
import base64
import os
import tempfile

from . import media
from .ass_style import build_ass
from .config import fonts_dir
from .fcpxml import Rate


def _filter_path(path):
    """Escape a file path for use inside an ffmpeg filter option (works on Windows too)."""
    p = os.path.abspath(path).replace("\\", "/")
    p = p.replace(":", r"\:").replace("'", r"'\\\''")
    return "'" + p + "'"


def _rate_str(fps):
    r = Rate(fps)
    return f"{r.timebase * 1000}/1001" if r.ntsc else str(r.timebase)


def render_overlay(captions, style, seq, start, end, out_path, progress=None):
    """Transparent QuickTime (Animation codec, with alpha) the length of [start, end] seconds.
    Animation codec keeps files small for mostly-empty frames, and Premiere reads it natively."""
    w, h = int(seq.get("width") or 1920), int(seq.get("height") or 1080)
    fps = seq.get("fps") or 30
    length = max(0.1, end - start)
    caps = [c for c in captions if c["end"] > start and c["start"] < end]
    ass_text = build_ass(caps, w, h, style, offset=start)
    ass_path = os.path.splitext(out_path)[0] + ".ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_text)
    vf = f"ass=filename={_filter_path(ass_path)}:fontsdir={_filter_path(fonts_dir())}:alpha=1"
    cmd = [media.ffmpeg(), "-y", "-v", "error",
           "-f", "lavfi", "-i", f"color=c=black@0.0:s={w}x{h}:r={_rate_str(fps)}:d={length:.3f},format=rgba",
           "-vf", vf, "-c:v", "qtrle", "-pix_fmt", "argb", out_path]
    media.run(cmd, progress=progress, duration=length)
    return out_path


def _background(seq, t, w, h, tmp):
    """A frame of the real video at sequence time t (V1 upwards), else a neutral backdrop."""
    for tr in sorted(seq.get("video_tracks", []), key=lambda x: -x["index"]):
        for it in tr.get("items", []):
            if it.get("path") and not it.get("disabled") and it["start"] <= t < it["end"]:
                src_t = float(it.get("in", 0)) + (t - it["start"])
                png = os.path.join(tmp, "bg.png")
                try:
                    media.run([media.ffmpeg(), "-y", "-v", "error", "-ss", f"{src_t:.3f}", "-i", it["path"],
                               "-frames:v", "1", "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                               f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2", png], timeout=60)
                    return png
                except media.MediaError:
                    pass
    return None


def preview_png(caption, style, seq, at=None, max_width=640):
    """PNG (base64) showing one caption at time `at` (default: just after its 2nd word starts)."""
    w, h = int(seq.get("width") or 1920), int(seq.get("height") or 1080)
    words = caption.get("words") or []
    if at is None:
        at = words[min(1, len(words) - 1)]["start"] + 0.2 if words else (caption["start"] + caption["end"]) / 2
    at = min(max(at, caption["start"] + 0.01), caption["end"] - 0.01)
    with tempfile.TemporaryDirectory() as tmp:
        ass_path = os.path.join(tmp, "p.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(build_ass([caption], w, h, style, offset=caption["start"]))
        local_t = at - caption["start"]
        bg = _background(seq, at, w, h, tmp)
        if bg:
            src = ["-loop", "1", "-framerate", "25", "-t", f"{local_t + 0.2:.3f}", "-i", bg]
        else:
            src = ["-f", "lavfi", "-i", f"color=c=0x3a4250:s={w}x{h}:r=25:d={local_t + 0.2:.3f}"]
        out = os.path.join(tmp, "out.png")
        vf = (f"format=rgb24,ass=filename={_filter_path(ass_path)}:fontsdir={_filter_path(fonts_dir())},"
              f"scale={max_width}:-2")
        media.run([media.ffmpeg(), "-y", "-v", "error"] + src +
                  ["-vf", vf, "-ss", f"{local_t:.3f}", "-frames:v", "1", "-update", "1", out], timeout=60)
        with open(out, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
