"""Local HTTP API used by the Premiere panel. Listens on 127.0.0.1 only."""
import json
import os
import re
import socket
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ass_style, captions, config, cuts, fcpxml, jobs, media, render, transcribe, translate
from .fillers import FillerMatcher


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- helpers
def _seq_audio_items(seq):
    """Audio the viewer hears: items on audio tracks that are not muted."""
    tracks = seq.get("audio_tracks", [])
    unmuted = [t for t in tracks if not t.get("muted")] or tracks
    items = []
    for t in unmuted:
        for it in t.get("items", []):
            if it.get("path") and not it.get("disabled"):
                items.append(dict(it, track=t["index"]))
    return items


def _safe_name(name):
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name or "sequence").strip(" .") or "sequence"
    return n[:80]


def _load_analysis(aid):
    if not jobs.exists(aid):
        raise ApiError("This analysis was not found. Click 'Analyze' again.", 404)
    return {
        "seq": jobs.load_json(aid, "seq.json"),
        "words": jobs.load_json(aid, "words.json", []),
        "env": jobs.load_json(aid, "envelope.json", []),
        "probes": jobs.load_json(aid, "probes.json", {}),
        "meta": jobs.load_json(aid, "meta.json", {}),
        "edits": jobs.load_json(aid, "edits.json", {}),
    }


def _matcher(settings):
    return FillerMatcher(settings.get("filler_sounds"), settings.get("filler_ambiguous"),
                         settings.get("filler_phrases"))


def _unmap_time(t, applied):
    """Edited-timeline time -> original time (inverse of cuts.remap_time)."""
    for c in sorted(applied, key=lambda c: c["start"]):
        if t >= c["start"]:
            t += c["end"] - c["start"]
        else:
            break
    return t


# ---------------------------------------------------------------- analysis job
def _analyze(job, seq, provider, language, premiere_transcripts, force):
    settings = config.load()
    seq = dict(seq)
    seq["audio_items"] = _seq_audio_items(seq)
    if not seq["audio_items"] and provider != "premiere":
        raise ApiError("No audio found in this sequence.")

    job.update(0.02, "Checking media files…")
    probes = {}
    all_items = [it for tr in seq.get("video_tracks", []) + seq.get("audio_tracks", []) for it in tr.get("items", [])]
    paths = sorted({it["path"] for it in all_items if it.get("path")})
    for i, p in enumerate(paths):
        if not os.path.isfile(p):
            raise ApiError(f"Media file not found on disk: {p}")
        probes[p] = media.probe(p)
        job.update(0.02 + 0.06 * (i + 1) / max(1, len(paths)))
    for it in seq["audio_items"]:
        it["has_audio"] = bool(probes.get(it["path"], {}).get("audio"))

    fp = jobs.audio_fingerprint(seq, provider, language)
    old = None if force else jobs.find_by_fingerprint(fp)

    aid = job.id
    adir = jobs.analysis_dir(aid)
    job.update(0.1, "Mixing the sequence audio…")
    wav, mp3 = media.mix_sequence_audio(seq, adir, progress=lambda f: job.update(0.1 + 0.2 * f))

    job.update(0.3, "Measuring loudness…")
    env = media.envelope_db(wav)

    meta = {"provider": provider, "language": language, "created": time.time(), "name": seq.get("name")}
    if old:
        job.update(0.35, "Same audio as before: reusing the saved transcript (no new charge)…")
        words = jobs.load_json(old, "words.json", [])
        meta.update(jobs.load_json(old, "meta.json", {}) or {})
        meta["reused_from"] = old
    elif provider == "premiere":
        job.update(0.4, "Reading Premiere's transcript…")
        words, info = transcribe.premiere(premiere_transcripts or [])
        meta.update(info)
    elif provider == "deepgram":
        job.update(0.35, "Transcribing with Deepgram… (long videos take a few minutes)")
        words, info = transcribe.deepgram(mp3, settings.get("deepgram_key", ""), language)
        meta.update(info)
    else:
        job.update(0.35, "Transcribing with ElevenLabs Scribe… (long videos take a few minutes)")
        words, info = transcribe.elevenlabs(mp3, settings.get("elevenlabs_key", ""), language,
                                            settings.get("keyterms") or [])
        meta.update(info)
    if not words:
        raise ApiError("The transcript came back empty. Is there speech in the sequence audio?")

    job.update(0.95, "Saving…")
    jobs.save_json(aid, "seq.json", seq)
    jobs.save_json(aid, "probes.json", probes)
    jobs.save_json(aid, "envelope.json", env)
    jobs.save_json(aid, "meta.json", meta)
    jobs.save_json(aid, "words.json", words)
    jobs.save_json(aid, "edits.json", {})
    jobs.remember_fingerprint(fp, aid)
    try:
        os.remove(mp3)
    except OSError:
        pass
    return {"analysis_id": aid, "words": len([w for w in words if w.get("kind") == "word"]),
            "duration": seq["duration"], "language": meta.get("language"), "reused": bool(old),
            "provider": meta.get("provider")}


