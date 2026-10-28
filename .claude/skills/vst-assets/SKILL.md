---
name: vst-assets
description: Render skeuomorphic plugin UI assets (Backplate, Filmstrips, Overlays, Manifest) from a Panel Spec in headless Blender. Use when making a new Panel, changing a Component's look, turning Refs into a Look Brief, or checking a render against its Refs.
---

# vst-assets

One Spec in `specs/` describes one Panel. Use the words in `GLOSSARY.md`; the ADRs in `docs/adr/` are settled decisions. Spec fields are in [SPEC.md](SPEC.md).

## Loop

### 0. New Panel

For a Panel with no Spec yet: open a GitHub issue for it (`opto_leveler`'s is #1) and start `specs/<name>.json` from `specs/smoke.json`, with `name`, the Panel's `size` from the Refs' proportions, and `notes.refs` listing the photo files in `refs/<name>/`. Take positions and sizes from a straight-on Ref. The Panel gets our own name.

### 1. Refs → Look Brief

If `refs/<name>/` has photos and they're listed in the Spec's `notes.refs`, run `python3 tools/refboard.py specs/<name>.json` and read `out/<name>/moodboard.png` plus each photo. Write `notes.look_brief`: knob family, materials, colours (from the swatches), Wear, lighting, layout. Tie every line to a Spec field, and list anything no generator covers.

Done when every visible part of the Refs is either mapped to a Spec field or listed as uncovered. If the Spec needs Refs and has none, ask the user for them; Refs are needed before the first Knob is judged.

### 1b. Uncovered parts

A part no generator covers (`BUILDERS` in `blender/parts.py`: `knob`, `toggle`, `button`, `lamp` and `vu_meter` as of fet_limiter) is a new Component type. Don't fake it with an existing type or leave it out silently. For each one, open an issue that names the type, the Spec fields it needs, its Frames or States, and whether it needs an Overlay, then stop and ask the user whether to build it, defer it, or drop it from the Panel. Once it's built, add it to `BUILDERS`, [SPEC.md](SPEC.md) and the Component entry in `GLOSSARY.md`.

### 2. Spec

Edit the Spec. Positions are 1× px from the Panel's top-left. Clones copy the layout and materials, never the brand: our own name and wordmark, and no third-party names or logos anywhere in a render (ADR 0004).

### 3. Draft

```sh
blender -b --factory-startup -P blender/render.py -- specs/<name>.json
python3 tools/pack.py out/<name>
```

About 30 s. Pack must exit 0. Any warning except the known texture-limit one (ADR 0006) is a defect to fix before review.

### 4. Self-review

Read `out/<name>/compare.png` (or `contact_sheet.png` when there are no Refs), then crop and zoom into each Component. Check every item:

- Light comes from the top-left, and every shadow falls bottom-right.
- Nothing is cut off at a Frame's edge, and no seam or halo shows around a Frame on the Backplate.
- Each Filmstrip's first, middle and last Frames show the right angle or State.
- A VU needle lands on its ticks. Composite the Frame nearest each Scale Mark's angle and look.
- Colours and materials match the Moodboard's swatches, allowing for the photos' exposure.
- Labels read at 1×, and no third-party branding appears.

Fix and redraft, for up to three rounds. Done when every item passes, or what remains is a judgement call for the user.

### 5. Gate

Show the user the Contact Sheet and zoomed crops at a Gate, or whenever a judgement call remains. Say what you changed and what you're unsure of. Wait for their answer before the Final.

### 6. Final

```sh
blender -b --factory-startup -P blender/render.py -- specs/<name>.json --final
python3 tools/pack.py out/<name>
```

About 15 min for opto_leveler. Run it in the background. Report the files in `out/<name>/final/`, the Manifest, and any warnings.

## Gotchas

- A Cycles shadow catcher records any light a Component blocks, even one with `use_shadow` off. Exclude every Component from the fill (render.py does, via shadow linking), or Frames get a halo that their edge cuts off.
- Seen straight down, every flat top reflects straight up. Metal needs something bright there; black bakelite and paint must not see it, or they go milky. render.py's metal dome (light-linked to metal presets only) and procedural reflection rig handle this; a new metal preset must be added to `METALS` in render.py.
- A Frame carries shadow but cannot carry light spilling onto the Panel. Keep a glow inside the part (`visible_diffuse = False`).
