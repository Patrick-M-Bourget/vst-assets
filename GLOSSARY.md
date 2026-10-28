# vst-assets

Skeuomorphic plugin UI assets rendered from procedural Blender scenes. A Spec describes one Panel; a Render turns it into a Backplate, Filmstrips and Overlays that a plugin's editor draws.

## Inputs

**Spec**:
The JSON file in `specs/` that describes one Panel: its size, Scale, materials, Wear, light and Components.
_Avoid_: Config, scene file, layout

**Panel**:
A plugin's whole front face: the Backplate plus every Component placed on it.
_Avoid_: Faceplate (except for real hardware), skin, UI

**Component**:
One control or indicator placed on a Panel: a Knob, Toggle, Button, Lamp or VU Meter.
_Avoid_: Widget, control (for the rendered part)

**Stepped Knob**:
A Knob with a few fixed positions, given as explicit `angles`, such as a meter-function selector.
_Avoid_: Rotary switch, selector type

**Toggle**:
A bat-handle switch on a hex nut. Its Frames are its States, the bat leaning toward the bottom of the Panel in the first and toward the top in the last.
_Avoid_: Switch (alone), button

**Button**:
A latching rectangular push button, as in an 1176's ratio column: proud of the Panel in its first State (`up`), sunk in its last (`down`). Each button is its own Component.
_Avoid_: Key, switch (alone)

**Lamp**:
A jewel pilot light: faceted coloured glass in a bezel, dark in its first State and lit in its last.
_Avoid_: LED, indicator

**VU Meter**:
A needle meter in three layers: its face (arc, ticks, numbers) printed on the Backplate from its Scale Marks, its needle as a Filmstrip turning on a pivot hidden behind the bezel, and its bezel and glass as an Overlay. Always lit.
_Avoid_: Meter (alone), gauge

**State**:
The named position a Toggle, Button or Lamp shows in one Frame, such as `off` and `on`, listed in the Spec's `states` and the Manifest. A Knob's Frames are angles instead.

**Bipolar Knob**:
A Knob whose neutral value is at 12 o'clock. It always has an odd Frame count, so one Frame sits exactly at 0°.

**Scale Marks**:
The Spec's table of printed values and their angles. It draws both a Knob's tick ring or a VU Meter's face and the Manifest's value-to-angle list, so a needle or pointer always lands on its tick.

**Wear**:
One number from 0 to 1 for how used the hardware looks: scratches, dulled paint, dust in the recesses. 0.3 is light vintage.

**Refs**:
Reference images for a Spec, in `refs/<spec name>/`. They stay on the user's machine and are never committed.

**Moodboard**:
The Refs laid out in a grid, each over its dominant colours as swatches; `tools/refboard.py` makes it under `out/`.

**Look Brief**:
The written summary of the Refs in a Spec's `notes`: knob family, materials, colours, Wear and lighting, each tied to a Spec field.

## Outputs

**Backplate**:
The Panel's static image: plate, rack ears, screws, hinge, and the printed labels and Scale Marks, with the Components left out. Their shadows travel in their Frames (ADR 0007).
_Avoid_: Background (except in file names), bg image

**Filmstrip**:
A Component's Frames stacked top to bottom in one PNG.
_Avoid_: Sprite sheet, strip

**Frame**:
One image of a Component in one state, with its own shadow in the alpha; a Filmstrip's height is its Frame height times its Frame count.

**Overlay**:
A static transparent PNG drawn above a Filmstrip, such as a VU Meter's glass and bezel.

**Manifest**:
`manifest.json` beside the outputs: every file's Frame size and count, each Frame's angle or State, Scale Marks and 1× bounds on the Panel.

**Scale**:
The pixel multiple the outputs are rendered at, 2× by default. Spec positions are always in 1× pixels.

## Process

**Draft**:
A quick Render (Cycles at 16 samples, 1×, at most 16 Frames) used to check the look.

**Final**:
The Render that ships (Cycles, the Spec's Scale, every Frame).

**Contact Sheet**:
The Backplate with each Component's first, middle and last Frames composited in place: the image a Draft is reviewed from.

**Compare**:
`compare.png`: the Contact Sheet beside the Moodboard, written by `pack.py` when the Spec lists Refs. It's how a Draft is checked against its Refs.

**Gate**:
A point where the user approves the look before work goes on.
