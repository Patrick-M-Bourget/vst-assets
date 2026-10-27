# Labels and Scale Marks are printed into the Backplate

Labels ("GAIN") and Scale Marks are rendered as silkscreened or engraved text and ticks on the Backplate, so they catch the same light and Wear as the hardware. The text uses one OFL font committed in `fonts/`, since the repo is public.

## Considered Options

- **Drawn by the plugin at runtime.** Rejected: crisp at any size and easy to change, but flat next to rendered metal and paint.

## Consequences

- Changing a label needs a new Render (seconds for a Draft).
- A VU Meter's face and a Knob's tick ring come from the same Scale Marks table as the Manifest's angles, so they can't drift apart.
