# vst-assets

Skeuomorphic UI assets for audio plugins, rendered from code. A JSON spec describes a plugin's front panel. Headless Blender renders it into a backplate, vertical filmstrips for knobs, switches, lamps and meter needles (each frame carries its own shadow), and static overlays. A manifest records sizes, frame counts, and each frame's angle or state for the plugin's editor.

The first panel is an LA-2A-style opto leveler. See issue #1 for the spec and `GLOSSARY.md` for the vocabulary.

Its Final render ships in `assets/opto_leveler/`: the backplate, a filmstrip per control, the VU meter's bezel and glass overlay, `manifest.json`, and a contact sheet.

![OPTO-2 contact sheet](assets/opto_leveler/contact_sheet.png)

## Setup

The `vst-assets` skill lives in this repo (`.claude/skills/vst-assets/`) and runs the repo's own scripts, so installing it means cloning the repo and installing what the scripts need. Claude Code loads the skill on its own whenever it runs inside the repo; there is nothing to copy into `~/.claude`.

1. Clone the repo:

   ```sh
   git clone https://github.com/Patrick-M-Bourget/vst-assets.git
   cd vst-assets
   ```

2. Install Blender 5.2.3 LTS, the pinned version (`blender --version` should print it):

   ```sh
   brew install --cask blender
   ```

3. Install Pillow for the system Python, which runs the packing tools:

   ```sh
   python3 -m pip install --user Pillow
   ```

4. Check the setup. The tests should pass, and the smoke Draft should take about 30 s and end with `packed 2 Filmstrips`:

   ```sh
   python3 -m unittest discover tests
   blender -b --factory-startup -P blender/render.py -- specs/smoke.json
   python3 tools/pack.py out/smoke
   ```

5. Start Claude Code from the repo root (`claude`).

## Make a new Panel from reference photos

1. Pick a short name for the Panel, such as `fet_limiter`. Put photos of the hardware in `refs/<name>/`: a straight-on front view, close-ups of the knobs, switches and meters, and one shot showing the wear. Note where each came from in `refs/<name>/SOURCES.txt`. Refs never leave your machine (ADR 0003).
2. In Claude Code, ask for it, for example: *"Use the vst-assets skill to make a Panel called `fet_limiter` from the photos in `refs/fet_limiter/`."*
3. Claude writes the Look Brief and the Spec, renders Drafts, and reviews them against the Moodboard. Then it shows you the Contact Sheet and close-ups, and waits for your approval before rendering the Final. If the hardware has a part with no generator yet (a fader, an LED ladder), it proposes the new Component type as an issue and waits for you before building it.
4. After the last Gate it renders the Final, about 15 min. The files to ship land in `out/<name>/final/`; commit them to `assets/<name>/` as was done for `opto_leveler`.

Clones copy the look, never the brand: the Panel gets its own name, and no third-party names or logos appear in any render (ADR 0004).

## Render

```sh
blender -b --factory-startup -P blender/render.py -- specs/<name>.json [--final]
python3 tools/pack.py out/<name>
```

A Draft (16 samples, 1×, at most 16 frames) by default; `--final` renders with Cycles at the spec's scale. Output goes to `out/<name>/`, and the files to ship to `out/<name>/final/`.

## Refs

Put reference photos in `refs/<name>/` (never committed) and list their file names in the spec's `notes.refs`. Then:

```sh
python3 tools/refboard.py specs/<name>.json
```

This writes `out/<name>/moodboard.png` and prints each photo's dominant colours, to write the look brief from. Once the spec lists refs, `pack.py` also writes `out/<name>/compare.png`: the contact sheet beside the moodboard.

## Textures

A panel (`panel.texture`) or a VU meter face (`face.texture`) can take an image, given as a path from the repo root, which replaces its colour and is stretched over the surface. Commit only images you have the rights to.

