// @ts-check
/* Everything that talks to Premiere Pro (UXP "premierepro" module, Premiere 25.6+). */

const ppro = /** @type {PPro.Module} */ (require("premierepro"));
const C = ppro.Constants;
const TICKS_PER_SECOND = 254016000000;

/** @param {number} s */
function tt(s) {
  return ppro.TickTime.createWithSeconds(Math.max(0, s));
}

async function getProject() {
  const project = await ppro.Project.getActiveProject();
  if (!project) throw new Error("Open a project in Premiere first.");
  return project;
}

async function getSequence() {
  const project = await getProject();
  const seq = await project.getActiveSequence();
  if (!seq) throw new Error("Open a sequence in the timeline first.");
  return { project, seq };
}

/**
 * Run edits as one undoable step.
 * @param {PPro.Project} project
 * @param {string} label
 * @param {() => PPro.Action[]} makeActions  called inside lockedAccess
 */
function transact(project, label, makeActions) {
  let ok = false;
  /** @type {any} */
  let err = null;
  project.lockedAccess(() => {
    try {
      const actions = makeActions();
      if (!actions.length) {
        ok = true;
        return;
      }
      ok = project.executeTransaction((/** @type {PPro.CompoundAction} */ compound) => {
        for (const a of actions) compound.addAction(a);
      }, label);
    } catch (e) {
      err = e;
    }
  });
  if (err) throw err;
  if (!ok) throw new Error(`Premiere could not complete: ${label}`);
  return ok;
}

/** @param {any} item */
async function clipPath(item) {
  try {
    const pi = await item.getProjectItem();
    const clip = ppro.ClipProjectItem.cast(pi);
    if (!clip) return { path: "", clip: null };
    if (await clip.isSequence()) return { path: "", clip: null };
    const path = await clip.getMediaFilePath();
    return { path: path || "", clip };
  } catch (e) {
    return { path: "", clip: null };
  }
}

/** @param {any} item */
async function describeItem(item) {
  const { path } = await clipPath(item);
  let speed = 1;
  try {
    speed = Number(await item.getSpeed()) || 1;
    if (speed > 10) speed = speed / 100; // some versions report percent
  } catch (e) { /* keep 1 */ }
  return {
    path,
    name: await item.getName(),
    start: (await item.getStartTime()).seconds,
    end: (await item.getEndTime()).seconds,
    in: (await item.getInPoint()).seconds,
    disabled: await item.isDisabled(),
    speed,
  };
}

/** Everything the helper needs to know about the active sequence. */
async function describeSequence() {
  const { project, seq } = await getSequence();
  const tb = Number(await seq.getTimebase());
  const fps = tb > 0 ? TICKS_PER_SECOND / tb : 30;
  let width = 1920, height = 1080, audioRate = 48000;
  try {
    const size = await seq.getFrameSize();
    if (size && size.width) { width = Math.round(size.width); height = Math.round(size.height); }
  } catch (e) { /* defaults */ }
  try {
    const settings = await seq.getSettings();
    const ar = await settings.getAudioSampleRate();
    if (ar && ar.value > 1000) audioRate = Math.round(ar.value);
  } catch (e) { /* default 48 kHz */ }

  const videoTracks = [];
  const vCount = await seq.getVideoTrackCount();
  for (let i = 0; i < vCount; i++) {
    const tr = await seq.getVideoTrack(i);
    const items = await tr.getTrackItems(C.TrackItemType.CLIP, false);
    const out = [];
    for (const it of items) out.push(await describeItem(it));
    videoTracks.push({ index: i, muted: await tr.isMuted(), items: out });
  }
  const audioTracks = [];
  const aCount = await seq.getAudioTrackCount();
  for (let i = 0; i < aCount; i++) {
    const tr = await seq.getAudioTrack(i);
    const items = await tr.getTrackItems(C.TrackItemType.CLIP, false);
    const out = [];
    for (const it of items) out.push(await describeItem(it));
    audioTracks.push({ index: i, muted: await tr.isMuted(), items: out });
  }
  let duration = (await seq.getEndTime()).seconds;
  for (const t of videoTracks.concat(audioTracks)) for (const it of t.items) duration = Math.max(duration, it.end);
  return {
    project, seq,
    info: {
      name: seq.name, guid: seq.guid.toString(), fps, width, height, audio_rate: audioRate, duration,
      video_tracks: videoTracks, audio_tracks: audioTracks,
    },
  };
}

/** @param {number} seconds */
async function jumpTo(seconds) {
  const { seq } = await getSequence();
  await seq.setPlayerPosition(tt(seconds));
}

async function playheadSeconds() {
  const { seq } = await getSequence();
  return (await seq.getPlayerPosition()).seconds;
}