def _render_job(job, aid, caps, style, start, end, name):
    a = _load_analysis(aid)
    out_dir = os.path.join(config.output_dir(), aid)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, _safe_name(name) + ".mov")
    n = 1
    while os.path.exists(out):
        n += 1
        out = os.path.join(out_dir, f"{_safe_name(name)} {n}.mov")
    job.update(0.01, "Drawing captions…")
    render.render_overlay(caps, style, a["seq"], start, end, out, progress=lambda f: job.update(f, "Drawing captions…"))
    return {"path": out, "start": start, "end": end}


def _install_ffmpeg_job(job):
    job.update(0.01, "Downloading ffmpeg (about 140 MB)…")
    path = media.install_ffmpeg(progress=lambda f: job.update(f, "Downloading ffmpeg…"))
    return {"path": path}


# ---------------------------------------------------------------- routes
def route(method, path, body):
    settings = config.load()
    if method == "GET" and path == "/health":
        return {"ok": True, "version": config.VERSION, "ffmpeg": media.ffmpeg_info(),
                "fonts": ass_style.PANEL_FONTS, "styles": ass_style.STYLES,
                "settings": config.public(settings)}

    if method == "POST" and path == "/settings":
        allowed = {k: v for k, v in body.items() if k in config.DEFAULTS}
        for k in ("elevenlabs_key", "sarvam_key", "deepgram_key"):
            if k in allowed and (allowed[k] or "").startswith("…"):
                allowed.pop(k)  # masked value sent back unchanged
        return config.public(config.save(allowed))

    if method == "POST" and path == "/ffmpeg/install":
        return jobs.start("ffmpeg", _install_ffmpeg_job).public()

    if method == "GET" and path.startswith("/jobs/"):
        j = jobs.get(path.split("/")[2])
        if not j:
            raise ApiError("Unknown job (the helper may have restarted).", 404)
        return j.public()

    if method == "POST" and path == "/analyze":
        seq = body.get("seq") or {}
        if not seq.get("duration"):
            raise ApiError("The sequence is empty.")
        provider = body.get("provider") or settings.get("provider") or "elevenlabs"
        language = body.get("language") or settings.get("language") or "auto"
        return jobs.start("analyze", _analyze, seq, provider, language, body.get("premiere_transcripts"),
                          bool(body.get("force"))).public()

    if method == "POST" and path == "/transcript":
        a = _load_analysis(body.get("analysis_id"))
        return {"words": a["words"], "meta": a["meta"]}

    if method == "POST" and path == "/cuts/plan":
        a = _load_analysis(body.get("analysis_id"))
        p = cuts.params_for(body.get("intensity", 50), body.get("overrides"))
        plan = cuts.plan_cuts(a["words"], a["seq"]["duration"], a["env"], p, _matcher(settings))
        return {"cuts": plan, "summary": cuts.summarize(plan, a["seq"]["duration"]), "params": p}

    if method == "POST" and path == "/cuts/xml":
        aid = body.get("analysis_id")
        a = _load_analysis(aid)
        applied = sorted(({"start": float(c["start"]), "end": float(c["end"])} for c in body.get("cuts", [])),
                         key=lambda c: c["start"])
        base = body.get("name") or ((a["seq"].get("name") or "Sequence") + " - Hinglish Cut")
        name, n = base, 1
        while name in a["edits"]:
            n += 1
            name = f"{base} {n}"
        xml, warnings, stats = fcpxml.build_xml(a["seq"], applied, a["probes"], name)
        applied = stats.pop("applied_cuts", None) or applied  # frame-exact, matches the XML
        out_dir = os.path.join(config.output_dir(), aid)
        os.makedirs(out_dir, exist_ok=True)
        xml_path = os.path.join(out_dir, _safe_name(name) + ".xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml)
        a["edits"][name] = {"cuts": applied, "xml": xml_path, "created": time.time()}
        jobs.save_json(aid, "edits.json", a["edits"])
        return {"xml_path": xml_path, "name": name, "warnings": warnings, "stats": stats}

    if method == "POST" and path == "/captions/build":
        a = _load_analysis(body.get("analysis_id"))
        style = ass_style.style_options(body.get("style_id"), body.get("style"))
        opts = dict(body.get("options") or {})
        for k in ("max_words", "lines", "max_chars", "uppercase"):
            opts.setdefault(k, style.get(k))
        edit = a["edits"].get(body.get("edit_name") or "")
        applied = edit["cuts"] if edit else None
        caps = captions.build(a["words"], opts, applied, sarvam_key=settings.get("sarvam_key") or None,
                              cache=_SARVAM_CACHE)
        return {"captions": caps, "style": style, "timeline": "edited" if edit else "original"}

    if method == "POST" and path == "/captions/srt":
        aid = body.get("analysis_id")
        _load_analysis(aid)
        caps = captions.apply_edits(body.get("captions") or [])
        out_dir = os.path.join(config.output_dir(), aid)
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, _safe_name(body.get("name") or "captions") + ".srt")
        with open(p, "w", encoding="utf-8-sig") as f:  # BOM helps Premiere read Hindi correctly
            f.write(captions.to_srt(caps))
        return {"path": p}

    if method == "POST" and path == "/captions/preview":
        a = _load_analysis(body.get("analysis_id"))
        style = ass_style.style_options(body.get("style_id"), body.get("style"))
        cap = captions.apply_edits([body.get("caption")])[0]
        seq = a["seq"]
        edit = a["edits"].get(body.get("edit_name") or "")
        if edit:
            # background frame comes from the original timeline
            seq = dict(seq)
            shift = _unmap_time(cap["start"], edit["cuts"]) - cap["start"]
            for tr in seq.get("video_tracks", []):
                tr["items"] = [dict(it, start=it["start"] - shift, end=it["end"] - shift) for it in tr["items"]]
        return {"png": render.preview_png(cap, style, seq)}

    if method == "POST" and path == "/captions/render":
        aid = body.get("analysis_id")
        a = _load_analysis(aid)
        style = ass_style.style_options(body.get("style_id"), body.get("style"))
        caps = captions.apply_edits(body.get("captions") or [])
        if not caps:
            raise ApiError("There are no captions to render.")
        start = float(body.get("start", 0.0))
        end = float(body.get("end") or max(c["end"] for c in caps))
        name = body.get("name") or (style["name"].replace("·", "-") + " captions")
        return jobs.start("render", _render_job, aid, caps, style, start, end, name).public()

    raise ApiError("Not found", 404)


