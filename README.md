# Hinglish Edit for Premiere Pro

An editing assistant for raw, full-length Hindi / English / Hinglish videos:

- **Cuts**: finds silence, long pauses, filler words (umm, uh, hmm, अं, aa…) and repeated words. You
  review every cut, then it builds a **new edited sequence**. Your original sequence is never changed.
- **Captions**: Roman Hinglish (*kya haal hai*), Devanagari (*क्या हाल है*), as spoken, or English (translated: Sarvam key for best quality, otherwise a free service with a daily limit). 14 designs:
  viral big-word stacks, glow caps, aesthetic serif, justified stack with script word, two-tone italic,
  hook styles and full-length subtitles. Fonts, colors, size, position and timing can be changed.
- **Zoom**: one-click smooth zoom in / out / punch-in / slow push on selected clips.

It has two parts:

| Part | What it does |
|---|---|
| **Panel** (`plugin` folder) | Runs inside Premiere Pro (Window ▸ UXP Plugins ▸ Hinglish Edit). Reads your timeline, shows cuts and captions, adds markers, zoom keyframes, imports results. |
| **Helper** (`helper` folder) | Small app on your PC. Mixes the audio, calls the transcription service, plans the cuts, writes the edited timeline, makes and renders captions. The panel talks to it at `http://127.0.0.1:47800`. |

Why two parts: Premiere's plugin system (UXP) cannot run AI or audio tools inside Premiere, so that work
happens in the helper on your own PC.

---

## Install on Mac (Apple Silicon: M1 and newer, including Mac mini)

