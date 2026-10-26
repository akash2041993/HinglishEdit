"""Write the edited timeline as a Final Cut Pro 7 XML (xmeml) file, which Premiere imports as a new
sequence. This is the same route desktop "silence remover" tools use to hand a timeline to
Premiere: the original sequence is never changed.

Every clip on every track is cut at the same places (like a razor through all tracks), and the
gaps are closed.
"""
import os
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

from .cuts import keep_ranges


class Rate:
    def __init__(self, fps):
        fps = float(fps or 30.0)
        tb = int(round(fps))
        self.ntsc = abs(fps - tb) > 0.005
        self.timebase = tb
        self.fps = tb * 1000.0 / 1001.0 if self.ntsc else float(tb)

    def frames(self, seconds):
        return int(round(float(seconds) * self.fps))

    def xml(self, parent):
        r = ET.SubElement(parent, "rate")
        ET.SubElement(r, "timebase").text = str(self.timebase)
        ET.SubElement(r, "ntsc").text = "TRUE" if self.ntsc else "FALSE"
        return r


def _sub(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def pathurl(path):
    if path.startswith("\\\\") or path.startswith("//"):  # network share: \\NAS\share\x.mov
        rest = path.replace("\\", "/").lstrip("/")
        return "file://" + urllib.parse.quote(rest, safe="/")
    p = os.path.abspath(path) if not (len(path) > 2 and path[1] == ":") else path
    p = p.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        return "file://localhost/" + urllib.parse.quote(p[0] + ":", safe="").replace("%3A", "%3a") + \
               urllib.parse.quote(p[2:], safe="/")
    return "file://localhost" + urllib.parse.quote(p, safe="/")


def _timecode_frame(tc, rate):
    """'01:00:00:00' (or ';' drop-frame) -> frame number."""
    if not tc:
        return 0, "00:00:00:00", "NDF"
    drop = ";" in tc
    parts = [int(x) for x in tc.replace(";", ":").replace(".", ":").split(":") if x.isdigit()]
    if len(parts) != 4:
        return 0, "00:00:00:00", "NDF"
    h, m, s, f = parts
    tb = rate.timebase
    total = (h * 3600 + m * 60 + s) * tb + f
    if drop and tb in (30, 60):
        d = 2 if tb == 30 else 4
        total_min = h * 60 + m
        total -= d * (total_min - total_min // 10)
    return total, tc, "DF" if drop else "NDF"


def _timecode(parent, rate, tc=None):
    frame, string, fmt = _timecode_frame(tc, rate)
    t = _sub(parent, "timecode")
    rate.xml(t)
    _sub(t, "string", string)
    _sub(t, "frame", frame)
    _sub(t, "displayformat", fmt)
    return t


def build_xml(seq, cuts, probes, name):
    """seq: sequence description from the panel. probes: {path: media.probe(path)}.
    Returns (xml_text, warnings, stats)."""
    srate = Rate(seq.get("fps") or 30)
    width, height = int(seq.get("width") or 1920), int(seq.get("height") or 1080)
    duration = float(seq["duration"])
    keeps = []
    for a, b in keep_ranges(cuts, duration):
        fa, fb = srate.frames(a), srate.frames(b)
        if fb > fa:
            keeps.append((fa, fb))
    # where each kept range starts on the new timeline
    new_pos, pos = [], 0
    for fa, fb in keeps:
        new_pos.append(pos)
        pos += fb - fa
    total_frames = pos
    warnings = []

    root = ET.Element("xmeml", version="4")
    sq = _sub(root, "sequence", id="sequence-1", explodedTracks="true")
    _sub(sq, "uuid", str(uuid.uuid4()))
    _sub(sq, "duration", total_frames)
    srate.xml(sq)
    _sub(sq, "name", name)
    media = _sub(sq, "media")
    video = _sub(media, "video")
    fmt = _sub(video, "format")
    sc = _sub(fmt, "samplecharacteristics")
    srate.xml(sc)
    _sub(sc, "width", width)
    _sub(sc, "height", height)
    _sub(sc, "anamorphic", "FALSE")
    _sub(sc, "pixelaspectratio", "square")
    _sub(sc, "fielddominance", "none")
    _sub(sc, "colordepth", "24")

    file_ids, file_written = {}, set()
    clip_n = [0]
    groups = {}  # (path, start_frame, in_frame, keep_index) -> list of clipitem refs for linking

    def file_el(parent, path):
        fid = file_ids.setdefault(path, "file-%d" % (len(file_ids) + 1))
        if fid in file_written:
            _sub(parent, "file", id=fid)
            return
        file_written.add(fid)
        info = probes.get(path) or {}
        v = info.get("video")
        frate = Rate(v["fps"]) if v and v.get("fps") else srate
        f = _sub(parent, "file", id=fid)
        _sub(f, "name", os.path.basename(path))
        _sub(f, "pathurl", pathurl(path))
        frate.xml(f)
        _sub(f, "duration", frate.frames(info.get("duration") or 0))
        _timecode(f, frate, info.get("timecode"))
        m = _sub(f, "media")
        if v:
            vv = _sub(m, "video")
            vsc = _sub(vv, "samplecharacteristics")
            frate.xml(vsc)
            _sub(vsc, "width", v.get("width") or width)
            _sub(vsc, "height", v.get("height") or height)
            _sub(vsc, "anamorphic", "FALSE")
            _sub(vsc, "pixelaspectratio", "square")
            _sub(vsc, "fielddominance", "none")
        for a in (info.get("audio") or [])[:1]:
            aa = _sub(m, "audio")
            asc = _sub(aa, "samplecharacteristics")
            _sub(asc, "depth", 16)
            _sub(asc, "samplerate", a.get("sample_rate") or 48000)
            _sub(aa, "channelcount", a.get("channels") or 2)

    def pieces(item):
        """Split one timeline item by the kept ranges."""
        s, e = srate.frames(item["start"]), srate.frames(item["end"])
        out = []
        for k, (fa, fb) in enumerate(keeps):
            a, b = max(s, fa), min(e, fb)
            if b > a:
                out.append((k, a, b, new_pos[k] + (a - fa)))
        return s, out

    def usable(item, kind):
        if not item.get("path"):
            warnings.append(f"Skipped '{item.get('name', 'item')}' on {kind}: it is not a media file "
                            f"(graphics, nested sequences and adjustment layers are not copied).")
            return False
        if abs(float(item.get("speed") or 1.0) - 1.0) > 0.001:
            warnings.append(f"Skipped '{item.get('name')}': speed changes are not supported yet.")
            return False
        return True

    def clipitem(track_el, item, k, a, b, newstart, s_frame, mediatype, channel=None, chtype=None):
        info = probes.get(item["path"]) or {}
        v = info.get("video")
        crate = Rate(v["fps"]) if (v and v.get("fps")) else srate
        clip_n[0] += 1
        cid = "clipitem-%d" % clip_n[0]
        ci = _sub(track_el, "clipitem", id=cid, **({"premiereChannelType": chtype} if chtype else {}))
        _sub(ci, "name", item.get("name") or os.path.basename(item["path"]))
        _sub(ci, "enabled", "FALSE" if item.get("disabled") else "TRUE")
        _sub(ci, "duration", crate.frames(info.get("duration") or 0))
        crate.xml(ci)
        _sub(ci, "start", newstart)
        _sub(ci, "end", newstart + (b - a))
        src_in = float(item.get("in", 0.0)) + (a - s_frame) / srate.fps
        src_out = src_in + (b - a) / srate.fps
        _sub(ci, "in", crate.frames(src_in))
        _sub(ci, "out", crate.frames(src_out))
        file_el(ci, item["path"])
        if mediatype == "audio":
            st = _sub(ci, "sourcetrack")
            _sub(st, "mediatype", "audio")
            _sub(st, "trackindex", channel or 1)
        key = (item["path"], s_frame, round(float(item.get("in", 0.0)), 3), k)
        groups.setdefault(key, []).append({"el": ci, "id": cid, "mediatype": mediatype})
        return ci

    # ---- video tracks (V1 first)
    vt_count = 0
    for tr in sorted(seq.get("video_tracks", []), key=lambda t: t["index"]):
        vt_count += 1
        t = _sub(video, "track")
        n = 0
        for item in sorted(tr.get("items", []), key=lambda i: i["start"]):
            if not usable(item, "V%d" % (tr["index"] + 1)):
                continue
            s_frame, ps = pieces(item)
            for k, a, b, ns in ps:
                clipitem(t, item, k, a, b, ns, s_frame, "video")
                n += 1
        _sub(t, "enabled", "TRUE")
        _sub(t, "locked", "FALSE")

    # ---- audio
    audio = _sub(media, "audio")
    _sub(audio, "numOutputChannels", 2)
    afmt = _sub(audio, "format")
    asc = _sub(afmt, "samplecharacteristics")
    _sub(asc, "depth", 16)
    _sub(asc, "samplerate", int(seq.get("audio_rate") or 48000))
    outs = _sub(audio, "outputs")
    for ch in (1, 2):
        g = _sub(outs, "group")
        _sub(g, "index", ch)
        _sub(g, "numchannels", 1)
        _sub(g, "downmix", 0)
        c = _sub(g, "channel")
        _sub(c, "index", ch)

    # Items that appear on several audio tracks at the same place are one clip split into mono
    # channels (common for cameras): give each track the next channel number.
    atracks = sorted(seq.get("audio_tracks", []), key=lambda t: t["index"])
    seen_channel = {}
    track_layout = []
    for tr in atracks:
        layout = "stereo"
        chans = {}
        for item in tr.get("items", []):
            if not item.get("path"):
                continue
            key = (item["path"], round(float(item["start"]), 3), round(float(item.get("in", 0)), 3))
            nxt = seen_channel.get(key, 0) + 1
            seen_channel[key] = nxt
            chans[id(item)] = nxt
            info = probes.get(item["path"]) or {}
            nch = ((info.get("audio") or [{}])[0]).get("channels") or 2
            if nch == 1 or nxt > 1:
                layout = "mono"
        if any(v > 1 for v in chans.values()):
            layout = "mono"
        track_layout.append((tr, layout, chans))
    # a track whose items are the first channel of a split clip is mono too
    for i, (tr, layout, chans) in enumerate(track_layout):
        for item in tr.get("items", []):
            key = (item.get("path"), round(float(item.get("start", 0)), 3), round(float(item.get("in", 0)), 3))
            if seen_channel.get(key, 1) > 1:
                track_layout[i] = (tr, "mono", chans)
                break

    a_xml_index = 0
    for tr, layout, chans in track_layout:
        explode = [1, 2] if layout == "stereo" else [None]
        for ex_i, ch_fixed in enumerate(explode):
            a_xml_index += 1
            attrs = {}
            if layout == "stereo":
                attrs = {"currentExplodedTrackIndex": ex_i, "totalExplodedTrackCount": 2,
                         "premiereTrackType": "Stereo"}
            else:
                attrs = {"currentExplodedTrackIndex": 0, "totalExplodedTrackCount": 1,
                         "premiereTrackType": "Mono"}
            t = _sub(audio, "track", **attrs)
            for item in sorted(tr.get("items", []), key=lambda i: i["start"]):
                if not usable(item, "A%d" % (tr["index"] + 1)):
                    continue
                channel = ch_fixed if ch_fixed else chans.get(id(item), 1)
                s_frame, ps = pieces(item)
                for k, a, b, ns in ps:
                    clipitem(t, item, k, a, b, ns, s_frame, "audio", channel, layout)
            _sub(t, "enabled", "TRUE")
            _sub(t, "locked", "FALSE")
            _sub(t, "outputchannelindex", 1 if (layout == "mono" or ex_i == 0) else 2)

    # ---- links: keep video and its audio linked, like in the original
    where = {}
    for parent in (video, audio):
        for ti, trk in enumerate(parent.findall("track"), 1):
            for ci_i, ci in enumerate(trk.findall("clipitem"), 1):
                where[id(ci)] = (ti, ci_i)

    def track_and_index(el):
        return where.get(id(el), (1, 1))

    for members in groups.values():
        if len(members) < 2:
            continue
        positions = [track_and_index(m["el"]) for m in members]
        for m in members:
            for other, (ti, ci_i) in zip(members, positions):
                ln = _sub(m["el"], "link")
                _sub(ln, "linkclipref", other["id"])
                _sub(ln, "mediatype", other["mediatype"])
                _sub(ln, "trackindex", ti)
                _sub(ln, "clipindex", ci_i)
                if other["mediatype"] == "audio":
                    _sub(ln, "groupindex", 1)

    _timecode(sq, srate, None)
    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode") + "\n"
    stats = {"frames": total_frames, "seconds": round(total_frames / srate.fps, 3),
             "clipitems": clip_n[0], "video_tracks": vt_count, "audio_tracks": a_xml_index}
    return xml, warnings, stats
