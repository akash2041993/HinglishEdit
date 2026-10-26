"""Speech-to-text providers. Every provider returns the same word list:
    [{"text": "क्या", "start": 0.12, "end": 0.40, "kind": "word"|"event", "speaker": "speaker_0"}]
Times are seconds on the sequence timeline.
"""
import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

ELEVENLABS_URL = os.environ.get("HINGLISH_ELEVENLABS_URL", "https://api.elevenlabs.io/v1/speech-to-text")
DEEPGRAM_URL = os.environ.get("HINGLISH_DEEPGRAM_URL", "https://api.deepgram.com/v1/listen")


class TranscribeError(Exception):
    pass


class _Multipart:
    """Streams a multipart/form-data body so big audio files are not loaded into memory twice."""

    def __init__(self, fields, file_field, file_path):
        self.boundary = "----HinglishEdit" + uuid.uuid4().hex
        b = self.boundary.encode()
        head = b""
        for k, v in fields:
            head += b"--" + b + b"\r\n"
            head += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
            head += str(v).encode("utf-8") + b"\r\n"
        ctype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        head += b"--" + b + b"\r\n"
        head += (f'Content-Disposition: form-data; name="{file_field}"; '
                 f'filename="{os.path.basename(file_path)}"\r\n').encode()
        head += f"Content-Type: {ctype}\r\n\r\n".encode()
        self.head = head
        self.tail = b"\r\n--" + b + b"--\r\n"
        self.path = file_path
        self.length = len(head) + os.path.getsize(file_path) + len(self.tail)

    def __iter__(self):
        yield self.head
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                yield chunk
        yield self.tail


def _post(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:600]
        if e.code in (401, 403):
            raise TranscribeError(f"The API key was rejected ({e.code}). Check it in Settings. {body}")
        raise TranscribeError(f"Transcription failed (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise TranscribeError(f"Could not reach the transcription service: {e.reason}")


def elevenlabs(audio_path, api_key, language="auto", keyterms=None, timeout=3600):
    if not api_key:
        raise TranscribeError("Add your ElevenLabs API key in Settings first.")
    fields = [
        ("model_id", "scribe_v2"),
        ("timestamps_granularity", "word"),
        ("tag_audio_events", "true"),
        ("no_verbatim", "false"),  # keep "umm", "uh" so we can find and cut them
        ("diarize", "false"),
    ]
    if language and language != "auto":
        fields.append(("language_code", language))
    for t in (keyterms or [])[:100]:
        fields.append(("keyterms", t))
    body = _Multipart(fields, "file", audio_path)
    req = urllib.request.Request(ELEVENLABS_URL, data=iter(body), method="POST", headers={
        "xi-api-key": api_key,
        "Content-Type": "multipart/form-data; boundary=" + body.boundary,
        "Content-Length": str(body.length),
    })
    data = _post(req, timeout)
    return parse_elevenlabs(data), {"provider": "elevenlabs", "language": data.get("language_code"),
                                    "language_probability": data.get("language_probability")}


def parse_elevenlabs(data):
    words = []
    for w in data.get("words") or []:
        t = w.get("type")
        if t == "spacing" or w.get("start") is None or w.get("end") is None:
            continue
        text = (w.get("text") or "").strip()
        if not text:
            continue
        words.append({
            "text": text,
            "start": float(w["start"]),
            "end": float(w["end"]),
            "kind": "event" if t == "audio_event" else "word",
            "speaker": w.get("speaker_id"),
            "conf": w.get("logprob"),
        })
    return words


def deepgram(audio_path, api_key, language="auto", timeout=3600):
    if not api_key:
        raise TranscribeError("Add your Deepgram API key in Settings first.")
    q = {"model": "nova-3", "language": "multi" if language in (None, "", "auto") else language,
         "smart_format": "true", "punctuate": "true", "filler_words": "true"}
    url = DEEPGRAM_URL + "?" + urllib.parse.urlencode(q)
    with open(audio_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": "Token " + api_key, "Content-Type": "audio/mpeg"})
    res = _post(req, timeout)
    words = []
    try:
        alt = res["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError):
        return [], {"provider": "deepgram"}
    for w in alt.get("words", []):
        words.append({"text": w.get("punctuated_word") or w.get("word", ""), "start": float(w["start"]),
                      "end": float(w["end"]), "kind": "word", "speaker": w.get("speaker"),
                      "lang": w.get("language")})
    return words, {"provider": "deepgram"}


def premiere(transcripts):
    """Premiere's own transcription (free). The panel sends, per source clip:
         {"json": "<Transcript.exportToJSON>", "items": [{"start", "end", "in"}]}
       Word times in Premiere's JSON are seconds from the start of the media; we move them onto
       the sequence using each timeline item's position."""
    words = []
    for t in transcripts:
        try:
            data = json.loads(t["json"]) if isinstance(t["json"], str) else t["json"]
        except ValueError:
            raise TranscribeError("Premiere returned a transcript that is not valid JSON.")
        src = []
        for seg in data.get("segments", []):
            for w in seg.get("words", []):
                text = (w.get("text") or "").strip()
                if not text:
                    continue
                st = float(w.get("start", 0))
                en = st + float(w.get("duration", 0))
                if w.get("type") == "punctuation" and src:
                    src[-1]["text"] += text
                    continue
                src.append({"text": text, "start": st, "end": en})
        for it in t.get("items", []):
            s, e, i = float(it["start"]), float(it["end"]), float(it.get("in", 0))
            for w in src:
                if w["start"] >= i - 0.01 and w["end"] <= i + (e - s) + 0.01:
                    words.append({"text": w["text"], "start": s + (w["start"] - i), "end": s + (w["end"] - i),
                                  "kind": "word", "speaker": None})
    words.sort(key=lambda w: w["start"])
    return words, {"provider": "premiere"}