1. Close Premiere Pro. Download **`HinglishEdit-Mac.pkg`** from the latest
   [release](https://github.com/akash2041993/HinglishEdit/releases).
2. Double-click it. Because the installer is not signed with a paid Apple developer ID, the Mac says
   *"Apple could not verify…"*. Click **Done** (not *Move to Trash*), then open
   **System Settings ▸ Privacy & Security**, scroll down and click **Open Anyway** next to
   *"HinglishEdit-Mac.pkg was blocked"*. Enter your Mac password and finish the installer.
3. The installer puts everything in **Applications ▸ HinglishEdit**, installs the Premiere panel, and starts the
   helper in a **Terminal** window. Keep that window open while you edit.
   Next time, double-click **Start Hinglish Edit Helper.command** in that folder, or click **Start helper** in the panel.
4. Open Premiere ▸ **Window ▸ UXP Plugins ▸ Hinglish Edit**. If it is not there, double-click
   **HinglishEdit.ccx** in Applications ▸ HinglishEdit.
5. The first time the helper reads a video from Desktop, Documents or an external drive, the Mac asks
   *"Terminal would like to access…"*: click **Allow**.

To remove it: double-click **Uninstall Hinglish Edit.command** in Applications ▸ HinglishEdit.
Settings and outputs on Mac are in `~/Library/Application Support/HinglishEdit`.
Problems during install are written to `/tmp/hinglish-edit-install.log`.

## Install on Windows

Download **`HinglishEdit-Setup.exe`** from the latest release and run it (close Premiere first). The sections
below describe the manual setup from source.

---

## Requirements

- Windows 10/11 or macOS (Apple Silicon), **Premiere Pro 25.6 or newer** (26.x recommended)
- **Python 3.9+** from [python.org](https://www.python.org/downloads/windows/) (tick *Add python.exe to PATH*)
- **ffmpeg**: the panel installs it for you (Settings ▸ *Install ffmpeg*), about 140 MB
- For transcription, one of:
  - **ElevenLabs** API key (best for Hinglish, about $0.22 per hour of audio), or
  - **Premiere built-in** transcription (free, needs Premiere's Hindi/English language pack; best on Premiere 26.3+), or
  - **Deepgram** API key
- Optional: **Sarvam AI** key for better Roman Hinglish spelling in captions

---

## Install (one time)

### 1. The helper
1. Copy the `helper` folder somewhere permanent, for example `Documents\HinglishEdit\helper`.
2. Double-click **`Start Helper.bat`**. A black window opens and says
   *"Hinglish Edit helper … is running"*. **Keep it open while you edit.** Close it when you are done.

### 2. The panel
**Option A – double-click install:** double-click **`HinglishEdit.ccx`**. Creative Cloud asks to install
an unverified plugin → click *Install*.

**Option B – UXP Developer Tool** (if the .ccx is refused):
1. Install **UXP Developer Tools** from the Creative Cloud app (*All apps ▸ UXP Developer Tools*).
2. In Premiere: *Settings ▸ Plugins ▸ Enable developer mode*, then restart Premiere.
3. In UXP Developer Tool: *Add Plugin* → choose `plugin\manifest.json` → *Load*.

Open it from **Window ▸ UXP Plugins ▸ Hinglish Edit**.

### 3. First setup in the panel
1. **Settings** tab → *Check connection* (should say *Connected*). If ffmpeg is missing, click *Install ffmpeg*.
2. Paste your **ElevenLabs API key** (elevenlabs.io ▸ Profile ▸ API keys), click **Save settings**.
3. Optional: *Choose "Start Helper.bat"…* so the panel's **Start helper** button can start it next time.

---

## Use it

### Cuts
1. Open your raw sequence. **Cuts** tab → choose the transcription service → **Analyze sequence**.
   (The transcript is saved. Analyzing the same audio again costs nothing.)
2. Move **Cut intensity** (Gentle ↔ Aggressive) and the tick boxes. The list updates instantly.
3. Click a row to jump the playhead 1 second before that cut, press Space to listen. Untick what you want to keep.
4. Optional: **Add markers** puts every cut on the timeline as a marker (*✂ Pause*, *✂ Filler*…) to review there.
5. **Create edited sequence** → a new sequence *"<name> - Hinglish Cut"* is imported and opened.
   **Undo** = *Undo: delete the edited sequence* (or just delete it). The original is untouched.

How cuts stay natural: a short pause is always left between words, cut points move to the quietest
nearby moment (no clicks), loud sounds the transcript missed (laughs, untranscribed words) are never cut,
and Hindi doubled words said on purpose (*dheere dheere, bahut bahut*) are kept.

### Captions
1. Open the sequence you want captions on (the original *or* the edited one made by the panel).
2. **Captions** tab → choose **Script** and **Design** → **Make captions**.
3. Fix any text in the list. Put `*stars*` around a word to make it the big word: `ye *galti* mat karna`.
4. **Preview selected** shows the design on your real video frame.
5. Choose the **Range** (whole sequence, In→Out, or the first seconds as a hook), then:
   - **Render designed captions**: a transparent video layer (QuickTime Animation with alpha) is
     rendered and placed on the top free video track, or
   - **Add as Premiere captions (SRT)**: editable Premiere captions you style in Premiere's caption tools.

### Zoom
Select clip(s) in the timeline, put the playhead where the zoom should start, choose type, amount,
duration and easing → **Apply zoom**. *Smooth* adds 2 editable Bezier keyframes; *Strong/Snap/Linear* write
the exact curve as frame-by-frame keyframes. **Remove zoom** clears them.

---

## What is tested and what is not (please read)

- **Mac**: the helper's full test runs on a real Apple Silicon Mac on GitHub for every build, and the built
  helper is started and checked there. The panel and the installer itself have **not** been tried on a Mac with
  Premiere yet.
- **Tested here** (Linux, with ffmpeg): the helper's full flow with a generated video and a simulated
  ElevenLabs response: cut planning (fillers, repeats, pauses, protected sounds, never cutting kept words),
  the edited-timeline XML (rebuilt and listened to, checking every kept word survives), captions in Roman
  and Devanagari, SRT, previews and the transparent caption render. All 14 designs were rendered and checked.
- **Checked but not run**: the panel's Premiere calls were type-checked against Adobe's official API
  reference (Premiere 26.5) and compared with Adobe's sample panel, but **no one has run them inside
  Premiere yet**. Things most likely to need a small fix on first use:
  1. **Zoom keyframe timing**: Adobe's docs do not say which clock keyframes use; developer reports say
     source-media time, which is the default here. If a zoom lands at the wrong place, Ctrl+Z and change
     *Keyframe timing* on the Zoom tab once.
  2. **SRT placement**: if Premiere refuses to put the SRT on the timeline from the plugin, it stays in the
     Project panel. Drag it to 00:00 on the timeline.
  3. Rendered captions go onto the top video track. If Premiere does not create a new track from the plugin,
     add an empty video track first.
- Not supported yet: clips with speed changes, nested sequences, graphics or adjustment layers inside the
  sequence being cut (these are listed as warnings and left out of the edited sequence), and effects applied
  to clips (the edited sequence is rebuilt from the media files).
- Transcription quality depends on the service. ElevenLabs is the best tested option for Hinglish; Premiere's
  free Hindi model is weaker on English words inside Hindi sentences.
- Your API keys are stored only in the helper's settings file on your PC
  (`%LOCALAPPDATA%\HinglishEdit\settings.json` on Windows, `~/Library/Application Support/HinglishEdit/settings.json` on Mac) and sent only to the service they belong to.

---

## Files

```
plugin/                 Premiere panel (UXP, manifest v5)
  manifest.json  index.html  index.js  styles.css
  js/premiere.js        Premiere API calls (timeline, markers, import, transcription)
  js/zoom.js            zoom keyframes
helper/
  Start Helper.bat      start the helper on Windows
  run_helper.py
  hinglish_edit/        helper code (Python standard library only; numpy optional for speed)
    server.py           local API for the panel
    transcribe.py       ElevenLabs Scribe v2, Deepgram Nova-3, Premiere transcript import
    cuts.py             cut planning        fillers.py   filler-word lists
    fcpxml.py           edited timeline as Final Cut Pro 7 XML (Premiere imports it)
    captions.py         caption timing + SRT    translit.py  Devanagari → Roman Hinglish
    ass_style.py, layouts.py   caption designs    render.py  rendering with ffmpeg/libass
  fonts/                open-licence fonts (OFL) with Hindi + English support, and metrics.json
  tests/test_end_to_end.py   full helper test      tests/gallery.py  picture of every design
tools/make_font_metrics.py   rebuild fonts/metrics.json after adding fonts
.github/workflows/build.yml  optional: builds HinglishEditHelper.exe (no Python needed) + HinglishEdit.ccx on GitHub
```

Helper output (edited XML timelines, SRT and caption videos) is saved in `%LOCALAPPDATA%\HinglishEdit\output`.
Keep it: your Premiere project links to those caption videos.
