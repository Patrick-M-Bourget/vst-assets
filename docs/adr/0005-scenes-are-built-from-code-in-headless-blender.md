# Scenes are built from code in headless Blender

Every Render starts from Blender's factory settings and builds its scene from the Spec in Python (`blender/`). No `.blend` file is kept: scenes stay diffable, reviewable and reproducible, and an agent can change them. Blender's version is pinned in `CLAUDE.md`.

## Considered Options

- **Substance Painter, Cinema 4D, Maya.** Rejected: an agent can't drive them.
- **2D procedural images in Python.** Rejected: faked lighting looks flat next to real metal and shadows.
- **Image generation models.** Rejected: they can't hold one Component steady across 128 Frames.

## Consequences

- Looks come from procedural geometry and materials. A new kind of knob is new code, not a sculpt.
- Image textures from Refs are allowed only on flat surfaces.
