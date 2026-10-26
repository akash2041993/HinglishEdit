"""Where the helper keeps its files, and the saved settings (API keys etc.)."""
import json
import os
import sys
import threading

VERSION = "1.0.2"
DEFAULT_PORT = 47800

_lock = threading.Lock()


def bundle_dir():
    """Folder with bundled files (fonts, ffmpeg) - works for source and for the packaged .exe."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_dir():
    base = os.environ.get("HINGLISH_HOME")
    if not base:
        if os.name == "nt":
            base = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "HinglishEdit")
        else:
            base = os.path.join(os.path.expanduser("~"), ".hinglish_edit")
    os.makedirs(base, exist_ok=True)
    return base


def jobs_dir():
    d = os.path.join(app_dir(), "jobs")
    os.makedirs(d, exist_ok=True)
    return d


def output_dir():
    """Files Premiere imports (XML timelines, SRT, caption videos). Kept, so projects stay linked."""
    d = os.path.join(app_dir(), "output")
    os.makedirs(d, exist_ok=True)
    return d


def fonts_dir():
    return os.path.join(bundle_dir(), "fonts")


DEFAULTS = {
    "provider": "elevenlabs",
    "elevenlabs_key": "",
    "sarvam_key": "",
    "deepgram_key": "",
    "language": "auto",          # auto | hi | en
    "keyterms": [],
    "filler_sounds": None,       # None = built-in list
    "filler_ambiguous": None,
    "filler_phrases": None,
}


def _path():
    return os.path.join(app_dir(), "settings.json")


def load():
    with _lock:
        data = dict(DEFAULTS)
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except (OSError, ValueError):
            pass
        return data


def save(updates):
    with _lock:
        data = dict(DEFAULTS)
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except (OSError, ValueError):
            pass
        for k, v in updates.items():
            if k in DEFAULTS:
                data[k] = v
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path())
        return data


def public(settings):
    """Settings safe to send to the panel: keys are masked."""
    out = dict(settings)
    for k in ("elevenlabs_key", "sarvam_key", "deepgram_key"):
        v = out.get(k) or ""
        out[k + "_set"] = bool(v)
        out[k] = ("…" + v[-4:]) if v else ""
    return out
