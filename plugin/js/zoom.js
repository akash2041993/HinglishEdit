// @ts-check
/* One-click smooth zoom: Scale keyframes on the Motion effect of the selected clips. */

const P = require("./premiere.js");
const { ppro, C, tt } = P;

const EASE = {
  /** @param {number} x */ linear: (x) => x,
  /** @param {number} x */ smooth: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  /** @param {number} x */ strong: (x) => (x < 0.5 ? 16 * Math.pow(x, 5) : 1 - Math.pow(-2 * x + 2, 5) / 2),
  /** @param {number} x */ snap: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
};

/** Find the Motion > Scale parameter of a clip. @param {any} item */
async function scaleParam(item) {
  const chain = await item.getComponentChain();
  const n = chain.getComponentCount();
  for (let i = 0; i < n; i++) {
    const comp = chain.getComponentAtIndex(i);
    const mn = await comp.getMatchName();
    if (mn !== "AE.ADBE Motion") continue;
    const pc = comp.getParamCount();
    for (let k = 0; k < pc; k++) {
      const p = comp.getParam(k);
      if ((p.displayName || "").toLowerCase() === "scale") return p;
    }
    return comp.getParam(1); // Motion: 0 Position, 1 Scale
  }
  // Fallback used by Adobe's own sample: component 1 = Motion, param 1 = Scale
  if (n > 1) {
    const comp = chain.getComponentAtIndex(1);
    if (comp.getParamCount() > 1) return comp.getParam(1);
  }
  throw new Error("This clip has no Motion effect (is it an audio clip or a title?).");
}

/** @param {any} kf */
function kfNumber(kf) {
  if (kf == null) return null;
  if (typeof kf === "number") return kf;
  const v = kf.value;
  if (typeof v === "number") return v;
  if (v && typeof v.value === "number") return v.value;
  return null;
}

/** Keyframe times are measured from the start of the source media by default (like ExtendScript).
 * @param {string} mode "source" | "clip" | "sequence"
 * @param {{start:number,in:number}} clip @param {number} seqT */
function kfTime(mode, clip, seqT) {
  if (mode === "sequence") return seqT;
  if (mode === "clip") return seqT - clip.start;
  return clip.in + (seqT - clip.start);
}

/**
 * @param {{type:string, amount:number, duration:number, hold:number, ease:string, at:string, timeMode:string}} opt
 *   type: in | out | punch | push ; amount: percent (e.g. 115) ; at: playhead | start
 */