_SARVAM_CACHE = {}


class Handler(BaseHTTPRequestHandler):
    server_version = "HinglishEditHelper/" + config.VERSION

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _handle(self, method):
        try:
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                body = json.loads(raw.decode("utf-8")) if raw else {}
            self._send(200, route(method, self.path.split("?")[0], body))
        except ApiError as e:
            self._send(e.code, {"error": str(e)})
        except (media.MediaError, transcribe.TranscribeError, translate.TranslateError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": f"{e.__class__.__name__}: {e}"})

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        self._handle("POST")

    def log_message(self, fmt, *args):
        if os.environ.get("HINGLISH_DEBUG"):
            super().log_message(fmt, *args)


class _Server6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def serve(port=None):
    port = int(port or os.environ.get("HINGLISH_PORT") or config.DEFAULT_PORT)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    # also answer on IPv6 loopback, in case "localhost" resolves to ::1
    try:
        httpd6 = _Server6(("::1", port), Handler)
        threading.Thread(target=httpd6.serve_forever, daemon=True).start()
    except OSError:
        pass
    print(f"Hinglish Edit helper {config.VERSION} is running on http://127.0.0.1:{port}")
    print("Keep this window open while you use the panel in Premiere. Close it to stop.")
    info = media.ffmpeg_info()
    if not info.get("found"):
        print("ffmpeg is not installed yet - the panel will offer to install it.")
    httpd.serve_forever()
