# AgX tone mapping, and Spec colours are material colours

Renders use Blender's AgX view with the "AgX - Medium High Contrast" look and +0.25 exposure, instead of Standard sRGB. The target is a hero product shot, judged against UAD, Arturia and Softube plugin UIs (#28): AgX rolls highlights off instead of clipping them, so chrome and glossy bakelite keep shape in their brightest spots, and its contrast look deepens a black faceplate.

So a Spec's colour is the material's own colour, not the pixel it renders as. AgX darkens and desaturates bright, saturated colours: a cream VU face renders greyer than its hex. Pack doesn't compensate. When a Panel reads too dark or too grey, change the Spec's colour. A Spec can still override `light.view`, `light.look` and `light.exposure`.

## Considered Options

- **Standard sRGB (v1).** Rejected: highlights clip to flat white and the panel reads flat.
- **AgX - Punchy.** Rejected for now: richer colour, but it crushes a black panel even at +0.5 exposure. Revisit at Look Gate A.
- **Compensate colours so the render matches the hex.** Rejected: it fights the tone mapping for every material, and the Refs' colours are only a guide anyway.

## Consequences

- OPTO-2 and FL-1 re-render with retuned colours (#36).
- refboard.py's swatches remain a starting point, not a target.
