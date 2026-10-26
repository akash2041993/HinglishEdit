"""ffmpeg / ffprobe helpers: find ffmpeg, probe files, mix the sequence audio, measure loudness."""
import array
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import wave
import zipfile

from .config import app_dir, bundle_dir

FFMPEG_ZIP_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class MediaError(Exception):
    pass


def _exe(name):
    return name + (".exe" if os.name == "nt" else "")


def find_tool(name):
    env = os.environ.get("HINGLISH_" + name.upper())
    if env and os.path.isfile(env):
        return env
    for d in (os.path.join(bundle_dir(), "ffmpeg"), os.path.join(bundle_dir(), "ffmpeg", "bin"),
              os.path.join(app_dir(), "ffmpeg", "bin")):
        p = os.path.join(d, _exe(name))
        if os.path.isfile(p):
            return p
    return shutil.which(name)


def ffmpeg():
    p = find_tool("ffmpeg")
    if not p:
        raise MediaError("ffmpeg was not found. Click 'Install ffmpeg' in the panel, or install it and restart the helper.")
    return p


def ffprobe():
    p = find_tool("ffprobe")
    if not p:
        raise MediaError("ffprobe was not found (it comes with ffmpeg).")
    return p


def run(cmd, timeout=None, progress=None, duration=None):
    """Run a command. If progress and duration are given, ffmpeg progress is reported 0..1."""
    if progress and duration:
        cmd = list(cmd)
        cmd[1:1] = ["-progress", "pipe:1", "-nostats"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", creationflags=_CREATE_NO_WINDOW)
        err_lines = []
        import threading

        def _drain():
            for ln in proc.stderr:
                err_lines.append(ln)
                if len(err_lines) > 200:
                    del err_lines[:100]
        t = threading.Thread(target=_drain, daemon=True)
        t.start()
        for ln in proc.stdout:
            if ln.startswith("out_time_us=") or ln.startswith("out_time_ms="):
                try:
                    us = int(ln.split("=", 1)[1])
                    progress(min(0.999, us / 1e6 / duration))
                except ValueError:
                    pass
        proc.wait(timeout=timeout)
        t.join(timeout=2)
        if proc.returncode != 0:
            raise MediaError("ffmpeg failed: " + "".join(err_lines[-15:]))
        return ""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, creationflags=_CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise MediaError(f"{os.path.basename(cmd[0])} failed: {r.stderr[-1500:]}")
    return r.stdout


MAC_FFMPEG_URLS = {
    "arm64": "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/{}.zip",
    "x86_64": "https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/release/{}.zip",
}


def _download(url, tmp, progress, lo, hi):
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(lo + (hi - lo) * done / total)


def install_ffmpeg(progress=None):
    """Download a static ffmpeg build into the helper's folder (Windows and Mac).
    The installers already include ffmpeg; this is only for running from source."""
    import platform
    dest = os.path.join(app_dir(), "ffmpeg", "bin")
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), "hinglish_ffmpeg.zip")
    if os.name == "nt":
        jobs = [(FFMPEG_ZIP_URL, ("ffmpeg.exe", "ffprobe.exe"))]
    elif sys.platform == "darwin":
        arch = "arm64" if platform.machine() == "arm64" else "x86_64"
        jobs = [(MAC_FFMPEG_URLS[arch].format(n), (n,)) for n in ("ffmpeg", "ffprobe")]
    else:
        raise MediaError("Automatic install is for Windows and Mac. Install ffmpeg with your package manager.")
    for k, (url, names) in enumerate(jobs):
        lo, hi = 0.95 * k / len(jobs), 0.95 * (k + 1) / len(jobs)
        _download(url, tmp, progress, lo, hi)
        with zipfile.ZipFile(tmp) as z:
            for m in z.namelist():
                base = os.path.basename(m)
                if base in names:
                    out_path = os.path.join(dest, base)
                    with z.open(m) as src, open(out_path, "wb") as out:
                        shutil.copyfileobj(src, out)
                    os.chmod(out_path, 0o755)
        os.remove(tmp)
    if progress:
        progress(1.0)
    return find_tool("ffmpeg")