/** Sequence In/Out points (seconds), or null when not set. */
async function inOutRange() {
  const { seq } = await getSequence();
  try {
    const a = (await seq.getInPoint()).seconds;
    const b = (await seq.getOutPoint()).seconds;
    const end = (await seq.getEndTime()).seconds;
    if (b > a && !(a <= 0.001 && Math.abs(b - end) < 0.05)) return { start: a, end: b };
  } catch (e) { /* not set */ }
  return null;
}

// ---------------------------------------------------------------- markers
const MARK = "✂ ";

/** @param {{start:number,end:number,label:string,text?:string}[]} cuts */
async function addCutMarkers(cuts) {
  const { project, seq } = await getSequence();
  const markers = await ppro.Markers.getMarkers(seq);
  const type = (/** @type {any} */ (ppro.Marker)).MARKER_TYPE_COMMENT || "Comment";
  transact(project, "Hinglish Edit: mark cuts", () =>
    cuts.map((c) => markers.createAddMarkerAction(
      MARK + c.label, type, tt(c.start), tt(Math.max(0.04, c.end - c.start)), c.text ? `Removes: ${c.text}` : "")));
  return cuts.length;
}

async function removeCutMarkers() {
  const { project, seq } = await getSequence();
  const markers = await ppro.Markers.getMarkers(seq);
  let list = [];
  try {
    list = markers.getMarkers(["Comment"]);
  } catch (e) {
    list = (/** @type {any} */ (markers)).getMarkers();
  }
  const ours = (list || []).filter((m) => (m.getName() || "").startsWith(MARK));
  transact(project, "Hinglish Edit: remove cut markers", () => ours.map((m) => markers.createRemoveMarkerAction(m)));
  return ours.length;
}

// ---------------------------------------------------------------- import helpers
/** @param {PPro.Project} project */
async function sequenceIds(project) {
  const seqs = await project.getSequences();
  return new Set(seqs.map((s) => s.guid.toString()));
}

/**
 * Import the XML timeline the helper wrote; returns the new sequence.
 * @param {string} xmlPath @param {string} name
 */
async function importEditedSequence(xmlPath, name) {
  const project = await getProject();
  const before = await sequenceIds(project);
  const ok = await project.importFiles([xmlPath], true, /** @type {any} */ (null), false);
  if (!ok) throw new Error("Premiere could not import the edited timeline (XML).");
  const after = await project.getSequences();
  const created = after.filter((s) => !before.has(s.guid.toString()));
  const target = created.find((s) => s.name === name) || created[0];
  if (!target) throw new Error("The XML was imported, but no new sequence appeared. Look in the Project panel for a bin named after it.");
  try {
    await project.openSequence(target);
    await project.setActiveSequence(target);
  } catch (e) { /* opening is a convenience */ }
  return { guid: target.guid.toString(), name: target.name };
}

/** @param {string} guid */
async function deleteSequenceByGuid(guid) {
  const project = await getProject();
  const seqs = await project.getSequences();
  const s = seqs.find((x) => x.guid.toString() === guid);
  if (!s) return false;
  return project.deleteSequence(s);
}

/** Collect every item id under a bin (recursive). @param {any} folder */
async function collectItems(folder, out = new Map()) {
  const items = await folder.getItems();
  for (const it of items) {
    out.set(it.getId(), it);
    let f = null;
    try { f = ppro.FolderItem.cast(it); } catch (e) { f = null; }
    if (f) {
      try { await collectItems(f, out); } catch (e) { /* not a bin */ }
    }
  }
  return out;
}

/** Import one file and return its ProjectItem. @param {string} path */
async function importFile(path) {
  const project = await getProject();
  const root = await project.getRootItem();
  const before = await collectItems(root);
  const ok = await project.importFiles([path], true, /** @type {any} */ (null), false);
  if (!ok) throw new Error("Premiere could not import " + path);
  const after = await collectItems(await project.getRootItem());
  const base = path.split(/[\\/]/).pop() || "";
  let found = null;
  for (const [id, it] of after) {
    if (!before.has(id)) { found = it; if ((it.name || "") === base) break; }
  }
  if (!found) {
    for (const [, it] of after) if ((it.name || "") === base) found = it;
  }
  if (!found) throw new Error("Imported, but could not find the new item in the Project panel.");
  return found;
}

/**
 * First video track (from the top) that is free over [start, end]; a new track index if none is.
 * @param {PPro.Sequence} seq @param {number} start @param {number} end
 */
async function freeVideoTrack(seq, start, end) {
  const count = await seq.getVideoTrackCount();
  for (let i = count - 1; i >= 1; i--) {
    const tr = await seq.getVideoTrack(i);
    const items = await tr.getTrackItems(C.TrackItemType.CLIP, false);
    let busy = false;
    for (const it of items) {
      const s = (await it.getStartTime()).seconds;
      const e = (await it.getEndTime()).seconds;
      if (s < end && e > start) { busy = true; break; }
    }
    if (!busy) {
      // only reuse it if no track above it is used (keeps captions on top)
      let above = false;
      for (let j = i + 1; j < count; j++) {
        const t2 = await seq.getVideoTrack(j);
        if ((await t2.getTrackItems(C.TrackItemType.CLIP, false)).length) { above = true; break; }
      }
      if (!above) return i;
    }
  }
  return count;
}

