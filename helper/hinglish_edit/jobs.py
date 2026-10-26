"""Long tasks (transcription, rendering) run in a background thread; the panel polls their progress.
Analysis results are saved on disk so they survive a helper restart and are never paid for twice."""
import hashlib
import json
import os
import threading
import time
import traceback
import uuid

from .config import jobs_dir

_jobs = {}
_lock = threading.Lock()


class Job:
    def __init__(self, kind):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.kind = kind
        self.status = "running"
        self.progress = 0.0
        self.message = "Starting…"
        self.result = None
        self.error = None

    def update(self, progress=None, message=None):
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self.message = message

    def public(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "progress": round(self.progress, 3),
                "message": self.message, "result": self.result, "error": self.error}


def start(kind, fn, *args, **kwargs):
    job = Job(kind)
    with _lock:
        _jobs[job.id] = job

    def runner():
        try:
            job.result = fn(job, *args, **kwargs)
            job.status = "done"
            job.progress = 1.0
            job.message = "Done"
        except Exception as e:  # noqa: BLE001 - every error goes back to the panel
            job.status = "error"
            job.error = str(e) or e.__class__.__name__
            job.message = "Failed"
            traceback.print_exc()

    threading.Thread(target=runner, daemon=True).start()
    return job


def get(job_id):
    with _lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------- saved analyses
def analysis_dir(aid):
    if not aid or any(c in aid for c in "/\\.:"):
        raise ValueError("Bad analysis id")
    d = os.path.join(jobs_dir(), aid)
    os.makedirs(d, exist_ok=True)
    return d


def save_json(aid, name, data):
    p = os.path.join(analysis_dir(aid), name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


def load_json(aid, name, default=None):
    p = os.path.join(analysis_dir(aid), name)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def exists(aid):
    return bool(aid) and os.path.isfile(os.path.join(jobs_dir(), aid, "words.json"))


def audio_fingerprint(seq, provider, language):
    """Same audio + same provider -> reuse the old transcript (no second charge)."""
    parts = [provider, language or ""]
    for it in sorted(seq.get("audio_items", []), key=lambda i: (i["start"], i.get("path", ""))):
        try:
            st = os.stat(it["path"])
            sig = f"{st.st_size}:{int(st.st_mtime)}"
        except OSError:
            sig = "?"
        parts.append(f"{it.get('path')}|{sig}|{it['start']:.3f}|{it['end']:.3f}|{float(it.get('in', 0)):.3f}|"
                     f"{bool(it.get('disabled'))}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()


def find_by_fingerprint(fp):
    idx = os.path.join(jobs_dir(), "index.json")
    try:
        with open(idx, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    aid = data.get(fp)
    return aid if exists(aid) else None


def remember_fingerprint(fp, aid):
    idx = os.path.join(jobs_dir(), "index.json")
    with _lock:
        try:
            with open(idx, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data[fp] = aid
        with open(idx, "w", encoding="utf-8") as f:
            json.dump(data, f)