def ffmpeg_info():
    p = find_tool("ffmpeg")
    if not p:
        return {"found": False}
    try:
        out = run([p, "-hide_banner", "-version"], timeout=20)
        ver = out.splitlines()[0] if out else ""
        filt = run([p, "-hide_banner", "-h", "filter=ass"], timeout=20)
        return {"found": True, "path": p, "version": ver, "ass": "alpha" in filt}
    except Exception as e:  # noqa: BLE001
        return {"found": True, "path": p, "error": str(e)}


# ------------------------------------------------------------------ probe
def probe(path):
    out = run([ffprobe(), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path], timeout=60)
    data = json.loads(out)
    info = {"path": path, "duration": float(data.get("format", {}).get("duration") or 0), "video": None, "audio": []}
    tc = (data.get("format", {}).get("tags") or {}).get("timecode")
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["video"] is None and s.get("disposition", {}).get("attached_pic", 0) == 0:
            num, den = (s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1").split("/")
            fps = float(num) / float(den) if float(den) else 0.0
            info["video"] = {"width": s.get("width"), "height": s.get("height"), "fps": fps,
                             "frames": int(s.get("nb_frames") or 0)}
            tc = tc or (s.get("tags") or {}).get("timecode")
        elif s.get("codec_type") == "audio":
            info["audio"].append({"index": s.get("index"), "channels": int(s.get("channels") or 0),
                                  "sample_rate": int(s.get("sample_rate") or 48000)})
    info["timecode"] = tc
    return info


# ------------------------------------------------------------------ audio mix of the sequence
def mix_sequence_audio(seq, out_dir, progress=None):
    """Mix the audio of the sequence (as the viewer hears it) to:
         analysis.wav  16 kHz mono, for the loudness envelope
         upload.mp3    16 kHz mono 64 kbps, for transcription
       seq["audio_items"]: [{path, start, end, in}] in seconds; seq["duration"]."""
    items = [it for it in seq.get("audio_items", [])
             if not it.get("disabled") and it.get("path") and it.get("has_audio", True)]
    dur = float(seq["duration"])
    if dur <= 0:
        raise MediaError("The sequence is empty.")
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, "analysis.wav")
    mp3 = os.path.join(out_dir, "upload.mp3")
    cmd = [ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=16000:cl=mono"]
    files = []
    for it in items:
        if it["path"] not in files:
            files.append(it["path"])
    for f in files:
        if not os.path.isfile(f):
            raise MediaError(f"Media file not found: {f}")
        cmd += ["-i", f]
    parts = ["[0:a]anull[base]"]
    labels = ["[base]"]
    for n, it in enumerate(items):
        k = files.index(it["path"]) + 1
        a_in = float(it.get("in", 0.0))
        length = float(it["end"]) - float(it["start"])
        if length <= 0:
            continue
        delay = int(round(float(it["start"]) * 1000))
        parts.append(
            f"[{k}:a:0]atrim=start={a_in:.4f}:duration={length:.4f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=16000:channel_layouts=mono,adelay={delay}:all=1[a{n}]")
        labels.append(f"[a{n}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,"
                 f"atrim=duration={dur:.3f},asplit=2[w][m]")
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "[w]", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav,
            "-map", "[m]", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", mp3]
    run(cmd, progress=progress, duration=dur)
    return wav, mp3


def envelope_db(wav_path, hop=0.01):
    """Loudness (dBFS) every `hop` seconds of a 16-bit mono WAV."""
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    step = max(1, int(sr * hop))
    try:
        import numpy as np  # fast path
        a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
        frames = len(a) // step
        a = a[:frames * step].reshape(frames, step)
        rms = np.sqrt((a * a).mean(axis=1))
        db = 20 * np.log10(np.maximum(rms, 1e-6))
        return [round(float(x), 1) for x in db]
    except ImportError:
        s = array.array("h")
        s.frombytes(raw)
        if sys.byteorder == "big":
            s.byteswap()
        out = []
        for i in range(0, len(s) - step + 1, step):
            chunk = s[i:i + step]
            acc = 0
            for v in chunk:
                acc += v * v
            rms = math.sqrt(acc / step) / 32768.0
            out.append(round(20 * math.log10(max(rms, 1e-6)), 1))
        return out


def grab_frame(path, t, out_png, width=640):
    run([ffmpeg(), "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1",
         "-vf", f"scale={width}:-2", out_png], timeout=60)
    return out_png