async function applyZoom(opt) {
  const { project, seq } = await P.getSequence();
  const selection = await seq.getSelection();
  const items = (await selection.getTrackItems()).filter((/** @type {any} */ i) => i instanceof /** @type {any} */ (ppro).VideoClipTrackItem);
  if (!items.length) throw new Error("Select one or more video clips in the timeline first.");
  const tb = Number(await seq.getTimebase());
  const fps = tb > 0 ? 254016000000 / tb : 30;
  const playhead = (await seq.getPlayerPosition()).seconds;
  let done = 0;
  const notes = [];

  for (const item of items) {
    const clip = {
      start: (await item.getStartTime()).seconds,
      end: (await item.getEndTime()).seconds,
      in: (await item.getInPoint()).seconds,
    };
    const param = await scaleParam(item);
    let base = 100;
    try {
      base = kfNumber(await param.getStartValue()) ?? 100;
    } catch (e) { /* default 100 */ }
    const zoomed = base * (opt.amount / 100);

    let t0 = opt.at === "playhead" && playhead >= clip.start && playhead < clip.end ? playhead : clip.start;
    /** @type {[number, number][]} [sequence time, value] */
    let keys = [];
    const D = Math.max(1 / fps, opt.duration);
    if (opt.type === "push") {
      keys = [[clip.start, base], [clip.end - 1 / fps, zoomed]];
    } else if (opt.type === "out") {
      keys = [[t0, zoomed], [t0 + D, base]];
    } else if (opt.type === "punch") {
      const hold = Math.max(0, opt.hold);
      keys = [[t0, base], [t0 + D, zoomed], [t0 + D + hold, zoomed], [t0 + 2 * D + hold, base]];
    } else {
      keys = [[t0, base], [t0 + D, zoomed]];
    }
    keys = keys.filter(([t]) => t >= clip.start - 1e-6 && t <= clip.end + 1e-6);
    if (keys.length < 2) {
      notes.push("A clip was too short for this zoom at the playhead.");
      continue;
    }

    // Bake the easing curve as frame-by-frame keyframes for strong/snap; smooth = Bezier keys, linear = Linear keys.
    const bezier = opt.ease === "smooth";
    const twoKeys = bezier || opt.ease === "linear";
    /** @type {[number, number][]} */
    let frames = [];
    if (twoKeys) {
      frames = keys;
    } else {
      const ease = EASE[/** @type {"linear"|"smooth"|"strong"|"snap"} */ (opt.ease)] || EASE.smooth;
      for (let k = 0; k < keys.length - 1; k++) {
        const [ta, va] = keys[k];
        const [tb2, vb] = keys[k + 1];
        const steps = Math.max(1, Math.round((tb2 - ta) * fps));
        for (let s = 0; s < steps; s++) {
          const x = s / steps;
          frames.push([ta + (tb2 - ta) * x, va + (vb - va) * ease(x)]);
        }
      }
      frames.push(keys[keys.length - 1]);
    }

    // keyframes sit on frames: keep times on the frame grid so easing can be set on them
    frames = frames.map(([t, v]) => /** @type {[number, number]} */ ([Math.round(t * fps) / fps, v]));
    frames = frames.filter(([t], i) => i === 0 || t > frames[i - 1][0] + 1e-6);
    if (!param.isTimeVarying()) {
      P.transact(project, "Hinglish Edit: enable scale keyframes", () => [param.createSetTimeVaryingAction(true)]);
    }
    P.transact(project, "Hinglish Edit: zoom", () => frames.map(([t, v]) => {
      const kf = param.createKeyframe(Number(v.toFixed(3)));
      kf.position = tt(kfTime(opt.timeMode, clip, t));
      return param.createAddKeyframeAction(kf);
    }));
    try {
      const mode = bezier ? C.InterpolationMode.BEZIER : C.InterpolationMode.LINEAR;
      P.transact(project, "Hinglish Edit: zoom easing", () =>
        frames.map(([t]) => param.createSetInterpolationAtKeyframeAction(tt(kfTime(opt.timeMode, clip, t)), mode, true)));
    } catch (e) {
      notes.push("Keyframes added, but the easing type could not be set: " + e);
    }
    done++;
  }
  return { done, notes };
}

/** Remove Scale keyframes from the selected clips. @param {string} timeMode */
async function removeZoom(timeMode) {
  const { project, seq } = await P.getSequence();
  const selection = await seq.getSelection();
  const items = (await selection.getTrackItems()).filter((/** @type {any} */ i) => i instanceof /** @type {any} */ (ppro).VideoClipTrackItem);
  if (!items.length) throw new Error("Select the clips to reset first.");
  let n = 0;
  for (const item of items) {
    const clip = {
      start: (await item.getStartTime()).seconds,
      end: (await item.getEndTime()).seconds,
      in: (await item.getInPoint()).seconds,
    };
    const param = await scaleParam(item);
    if (!param.isTimeVarying()) continue;
    let base = 100;
    try {
      base = kfNumber(await param.getStartValue()) ?? 100;
    } catch (e) { /* default 100 */ }
    P.transact(project, "Hinglish Edit: remove zoom", () => [
      param.createRemoveKeyframeRangeAction(tt(kfTime(timeMode, clip, clip.start) - 0.001),
        tt(kfTime(timeMode, clip, clip.end) + 0.001), true),
      param.createSetTimeVaryingAction(false),
    ]);
    try {
      P.transact(project, "Hinglish Edit: reset scale", () => [param.createSetValueAction(param.createKeyframe(base), true)]);
    } catch (e) { /* value stays as Premiere left it */ }
    n++;
  }
  return n;
}

module.exports = { applyZoom, removeZoom };
