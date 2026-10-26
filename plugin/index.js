// @ts-check
/* Panel UI: talks to the helper app (http://127.0.0.1:47800) and to Premiere (premiere.js). */

const P = require("./js/premiere.js");
const Z = require("./js/zoom.js");
const uxp = require("uxp");

/** @param {string} id @returns {any} */
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- small utils
const store = {
  /** @param {string} k @param {any} d */
  get(k, d) {
    try { const v = localStorage.getItem("he." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; }
  },
  /** @param {string} k @param {any} v */
  set(k, v) { try { localStorage.setItem("he." + k, JSON.stringify(v)); } catch (e) { /* ignore */ } },
};

/** @param {number} t */
function fmt(t) {
  t = Math.max(0, t || 0);
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s < 10 ? "0" : ""}${s.toFixed(1)}`;
}
/** @param {number} t */
function fmtDur(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t - m * 60);
  return m ? `${m}m ${s}s` : `${(Math.round(t * 10) / 10).toFixed(1)}s`;
}
/** @param {string} s */
function esc(s) {
  return String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] || c);
}
/** @param {string} msg @param {boolean} [isErr] */
function toast(msg, isErr) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  clearTimeout(/** @type {any} */ (toast).timer);
  /** @type {any} */ (toast).timer = setTimeout(() => { t.className = "toast hidden"; }, isErr ? 9000 : 4000);
}
/** @param {any} el @param {boolean} showIt */
function show(el, showIt) { if (showIt) el.classList.remove("hidden"); else el.classList.add("hidden"); }
/** @param {any} el @param {string} cls @param {boolean} on */
function setClass(el, cls, on) { if (on) el.classList.add(cls); else el.classList.remove(cls); }
/** Nearest ancestor (or self) with a class; UXP may not have Element.closest. @param {any} el @param {string} cls */
function up(el, cls) {
  while (el && el.classList) { if (el.classList.contains(cls)) return el; el = el.parentNode; }
  return null;
}
/** @param {string} sel */
const all = (sel) => /** @type {any[]} */ (Array.from(document.querySelectorAll(sel)));
/** @param {any} bar @param {number} f */
function setProgress(bar, f) { show(bar, f >= 0 && f < 1); bar.querySelector(".fill").style.width = Math.round(f * 100) + "%"; }
/** @param {string} btnId @param {() => Promise<any>} fn */
function busy(btnId, fn) {
  return async () => {
    const b = $(btnId);
    if (b.disabled) return;
    b.disabled = true;
    try { await fn(); } catch (e) { toast(String((/** @type {any} */ (e)).message || e), true); console.error(e); } finally { b.disabled = false; }
  };
}

// ---------------------------------------------------------------- helper API
const port = 47800; // must match manifest.json network permission
/** @type {any} */
let health = null;

const HOSTS = ["http://127.0.0.1:" + port, "http://localhost:" + port];
let hostIdx = 0;
/** @type {string} */
let lastNetError = "";

/** XMLHttpRequest fallback (some UXP builds treat fetch and XHR differently). */
function xhr(/** @type {string} */ method, /** @type {string} */ url, /** @type {string|undefined} */ body) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open(method, url);
    x.setRequestHeader("Content-Type", "application/json");
    x.onload = () => resolve({ ok: x.status >= 200 && x.status < 300, status: x.status, text: x.responseText });
    x.onerror = () => reject(new Error("XHR network error"));
    x.ontimeout = () => reject(new Error("XHR timeout"));
    x.send(body);
  });
}

/** @param {string} method @param {string} path @param {any} [body] */
async function api(method, path, body) {
  const payload = body ? JSON.stringify(body) : undefined;
  /** @type {any} */
  let res = null;
  const errors = [];
  for (let k = 0; k < HOSTS.length && !res; k++) {
    const host = HOSTS[(hostIdx + k) % HOSTS.length];
    try {
      const r = await fetch(host + path, { method, headers: { "Content-Type": "application/json" }, body: payload });
      res = { ok: r.ok, status: r.status, text: await r.text() };
      hostIdx = (hostIdx + k) % HOSTS.length;
    } catch (e) {
      errors.push(`fetch ${host}: ${(/** @type {any} */ (e)).message || e}`);
      try {
        res = await xhr(method, host + path, payload);
        hostIdx = (hostIdx + k) % HOSTS.length;
      } catch (e2) {
        errors.push(`xhr ${host}: ${(/** @type {any} */ (e2)).message || e2}`);
      }
    }
  }
  if (!res) {
    lastNetError = errors.join(" | ");
    setHelperDown(true);
    throw new Error("Can't reach the helper app. Is its window open? Details: " + lastNetError);
  }
  setHelperDown(false);
  let data = {};
  try { data = res.text ? JSON.parse(res.text) : {}; } catch (e) { /* not JSON */ }
  if (!res.ok) throw new Error(/** @type {any} */ (data).error || `Helper error ${res.status}`);
  return /** @type {any} */ (data);
}

/** @param {any} job @param {(f:number,msg:string)=>void} onProgress */
async function waitJob(job, onProgress) {
  for (;;) {
    const j = await api("GET", `/jobs/${job.id}`);
    onProgress(j.progress, j.message);
    if (j.status === "done") return j.result;
    if (j.status === "error") throw new Error(j.error);
    await new Promise((res) => setTimeout(res, 700));
  }
}

/** @param {boolean} down */
function setHelperDown(down) {
  show($("helperBar"), down);
}

async function checkHelper() {
  try {
    health = await api("GET", "/health");
  } catch (e) {
    $("helperInfo").innerHTML = `<span class="err">Not connected.</span> Open "Hinglish Edit Helper" from the desktop or Start menu (or click Start helper above).` +
      (lastNetError ? `<br><span class="small-text">Details: ${esc(lastNetError)}</span>` : "");
    setHelperDown(true);
    return false;
  }
  setHelperDown(false);
  const ff = health.ffmpeg || {};
  $("helperInfo").innerHTML = `<span class="ok">Connected</span> · helper ${esc(health.version)} · ` +
    (ff.found ? (ff.ass ? `<span class="ok">ffmpeg ready</span>` : `<span class="err">ffmpeg is too old for captions</span>`)
      : `<span class="err">ffmpeg missing</span>`);
  show($("btnInstallFfmpeg"), !ff.found || !ff.ass);
  try { fillSettings(health.settings); } catch (e) { console.error("settings UI", e); }
  try { fillStyles(); } catch (e) { console.error("styles UI", e); }
  return true;
}

// ---------------------------------------------------------------- tabs + active sequence
all(".tab").forEach((t) => t.addEventListener("click", () => {
  all(".tab").forEach((x) => setClass(x, "active", x === t));
  all(".page").forEach((p) => show(p, p.id === "page-" + t.getAttribute("data-tab")));
  refreshSequence();
}));

/** @type {{guid:string,name:string}|null} */
let activeSeq = null;
async function refreshSequence() {
  try {
    const { seq } = await P.getSequence();
    const s = { guid: seq.guid.toString(), name: seq.name };
    const changed = !activeSeq || activeSeq.guid !== s.guid;
    activeSeq = s;
    $("seqName").textContent = "Active sequence: " + s.name;
    $("capSeqName").textContent = "Active sequence: " + s.name;
    if (changed) onSequenceChanged();
  } catch (e) {
    activeSeq = null;
    $("seqName").textContent = "Open a sequence in the timeline.";
    $("capSeqName").textContent = "Open a sequence in the timeline.";
  }
}
setInterval(refreshSequence, 2500);

// analyses: sequence guid -> {id, name, provider}
// edits: edited-sequence guid -> {analysis_id, edit_name, source_guid, name}
function analysisForActive() {
  if (!activeSeq) return null;
  const a = store.get("analyses", {})[activeSeq.guid];
  if (a) return { analysis_id: a.id, edit_name: null, label: "Original: " + activeSeq.name };
  const e = store.get("edits", {})[activeSeq.guid];
  if (e) return { analysis_id: e.analysis_id, edit_name: e.edit_name, label: "Edited: " + activeSeq.name };
  return null;
}

function onSequenceChanged() {
  cuts = [];
  const a = activeSeq && store.get("analyses", {})[activeSeq.guid];
  analysisId = a ? a.id : null;
  show($("cutsArea"), !!analysisId);
  $("anStatus").textContent = a ? `Analyzed with ${a.provider} · ${a.words} words` : "";
  if (analysisId) planCuts();
  const lastEdit = activeSeq && store.get("lastEdit", {})[activeSeq.guid];
  show($("btnUndoApply"), !!lastEdit);
  refreshCaptionTimeline();
}

// ---------------------------------------------------------------- CUTS
/** @type {string|null} */
let analysisId = null;
/** @type {any[]} */
let cuts = [];
/** @type {any} */
let lastSummary = null;

$("provider").value = store.get("provider", "elevenlabs");
$("language").value = store.get("language", "auto");
$("provider").addEventListener("change", () => store.set("provider", $("provider").value));
$("language").addEventListener("change", () => store.set("language", $("language").value));

/** @param {boolean} force */
async function analyze(force) {
  const { info } = await P.describeSequence();
  if (!info.audio_tracks.some((/** @type {any} */ t) => t.items.length)) throw new Error("This sequence has no audio clips.");
  const provider = $("provider").value;
  const language = $("language").value;
  const bar = $("anProgress");
  const status = (/** @type {string} */ m) => { $("anStatus").textContent = m; };
  setProgress(bar, 0.01);
  /** @type {any} */
  let premiere_transcripts = null;
  if (provider === "premiere") {
    premiere_transcripts = await P.premiereTranscripts(info, language, status);
  }
  status("Sending to the helper…");
  const job = await api("POST", "/analyze", { seq: info, provider, language, premiere_transcripts, force });
  const res = await waitJob(job, (f, m) => { setProgress(bar, f); status(m); });
  setProgress(bar, 1);
  const all = store.get("analyses", {});
  all[info.guid] = { id: res.analysis_id, name: info.name, provider: res.provider, words: res.words, when: Date.now() };
  store.set("analyses", all);
  analysisId = res.analysis_id;
  status(`${res.reused ? "Reused the saved transcript · " : ""}${res.words} words found` +
    (res.language ? ` · language: ${res.language}` : ""));
  show($("cutsArea"), true);
  await planCuts();
  refreshCaptionTimeline();
}
$("btnAnalyze").addEventListener("click", busy("btnAnalyze", () => analyze(false)));
$("btnReanalyze").addEventListener("click", busy("btnReanalyze", () => analyze(true)));

function intensityName(/** @type {number} */ v) {
  return v < 25 ? "Gentle" : v < 70 ? "Normal" : "Aggressive";
}
function presetChecks(/** @type {number} */ v) {
  $("optAmbiguous").checked = v >= 35;
  $("optPhrases").checked = v >= 85;
  $("optRepeats").checked = v >= 35;
}
$("intensity").value = store.get("intensity", 50);
$("intensityLabel").textContent = intensityName(Number($("intensity").value));
presetChecks(Number($("intensity").value));

/** @type {any} */
let planTimer = null;
function schedulePlan() {
  clearTimeout(planTimer);
  planTimer = setTimeout(() => planCuts().catch((e) => toast(String(e.message || e), true)), 250);
}
$("intensity").addEventListener("input", () => {
  const v = Number($("intensity").value);
  $("intensityLabel").textContent = intensityName(v);
  presetChecks(v);
  store.set("intensity", v);
  schedulePlan();
});
["optSilence", "optSounds", "optAmbiguous", "optPhrases", "optRepeats"].forEach((id) => $(id).addEventListener("change", schedulePlan));

function disabledKeys() {
  return new Set(store.get("off." + analysisId, []));
}
/** @param {Set<string>} set */
function saveDisabled(set) { store.set("off." + analysisId, Array.from(set)); }

async function planCuts() {
  if (!analysisId) return;
  const res = await api("POST", "/cuts/plan", {
    analysis_id: analysisId,
    intensity: Number($("intensity").value),
    overrides: {
      cut_silence: $("optSilence").checked, cut_sounds: $("optSounds").checked,
      cut_ambiguous: $("optAmbiguous").checked, cut_phrases: $("optPhrases").checked, cut_repeats: $("optRepeats").checked,
    },
  });
  cuts = res.cuts;
  lastSummary = res.summary;
  renderCuts();
}

function enabledCuts() {
  const off = disabledKeys();
  return cuts.filter((c) => !off.has(c.key));
}

function renderCuts() {
  const off = disabledKeys();
  const list = $("cutList");
  if (!cuts.length) {
    list.innerHTML = `<div class="item muted">Nothing to cut at this intensity.</div>`;
  } else {
    list.innerHTML = cuts.map((c, i) => {
      const ctx = c.text
        ? `<div class="ctx">…${esc(c.before)} <b>${esc(c.text)}</b> ${esc(c.after)}…</div>` : "";
      return `<div class="item${off.has(c.key) ? " off" : ""}" data-i="${i}">
        <input type="checkbox" data-k="${esc(c.key)}" ${off.has(c.key) ? "" : "checked"}>
        <span class="time">${fmt(c.start)}</span>
        <div class="body"><span class="kind">${esc(c.label)} · ${c.duration.toFixed(2)}s</span>${ctx}</div>
      </div>`;
    }).join("");
  }
  // UXP inputs swallow events, so listen on each row and checkbox directly
  all("#cutList .item[data-i]").forEach((row) => {
    const c = cuts[Number(row.getAttribute("data-i"))];
    const box = row.querySelector("input");
    box.addEventListener("change", () => {
      const set = disabledKeys();
      if (box.checked) set.delete(c.key); else set.add(c.key);
      saveDisabled(set);
      setClass(row, "off", !box.checked);
      updateCutSummary();
    });
    row.addEventListener("click", (/** @type {any} */ ev) => {
      if (ev.target === box) return;
      P.jumpTo(Math.max(0, c.start - 1.0)).catch((e) => toast(String(e), true));
    });
  });
  updateCutSummary();
}

function updateCutSummary() {
  const en = enabledCuts();
  const removed = en.reduce((s, c) => s + (c.end - c.start), 0);
  const orig = lastSummary ? lastSummary.original : 0;
  $("cutSummary").textContent = `${en.length} of ${cuts.length} cuts on · removes ${fmtDur(removed)} · new length ${fmtDur(orig - removed)}`;
}

$("btnAll").addEventListener("click", () => { saveDisabled(new Set()); renderCuts(); });
$("btnNone").addEventListener("click", () => { saveDisabled(new Set(cuts.map((c) => c.key))); renderCuts(); });

$("btnMarkers").addEventListener("click", busy("btnMarkers", async () => {
  const n = await P.addCutMarkers(enabledCuts());
  toast(`Added ${n} markers. Review them in the timeline.`);
}));
$("btnUnmark").addEventListener("click", busy("btnUnmark", async () => {
  const n = await P.removeCutMarkers();
  toast(`Removed ${n} cut markers.`);
}));

$("btnApply").addEventListener("click", busy("btnApply", async () => {
  if (!analysisId || !activeSeq) throw new Error("Analyze the sequence first.");
  const en = enabledCuts();
  if (!en.length) throw new Error("No cuts are switched on.");
  const source = activeSeq;
  $("applyStatus").textContent = "Writing the edited timeline…";
  const res = await api("POST", "/cuts/xml", { analysis_id: analysisId, cuts: en });
  $("applyStatus").textContent = "Importing into Premiere…";
  const created = await P.importEditedSequence(res.xml_path, res.name);
  const edits = store.get("edits", {});
  edits[created.guid] = { analysis_id: analysisId, edit_name: res.name, source_guid: source.guid, name: created.name };
  store.set("edits", edits);
  const last = store.get("lastEdit", {});
  last[source.guid] = created.guid;
  store.set("lastEdit", last);
  const warn = (res.warnings || []).length ? ` Note: ${res.warnings.join(" ")}` : "";
  $("applyStatus").innerHTML = `<span class="ok">Done: "${esc(created.name)}" (${fmtDur(res.stats.seconds)}).</span>${esc(warn)}`;
  toast("Edited sequence created and opened.");
}));

$("btnUndoApply").addEventListener("click", busy("btnUndoApply", async () => {
  const src = activeSeq && store.get("edits", {})[activeSeq.guid] ? store.get("edits", {})[activeSeq.guid].source_guid : activeSeq && activeSeq.guid;
  const last = store.get("lastEdit", {});
  const guid = src ? last[src] : null;
  if (!guid) throw new Error("No edited sequence to delete.");
  const ok = await P.deleteSequenceByGuid(guid);
  delete last[/** @type {string} */ (src)];
  store.set("lastEdit", last);
  show($("btnUndoApply"), false);
  toast(ok ? "Deleted the edited sequence. Your original is unchanged." : "That sequence was already gone.");
}));

// ---------------------------------------------------------------- CAPTIONS
/** @type {any} */
let style = null;
/** @type {any[]} */
let captions = [];
let selectedCap = 0;

function fillStyles() {
  if (!health) return;
  const sel = $("capStyle");
  const cur = sel.value || store.get("styleId", "viral_keyword");
  sel.innerHTML = Object.keys(health.styles).map((k) => `<option value="${k}">${esc(health.styles[k].name)}</option>`).join("");
  sel.value = health.styles[cur] ? cur : "viral_keyword";
  const fontOpts = health.fonts.map((/** @type {string} */ f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("");
  $("sFont").innerHTML = fontOpts;
  $("sEmphFont").innerHTML = fontOpts;
  if (!style) loadStyle(sel.value, true);
}

/** @param {string} id @param {boolean} useSaved */
function loadStyle(id, useSaved) {
  const saved = useSaved ? store.get("style." + id, null) : null;
  style = Object.assign({}, health.styles[id], saved || {});
  store.set("styleId", id);
  styleToUi();
}

const colorFields = ["sColor", "sHighlight", "sOutlineColor", "sBoxColor", "sGradient", "sAccent"];
/** panel font names for the short names some designs use */
const FONT_ALIAS = { "Anton": "Anton (condensed)", "Great Vibes": "Great Vibes (script)" };
function styleToUi() {
  $("sFont").value = style.font;
  $("sEmphFont").value = /** @type {any} */ (FONT_ALIAS)[style.emph_font] || style.emph_font || style.font;
  $("sEmphScale").value = style.emph_scale;
  $("sGradient").value = style.gradient || "";
  $("sGlow").checked = !!style.glow;
  $("sAccent").value = style.accent_color || "";
  all(".layoutOnly").forEach((r) => show(r, (style.layout || "line") !== "line"));
  $("sSize").value = style.size;
  $("sColor").value = style.color;
  $("sHighlight").value = style.highlight;
  $("sOutlineColor").value = style.outline_color;
  $("sOutline").value = style.outline;
  $("sShadow").value = style.shadow;
  $("sBox").checked = !!style.box;
  $("sBoxColor").value = style.box_color;
  $("sBoxOpacity").value = style.box_opacity;
  $("sPosition").value = style.position;
  $("sY").value = style.y;
  $("sAnimation").value = style.animation;
  $("sWords").value = style.max_words;
  $("sLines").value = String(style.lines);
  $("sUpper").checked = !!style.uppercase;
  updateValues();
}
function updateValues() {
  $("sSizeV").textContent = Number($("sSize").value).toFixed(1) + "%";
  $("sEmphScaleV").textContent = Number($("sEmphScale").value).toFixed(1) + "×";
  $("sOutlineV").textContent = $("sOutline").value;
  $("sShadowV").textContent = $("sShadow").value;
  $("sBoxOpacityV").textContent = $("sBoxOpacity").value + "%";
  $("sYV").textContent = $("sY").value + "%";
  $("sWordsV").textContent = $("sWords").value;
  $("sOffsetV").textContent = Number($("sOffset").value).toFixed(2) + "s";
  colorFields.forEach((f) => { $(f + "Sw").style.backgroundColor = /^#[0-9a-fA-F]{6}$/.test($(f).value) ? $(f).value : "transparent"; });
}
function uiToStyle() {
  if (!style) return;
  const hex = (/** @type {string} */ id, /** @type {string} */ d) => (/^#[0-9a-fA-F]{6}$/.test($(id).value) ? $(id).value.toUpperCase() : d);
  Object.assign(style, {
    font: $("sFont").value, size: Number($("sSize").value), color: hex("sColor", style.color),
    highlight: hex("sHighlight", style.highlight), outline_color: hex("sOutlineColor", style.outline_color),
    outline: Number($("sOutline").value), shadow: Number($("sShadow").value), box: $("sBox").checked,
    box_color: hex("sBoxColor", style.box_color), box_opacity: Number($("sBoxOpacity").value),
    position: $("sPosition").value, y: Number($("sY").value), animation: $("sAnimation").value,
    max_words: Number($("sWords").value), lines: Number($("sLines").value), uppercase: $("sUpper").checked,
    emph_font: $("sEmphFont").value, emph_scale: Number($("sEmphScale").value),
    gradient: /^#[0-9a-fA-F]{6}$/.test($("sGradient").value) ? $("sGradient").value.toUpperCase() : "",
    glow: $("sGlow").checked,
    accent_color: /^#[0-9a-fA-F]{6}$/.test($("sAccent").value) ? $("sAccent").value.toUpperCase() : "",
  });
  store.set("style." + $("capStyle").value, style);
  updateValues();
}
["sFont", "sSize", "sColor", "sHighlight", "sOutlineColor", "sOutline", "sShadow", "sBox", "sBoxColor", "sBoxOpacity",
  "sAnimation", "sWords", "sLines", "sUpper", "sOffset", "sEmphFont", "sEmphScale", "sGradient", "sGlow", "sAccent"].forEach((id) => {
  $(id).addEventListener("input", uiToStyle);
  $(id).addEventListener("change", uiToStyle);
});
$("sPosition").addEventListener("change", () => {
  const map = { top: 18, middle: 62, bottom: 90 };
  $("sY").value = /** @type {any} */ (map)[$("sPosition").value] || 90;
  uiToStyle();
});
$("sY").addEventListener("input", uiToStyle);
$("capStyle").addEventListener("change", () => loadStyle($("capStyle").value, true));
$("btnStyleReset").addEventListener("click", () => { store.set("style." + $("capStyle").value, null); loadStyle($("capStyle").value, false); });
$("capScript").value = store.get("script", "roman");
$("capScript").addEventListener("change", () => store.set("script", $("capScript").value));

function refreshCaptionTimeline() {
  const a = analysisForActive();
  show($("capNeedsAnalysis"), !a);
  show($("capArea"), !!a);
  if (!a) return;
  $("capTimeline").innerHTML = `<option value="">${esc(a.label)}</option>`;
}

function capContext() {
  const a = analysisForActive();
  if (!a) throw new Error("Analyze this sequence first (Cuts tab), or open the edited sequence made by this panel.");
  return a;
}

$("btnCapBuild").addEventListener("click", busy("btnCapBuild", async () => {
  uiToStyle();
  const a = capContext();
  const res = await api("POST", "/captions/build", {
    analysis_id: a.analysis_id, edit_name: a.edit_name, style_id: $("capStyle").value, style,
    options: {
      script: $("capScript").value, max_words: style.max_words, lines: style.lines, max_chars: style.max_chars,
      uppercase: style.uppercase, offset: Number($("sOffset").value),
    },
  });
  captions = res.captions;
  selectedCap = Math.min(1, captions.length - 1);
  renderCaptions();
  show($("capListWrap"), true);
  toast(`${captions.length} captions ready. Edit any text, preview, then render.`);
}));

function renderCaptions() {
  $("capCount").textContent = `(${captions.length})`;
  $("capList").innerHTML = captions.map((c, i) => `<div class="item${i === selectedCap ? " sel" : ""}" data-i="${i}">
      <span class="time">${fmt(c.start)}</span>
      <div class="body"><input type="text" data-i="${i}" value="${esc(c.text)}"></div>
    </div>`).join("");
  all("#capList .item").forEach((row) => {
    const i = Number(row.getAttribute("data-i"));
    const input = row.querySelector("input");
    const select = () => {
      if (i === selectedCap) return;
      selectedCap = i;
      all("#capList .item").forEach((r) => setClass(r, "sel", Number(r.getAttribute("data-i")) === i));
    };
    const save = () => { captions[i].text = input.value.trim(); };
    input.addEventListener("change", save);
    input.addEventListener("input", save);
    input.addEventListener("focus", select);
    row.addEventListener("click", (/** @type {any} */ ev) => {
      select();
      if (ev.target !== input) P.jumpTo(captions[i].start).catch(() => {});
    });
  });
}

$("btnPreview").addEventListener("click", busy("btnPreview", async () => {
  uiToStyle();
  const a = capContext();
  const cap = captions[selectedCap];
  if (!cap) throw new Error("Make captions first.");
  const res = await api("POST", "/captions/preview", { analysis_id: a.analysis_id, edit_name: a.edit_name, caption: cap, style_id: $("capStyle").value, style });
  const img = $("capPreview");
  img.src = "data:image/png;base64," + res.png;
  show(img, true);
}));

async function captionRange() {
  const mode = $("capRange").value;
  if (mode === "inout") {
    const r = await P.inOutRange();
    if (!r) throw new Error("Set In and Out points on the sequence first (I and O keys).");
    return r;
  }
  const last = captions.length ? captions[captions.length - 1].end : 0;
  if (mode === "hook") return { start: 0, end: Math.min(last, Math.max(1, Number($("capHookSecs").value) || 8)) };
  return { start: 0, end: last };
}

$("btnRender").addEventListener("click", busy("btnRender", async () => {
  uiToStyle();
  const a = capContext();
  if (!captions.length) throw new Error("Make captions first.");
  const r = await captionRange();
  const caps = captions.filter((c) => c.end > r.start && c.start < r.end);
  const bar = $("capProgress");
  const job = await api("POST", "/captions/render", {
    analysis_id: a.analysis_id, captions: caps, style_id: $("capStyle").value, style, start: r.start, end: r.end,
    name: `${activeSeq ? activeSeq.name : "captions"} - ${style.name.replace("·", "-")}`,
  });
  const res = await waitJob(job, (f, m) => { setProgress(bar, f); $("capStatus").textContent = `${m} ${Math.round(f * 100)}%`; });
  setProgress(bar, 1);
  $("capStatus").textContent = "Importing into Premiere…";
  const item = await P.importFile(res.path);
  const track = await P.placeOnTop(item, r.start, r.end);
  $("capStatus").innerHTML = `<span class="ok">Captions placed on V${track + 1} at ${fmt(r.start)}.</span>`;
}));

$("btnSrt").addEventListener("click", busy("btnSrt", async () => {
  const a = capContext();
  if (!captions.length) throw new Error("Make captions first.");
  const r = await captionRange();
  const caps = captions.filter((c) => c.end > r.start && c.start < r.end);
  const res = await api("POST", "/captions/srt", { analysis_id: a.analysis_id, captions: caps, name: `${activeSeq ? activeSeq.name : "captions"} - ${$("capScript").value}` });
  const item = await P.importFile(res.path);
  try {
    await P.placeOnTop(item, 0, r.end);
    $("capStatus").innerHTML = `<span class="ok">Premiere captions added. Style them in the Properties / Essential Graphics panel.</span>`;
  } catch (e) {
    $("capStatus").innerHTML = `SRT imported to the Project panel as <b>${esc(item.name)}</b>. Drag it to the very start (00:00) of the timeline to add it as captions.`;
  }
}));

// ---------------------------------------------------------------- ZOOM
function zoomLabels() {
  $("zAmountV").textContent = $("zAmount").value + "%";
  $("zDurationV").textContent = Number($("zDuration").value).toFixed(2) + "s";
  $("zHoldV").textContent = Number($("zHold").value).toFixed(1) + "s";
  show($("zHoldRow"), $("zType").value === "punch");
}
["zAmount", "zDuration", "zHold", "zType"].forEach((id) => { $(id).addEventListener("input", zoomLabels); $(id).addEventListener("change", zoomLabels); });
const zSaved = store.get("zoom", null);
if (zSaved) ["zType", "zAmount", "zDuration", "zHold", "zEase", "zAt", "zTimeMode"].forEach((k) => { if (zSaved[k] != null) $(k).value = zSaved[k]; });
zoomLabels();

$("btnZoom").addEventListener("click", busy("btnZoom", async () => {
  const opt = {
    type: $("zType").value, amount: Number($("zAmount").value), duration: Number($("zDuration").value),
    hold: Number($("zHold").value), ease: $("zEase").value, at: $("zAt").value, timeMode: $("zTimeMode").value,
  };
  store.set("zoom", { zType: opt.type, zAmount: opt.amount, zDuration: opt.duration, zHold: opt.hold, zEase: opt.ease, zAt: opt.at, zTimeMode: opt.timeMode });
  const res = await Z.applyZoom(opt);
  $("zStatus").innerHTML = `<span class="ok">Zoom added to ${res.done} clip(s).</span> ${esc(res.notes.join(" "))}`;
}));
$("btnZoomRemove").addEventListener("click", busy("btnZoomRemove", async () => {
  const n = await Z.removeZoom($("zTimeMode").value);
  $("zStatus").textContent = `Removed zoom keyframes from ${n} clip(s).`;
}));

// ---------------------------------------------------------------- SETTINGS
/** @param {any} s */
function fillSettings(s) {
  if (!s) return;
  $("setEleven").value = s.elevenlabs_key || "";
  $("setDeepgram").value = s.deepgram_key || "";
  $("setSarvam").value = s.sarvam_key || "";
  $("setKeyterms").value = (s.keyterms || []).join(", ");
  $("setSounds").value = (s.filler_sounds || []).join(", ");
  $("setAmbiguous").value = (s.filler_ambiguous || []).join(", ");
  $("setPhrases").value = (s.filler_phrases || []).join(", ");
  $("setSounds").placeholder = "built-in: umm, uh, hmm, अं, हम्म…";
  $("setAmbiguous").placeholder = "built-in: aa, haan, ok, आ, हाँ…";
  $("setPhrases").placeholder = "built-in: basically, matlab, you know…";
}
/** @param {string} v */
const list = (v) => { const a = v.split(",").map((x) => x.trim()).filter(Boolean); return a.length ? a : null; };
$("btnSaveSettings").addEventListener("click", busy("btnSaveSettings", async () => {
  const s = await api("POST", "/settings", {
    elevenlabs_key: $("setEleven").value.trim(), deepgram_key: $("setDeepgram").value.trim(),
    sarvam_key: $("setSarvam").value.trim(), keyterms: list($("setKeyterms").value) || [],
    filler_sounds: list($("setSounds").value), filler_ambiguous: list($("setAmbiguous").value),
    filler_phrases: list($("setPhrases").value),
  });
  fillSettings(s);
  $("setStatus").innerHTML = `<span class="ok">Saved in the helper (keys never leave your PC except to the service they belong to).</span>`;
  if (analysisId) schedulePlan();
}));
$("btnFillersReset").addEventListener("click", () => { $("setSounds").value = ""; $("setAmbiguous").value = ""; $("setPhrases").value = ""; });
$("btnCheck").addEventListener("click", busy("btnCheck", async () => { if (await checkHelper()) toast("Helper connected."); }));
$("btnHelperRetry").addEventListener("click", busy("btnHelperRetry", checkHelper));
$("btnInstallFfmpeg").addEventListener("click", busy("btnInstallFfmpeg", async () => {
  const job = await api("POST", "/ffmpeg/install");
  await waitJob(job, (f, m) => { $("helperInfo").textContent = `${m} ${Math.round(f * 100)}%`; });
  await checkHelper();
  toast("ffmpeg installed.");
}));

/** true on macOS */
const IS_MAC = (() => {
  try { return String(require("os").platform()).toLowerCase().indexOf("darwin") >= 0; } catch (e) { /* fall through */ }
  try { return /mac/i.test(navigator.platform || ""); } catch (e) { return false; }
})();

async function pickHelper() {
  const fs = uxp.storage.localFileSystem;
  const file = await fs.getFileForOpening({ types: IS_MAC ? ["command", "app", "sh"] : ["bat", "exe", "cmd"] });
  if (!file) return null;
  const path = /** @type {any} */ (file).nativePath;
  store.set("helperPath", path);
  return path;
}
$("btnPickHelper").addEventListener("click", busy("btnPickHelper", async () => {
  const p = await pickHelper();
  if (p) toast("Saved. Use \"Start helper\" next time.");
}));
// where the installers put it
const DEFAULT_HELPER = IS_MAC
  ? "/Applications/HinglishEdit/Start Hinglish Edit Helper.command"
  : "C:\\Program Files\\HinglishEdit\\HinglishEditHelper.exe";
$("btnHelperStart").addEventListener("click", busy("btnHelperStart", async () => {
  const why = "Start the Hinglish Edit helper app on this computer";
  let path = store.get("helperPath", null);
  /** @param {string} p */
  const open = async (p) => { try { return await uxp.shell.openPath(p, why); } catch (e) { return String(e); } };
  let res = await open(path || DEFAULT_HELPER);
  if (res && !path) {
    path = await pickHelper();
    if (!path) return;
    res = await open(path);
  }
  if (res) throw new Error("Could not start the helper: " + res);
  toast(IS_MAC ? "Starting the helper… a Terminal window opens. Keep it open." : "Starting the helper… a window opens. Keep it open.");
  setTimeout(checkHelper, 3000);
  setTimeout(checkHelper, 7000);
}));

// ---------------------------------------------------------------- make sure every control shows a value
function initControls() {
  all("input[type=range]").forEach((r) => {
    const v = r.getAttribute("value");
    const min = Number(r.getAttribute("min") || 0), max = Number(r.getAttribute("max") || 100);
    const cur = Number(r.value);
    if (v != null && (isNaN(cur) || cur === min) && Number(v) !== min) r.value = v;
    if (isNaN(Number(r.value))) r.value = String((min + max) / 2);
  });
  all("select").forEach((sel) => {
    if (!sel.value && sel.options && sel.options.length) sel.value = sel.options[0].value;
  });
}
initControls();
zoomLabels();

// customize section folds away so the main buttons stay in view
$("btnCustomize").addEventListener("click", () => {
  const box = $("customizeBody");
  const open = box.classList.contains("hidden");
  show(box, open);
  $("btnCustomize").textContent = open ? "Customize ▴" : "Customize ▾";
});

// ---------------------------------------------------------------- start
(async () => {
  await checkHelper();
  await refreshSequence();
  setInterval(() => { if (!health || $("helperBar").classList.contains("hidden") === false) checkHelper(); }, 10000);
})();