/**
 * Put an imported item on the timeline at `start` on a free top track.
 * @param {any} projectItem @param {number} start @param {number} end
 */
async function placeOnTop(projectItem, start, end) {
  const { project, seq } = await getSequence();
  const vIndex = await freeVideoTrack(seq, start, end);
  const before = await seq.getVideoTrackCount();
  const aCount = await seq.getAudioTrackCount();
  const editor = ppro.SequenceEditor.getEditor(seq);
  let countBefore = 0;
  if (vIndex < before) {
    const tr = await seq.getVideoTrack(vIndex);
    countBefore = (await tr.getTrackItems(C.TrackItemType.CLIP, false)).length;
  }
  transact(project, "Hinglish Edit: add captions", () => [
    vIndex >= before
      // a new track: insert creates it (documented); nothing below it shifts on an empty track
      ? editor.createInsertProjectItemAction(projectItem, tt(start), vIndex, aCount, true)
      : editor.createOverwriteItemAction(projectItem, tt(start), vIndex, aCount),
  ]);
  // check it really landed
  const after = await seq.getVideoTrackCount();
  if (vIndex >= after) throw new Error("Premiere did not add the item to the timeline.");
  const tr = await seq.getVideoTrack(vIndex);
  const countAfter = (await tr.getTrackItems(C.TrackItemType.CLIP, false)).length;
  if (countAfter <= countBefore) throw new Error("Premiere did not add the item to the timeline.");
  return vIndex;
}

// ---------------------------------------------------------------- Premiere's own transcription
/**
 * Transcribe the source clips with Premiere (free) and return what the helper needs.
 * @param {any} info sequence description @param {string} language "auto" | "hi" | "en"
 * @param {(msg:string)=>void} status
 */
async function premiereTranscripts(info, language, status) {
  const { seq } = await getSequence();
  const T = ppro.Transcript;
  /** @type {Map<string, {clip:any, items:any[]}>} */
  const byPath = new Map();
  const aCount = await seq.getAudioTrackCount();
  const unmutedIdx = info.audio_tracks.filter((/** @type {any} */ t) => !t.muted).map((/** @type {any} */ t) => t.index);
  for (let i = 0; i < aCount; i++) {
    if (unmutedIdx.length && !unmutedIdx.includes(i)) continue;
    const tr = await seq.getAudioTrack(i);
    for (const it of await tr.getTrackItems(C.TrackItemType.CLIP, false)) {
      const { path, clip } = await clipPath(it);
      if (!path || !clip || (await it.isDisabled())) continue;
      const rec = byPath.get(path) || { clip, items: [] };
      const d = { start: (await it.getStartTime()).seconds, end: (await it.getEndTime()).seconds, in: (await it.getInPoint()).seconds };
      if (!rec.items.some((x) => Math.abs(x.start - d.start) < 0.01 && Math.abs(x.in - d.in) < 0.01)) rec.items.push(d);
      byPath.set(path, rec);
    }
  }
  /** @type {any} */
  let options = undefined;
  if (language && language !== "auto" && typeof T.querySupportedLanguages === "function") {
    try {
      const langs = T.querySupportedLanguages() || [];
      const want = language === "hi" ? "hi" : "en";
      for (const l of langs) {
        const code = typeof l === "string" ? l : (l.languageCode || l.code || "");
        if (code.toLowerCase().startsWith(want)) { options = { language: code }; break; }
      }
    } catch (e) { /* use Premiere's preference */ }
  }
  const out = [];
  let n = 0;
  for (const [path, rec] of byPath) {
    n++;
    const name = path.split(/[\\/]/).pop();
    // hasTranscript / querySupportedLanguages exist from Premiere 26.3
    const has = typeof T.hasTranscript === "function" ? T.hasTranscript(rec.clip) : false;
    if (!has) {
      status(`Premiere is transcribing ${name} (${n}/${byPath.size})… this can take a few minutes.`);
      const ok = await T.transcribeClipProjectItem(rec.clip, options);
      if (!ok) throw new Error(`Premiere could not transcribe ${name}. Is the language pack installed?`);
    }
    const json = await T.exportToJSON(rec.clip);
    if (!json) throw new Error(`No transcript found for ${name}.`);
    out.push({ json, items: rec.items });
  }
  return out;
}

module.exports = {
  ppro, C, tt, getProject, getSequence, transact, describeSequence, jumpTo, playheadSeconds, inOutRange,
  addCutMarkers, removeCutMarkers, importEditedSequence, deleteSequenceByGuid, importFile, placeOnTop,
  premiereTranscripts,
};
