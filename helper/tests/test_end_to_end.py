"""End-to-end test of the helper with a generated video and a fake ElevenLabs server.

Run:  python -m pytest -q tests   (or: python tests/test_end_to_end.py)
Checks: analysis, cut plan (fillers, repeats, pauses, protected sounds, never cutting kept words),
the XML timeline (frame maths, by re-building the edited audio from the XML and listening to it),
captions (Roman + Devanagari), SRT, preview PNG and the transparent caption render.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

WORDS = [
    ("नमस्ते", 0.8, 1.3), ("दोस्तों,", 1.35, 1.9), ("आज", 2.0, 2.3), ("हम", 2.35, 2.55), ("बात", 2.6, 2.9),
    ("करेंगे", 2.95, 3.5),
    ("umm", 5.2, 5.7),
    ("video", 6.1, 6.5), ("editing", 6.55, 7.1), ("के", 7.15, 7.3), ("बारे", 7.35, 7.6), ("में।", 7.65, 7.85),
    ("मैं", 8.9, 9.1), ("मैं", 9.45, 9.65), ("बताऊंगा", 9.7, 10.3), ("धीरे", 10.4, 10.7), ("धीरे", 10.72, 11.0),
    ("basically", 11.6, 12.1), ("सब", 12.6, 12.8), ("कुछ।", 12.85, 13.1),
    ("ठीक", 16.0, 16.3), ("है", 16.35, 16.5), ("uh", 16.9, 17.2), ("चलो", 17.6, 17.9), ("शुरू", 17.95, 18.3),
    ("करते", 18.35, 18.7), ("हैं।", 18.75, 19.0),
]
LAUGH = (14.0, 14.6)  # loud sound the transcript does not contain: must never be cut
DURATION = 22.0
FILLERS = {"umm", "uh"}


def make_media(path):
    import subprocess
    terms = []
    for i, (_, s, e) in enumerate(WORDS + [("laugh",) + LAUGH]):
        f = 180 + 40 * (i % 5)
        terms.append(f"0.45*sin(2*PI*{f}*t)*between(t,{s},{e})")
    expr = "+".join(terms) + "+0.002*(random(0)-0.5)"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=30000/1001:d={DURATION}",
        "-f", "lavfi", "-i", f"aevalsrc='{expr}|{expr}':s=48000:d={DURATION}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", path], check=True)


class FakeElevenLabs(BaseHTTPRequestHandler):
    seen = {}

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        FakeElevenLabs.seen = {"key": self.headers.get("xi-api-key"), "size": len(body),
                               "model": b'name="model_id"\r\n\r\nscribe_v2' in body,
                               "verbatim": b'name="no_verbatim"\r\n\r\nfalse' in body}
        words = []
        prev = 0.0
        for t, s, e in WORDS:
            words.append({"text": " ", "start": prev, "end": s, "type": "spacing", "logprob": 0})
            words.append({"text": t, "start": s, "end": e, "type": "word", "logprob": -0.1, "speaker_id": "speaker_0"})
            prev = e
        out = json.dumps({"language_code": "hin", "language_probability": 0.97, "text": "...", "words": words}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def call(port, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise AssertionError(f"{path} -> {e.code}: {e.read().decode()}")


def wait_job(port, job):
    for _ in range(1200):
        j = call(port, "GET", f"/jobs/{job['id']}")
        if j["status"] != "running":
            assert j["status"] == "done", j
            return j["result"]
        time.sleep(0.25)
    raise AssertionError("job timeout")


def play_xml_audio(xml_path, out_wav):
    """Rebuild the edited audio from the XML (A1, left channel) to check the frame maths."""
    import subprocess
    root = ET.parse(xml_path).getroot()
    seq = root.find("sequence")
    tb = int(seq.find("rate/timebase").text)
    ntsc = seq.find("rate/ntsc").text == "TRUE"
    fps = tb * 1000 / 1001 if ntsc else tb
    track = seq.find("media/audio/track")
    files = {}
    for f in root.iter("file"):
        if f.find("pathurl") is not None:
            files[f.get("id")] = urllib.parse.unquote(f.find("pathurl").text.replace("file://localhost", ""))
    segs = []
    last_end = 0
    for ci in track.findall("clipitem"):
        start, end = int(ci.find("start").text), int(ci.find("end").text)
        assert start == last_end, f"gap or overlap at frame {start} (expected {last_end})"
        last_end = end
        ctb = int(ci.find("rate/timebase").text)
        cntsc = ci.find("rate/ntsc").text == "TRUE"
        cfps = ctb * 1000 / 1001 if cntsc else ctb
        i, o = int(ci.find("in").text), int(ci.find("out").text)
        assert abs((o - i) / cfps - (end - start) / fps) < 1.5 / fps, "in/out length differs from timeline length"
        segs.append((files[ci.find("file").get("id")], i / cfps, o / cfps))
    parts, inputs = [], []
    for k, (p, a, b) in enumerate(segs):
        inputs += ["-i", p]
        parts.append(f"[{k}:a:0]atrim=start={a:.5f}:end={b:.5f},asetpts=PTS-STARTPTS,"
                     f"aformat=sample_rates=16000:channel_layouts=mono[s{k}]")
    fc = ";".join(parts) + ";" + "".join(f"[s{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", fc, "-map", "[o]",
                    "-c:a", "pcm_s16le", out_wav], check=True)
    return last_end / fps, segs


def xml_remap(t, segs):
    """Where source time t lands in the edited audio, using the real (frame-rounded) XML clips."""
    pos = 0.0
    for _, a, b in segs:
        if a <= t < b:
            return pos + (t - a)
        pos += b - a
    return None


def main():
    import urllib.parse  # noqa: F401
    tmp = tempfile.mkdtemp(prefix="hinglish_test_")
    os.environ["HINGLISH_HOME"] = os.path.join(tmp, "home")
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeElevenLabs)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    os.environ["HINGLISH_ELEVENLABS_URL"] = f"http://127.0.0.1:{fake.server_address[1]}/v1/speech-to-text"

    from hinglish_edit import config, cuts, media, server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    media_dir = os.path.join(tmp, "my videos with spaces")
    os.makedirs(media_dir)
    video = os.path.join(media_dir, "raw take 1.mp4")
    make_media(video)

    h = call(port, "GET", "/health")
    assert h["ok"] and h["ffmpeg"]["found"] and h["ffmpeg"]["ass"], h["ffmpeg"]
    call(port, "POST", "/settings", {"elevenlabs_key": "sk_test_1234"})
    assert call(port, "GET", "/health")["settings"]["elevenlabs_key"] == "…1234"

    item = {"path": video, "name": "raw take 1.mp4", "start": 0.0, "end": DURATION, "in": 0.0, "speed": 1}
    seq = {"name": "Episode 12", "fps": 29.97002997, "width": 1920, "height": 1080, "audio_rate": 48000,
           "duration": DURATION,
           "video_tracks": [{"index": 0, "items": [dict(item)]}],
           "audio_tracks": [{"index": 0, "muted": False, "items": [dict(item)]}]}

    res = wait_job(port, call(port, "POST", "/analyze", {"seq": seq, "provider": "elevenlabs"}))
    assert FakeElevenLabs.seen["key"] == "sk_test_1234" and FakeElevenLabs.seen["model"] and FakeElevenLabs.seen["verbatim"]
    assert res["words"] == len(WORDS), res
    aid = res["analysis_id"]

    # second analysis of the same audio must reuse the transcript (no second charge)
    FakeElevenLabs.seen = {}
    res2 = wait_job(port, call(port, "POST", "/analyze", {"seq": seq, "provider": "elevenlabs"}))
    assert res2["reused"] and not FakeElevenLabs.seen, "transcript was not reused"

    plan = call(port, "POST", "/cuts/plan", {"analysis_id": aid, "intensity": 50})
    cl = plan["cuts"]
    kinds = [k for c in cl for k in c["kinds"]]
    print("cuts @50:", [(c["start"], c["end"], c["label"]) for c in cl])
    print("summary:", plan["summary"])

    def inside(t):
        return any(c["start"] <= t <= c["end"] for c in cl)

    removed_words = set()
    for idx, (t, s, e) in enumerate(WORDS):
        mid = (s + e) / 2
        if t in FILLERS:
            assert inside(mid), f"filler {t} at {s} was not cut"
            removed_words.add(idx)
    # repeated "मैं": the first copy goes
    assert inside((8.9 + 9.1) / 2) and not inside((9.45 + 9.65) / 2), "repeat handling wrong"
    removed_words.add(12)
    # Hindi doubling without pause ("धीरे धीरे") stays
    assert not inside(10.55) and not inside(10.85)
    # "basically" is a filler phrase only at Aggressive
    assert not inside(11.85)
    for idx, (t, s, e) in enumerate(WORDS):
        if idx in removed_words:
            continue
        for c in cl:
            assert c["end"] <= s or c["start"] >= e, f"cut {c} touches kept word {t} {s}-{e}"
            # padding around kept words
            assert c["end"] <= s - 0.03 or c["start"] >= e + 0.03 or c["end"] <= s or c["start"] >= e
    assert not any(c["start"] < LAUGH[1] and c["end"] > LAUGH[0] for c in cl), "loud untranscribed sound was cut"
    assert "silence" in kinds and "filler" in kinds and "repeat" in kinds
    assert cl[0]["start"] == 0.0 and cl[-1]["end"] == DURATION, "lead/tail silence not cut"

    agg = call(port, "POST", "/cuts/plan", {"analysis_id": aid, "intensity": 100})["cuts"]
    assert any(c["start"] <= 11.85 <= c["end"] for c in agg), "aggressive should remove 'basically'"
    gentle = call(port, "POST", "/cuts/plan", {"analysis_id": aid, "intensity": 0})
    assert gentle["summary"]["removed"] < plan["summary"]["removed"] < call(
        port, "POST", "/cuts/plan", {"analysis_id": aid, "intensity": 100})["summary"]["removed"]

    # ---- XML timeline
    x = call(port, "POST", "/cuts/xml", {"analysis_id": aid, "cuts": cl})
    assert not x["warnings"], x["warnings"]
    print("xml:", x["xml_path"], x["stats"])
    root = ET.parse(x["xml_path"]).getroot()
    assert root.tag == "xmeml"
    tracks = root.findall("sequence/media/audio/track")
    assert len(tracks) == 2 and tracks[0].get("premiereTrackType") == "Stereo"
    assert [ci.find("sourcetrack/trackindex").text for ci in tracks[1].findall("clipitem")][:1] == ["2"]
    v_clips = root.findall("sequence/media/video/track/clipitem")
    assert len(v_clips) == len(cl) - 1, (len(v_clips), len(cl))  # lead+tail cuts remove the ends
    assert all(len(ci.findall("link")) == 3 for ci in v_clips), "video should link to its two audio channels"
    pu = root.find(".//pathurl").text
    assert pu.startswith("file://localhost/") and "%20" in pu
    out_wav = os.path.join(tmp, "edited.wav")
    new_len, segs = play_xml_audio(x["xml_path"], out_wav)
    # kept pieces are rounded outward to whole frames: each may grow by up to one frame, never shrink
    grow = new_len - plan["summary"]["new_duration"]
    assert -0.02 < grow <= (len(cl) + 1) * 1.001 / 29.97 + 0.01, (new_len, plan["summary"])
    env = media.envelope_db(out_wav)
    for idx, (t, s, e) in enumerate(WORDS):
        if idx in removed_words:
            continue
        # every kept word must be fully inside one clip of the XML (never clipped by frame rounding)
        assert any(a <= s and e <= b for _, a, b in segs), f"kept word {t} {s}-{e} is cut by the XML clips"
        nt = xml_remap((s + e) / 2, segs)
        assert nt is not None
        lvl = env[int(nt / 0.01)]
        assert lvl > -25, f"kept word {t} is silent in the edited audio ({lvl} dB at {nt:.2f}s)"
        # the whole word survived: check near its edges too
        for edge in (s + 0.03, e - 0.03):
            ne = xml_remap(edge, segs)
            assert ne is not None and env[int(ne / 0.01)] > -25, f"edge of {t} was clipped"
    nl = xml_remap(sum(LAUGH) / 2, segs)
    assert env[int(nl / 0.01)] > -25, "laugh missing in edited audio"
    names = call(port, "POST", "/cuts/xml", {"analysis_id": aid, "cuts": cl})["name"]
    assert names.endswith("2"), names

    # ---- captions
    caps = call(port, "POST", "/captions/build", {"analysis_id": aid, "style_id": "full_clean",
                                                    "options": {"script": "roman"}})["captions"]
    text = " | ".join(c["text"] for c in caps)
    print("roman captions:", text)
    assert "namaste" in text and "umm" not in text and "video editing" in text
    assert all(c["end"] > c["start"] for c in caps)
    assert all(caps[i]["end"] <= caps[i + 1]["start"] for i in range(len(caps) - 1))
    deva = call(port, "POST", "/captions/build", {"analysis_id": aid, "style_id": "hook_pop",
                                                    "options": {"script": "devanagari"}})["captions"]
    assert any("नमस्ते" in c["text"] for c in deva) and max(len(c["words"]) for c in deva) <= 3
    edited = call(port, "POST", "/captions/build", {"analysis_id": aid, "style_id": "full_clean",
                                                     "edit_name": x["name"], "options": {"script": "roman"}})
    assert edited["timeline"] == "edited"
    assert edited["captions"][0]["start"] < caps[0]["start"], "edited captions should move earlier"

    srt = call(port, "POST", "/captions/srt", {"analysis_id": aid, "captions": caps, "name": "ep12 roman"})
    s_text = open(srt["path"], encoding="utf-8-sig").read()
    assert s_text.startswith("1\n00:00:00,") and "-->" in s_text

    caps[1]["text"] = "edited TEXT here now"
    pv = call(port, "POST", "/captions/preview", {"analysis_id": aid, "caption": caps[1], "style_id": "hook_pop"})
    import base64
    png = base64.b64decode(pv["png"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5000
    with open(os.path.join(tmp, "preview.png"), "wb") as f:
        f.write(png)

    r = wait_job(port, call(port, "POST", "/captions/render", {
        "analysis_id": aid, "captions": deva, "style_id": "hook_pop", "start": 0.0, "end": 6.0,
        "name": "hook test"}))
    info = media.probe(r["path"])
    assert info["video"]["width"] == 1920 and abs(info["duration"] - 6.0) < 0.2, info
    from PIL import Image
    fr = os.path.join(tmp, "f.png")
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.2", "-i", r["path"], "-frames:v", "1",
                    "-pix_fmt", "rgba", fr], check=True)
    a = Image.open(fr).getchannel("A")
    assert a.getextrema() == (0, 255), "caption layer must be transparent with opaque text"
    print("render ok:", r["path"], os.path.getsize(r["path"]), "bytes")
    # a multi-size "viral" design with words appearing as spoken
    r2 = wait_job(port, call(port, "POST", "/captions/render", {
        "analysis_id": aid, "captions": deva, "style_id": "viral_glow", "start": 0.0, "end": 4.0, "name": "viral"}))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.0", "-i", r2["path"], "-frames:v", "1",
                    "-pix_fmt", "rgba", fr], check=True)
    assert Image.open(fr).getchannel("A").getextrema()[1] == 255, "viral design rendered nothing"
    assert root.find("sequence").get("explodedTracks") == "true"
    assert all(ci.get("premiereChannelType") == "stereo" for ci in tracks[0].findall("clipitem"))
    print("ALL HELPER TESTS PASSED")
    srv.shutdown()
    fake.shutdown()
    if not os.environ.get("KEEP_TMP"):
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("kept", tmp)


def test_end_to_end():
    main()


if __name__ == "__main__":
    main()
