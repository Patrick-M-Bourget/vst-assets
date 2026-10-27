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
One control or indicator placed on a Panel: a Knob, Toggle, Lamp or VU Meter.
_Avoid_: Widget, control (for the rendered part)

**Stepped Knob**:
A Knob with a few fixed positions, given as explicit `angles`, such as a meter-function selector.
_Avoid_: Rotary switch, selector type

**Bipolar Knob**:
A Knob whose neutral value is at 12 o'clock. It always has an odd Frame count, so one Frame sits exactly at 0°.

**Scale Marks**:
The Spec's table of printed values and their angles. It draws both a Knob's tick ring or a VU Meter's face and the Manifest's value-to-angle list, so a needle or pointer always lands on its tick.

**Wear**:
One number from 0 to 1 for how used the hardware looks: scratches, dulled paint, dust in the recesses. 0.3 is light vintage.

**Refs**:
Reference images for a Spec, in `refs/<spec name>/`. They stay on the user's machine and are never committed.

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
`manifest.json` beside the outputs: every file's Frame size and count, angles, Scale Marks and 1× bounds on the Panel.

**Scale**:
The pixel multiple the outputs are rendered at, 2× by default. Spec positions are always in 1× pixels.

## Process

**Draft**:
A quick Render (Cycles at 16 samples, 1×, at most 16 Frames) used to check the look.

**Final**:
The Render that ships (Cycles, the Spec's Scale, every Frame).

**Contact Sheet**:
The Backplate with each Component's first, middle and last Frames composited in place: the image a Draft is reviewed from.

**Gate**:
A point where the user approves the look before work goes on.
