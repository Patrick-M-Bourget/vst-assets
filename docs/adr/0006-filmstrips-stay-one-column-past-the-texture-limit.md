# Filmstrips stay one column past the texture limit

A Knob keeps 128 Frames in one vertical Filmstrip even when that makes it taller than 16384 px, the texture limit many GPUs and hosts have. The LA-2A-style Gain Knob at 2× is 222×28416. JUCE's software and CoreGraphics renderers draw images of any height, and a single column is what JUCE's filmstrip drawing expects. `pack.py` still warns, so the size is never a surprise.

## Considered Options

- **64 Frames.** Rejected: about 4.7° per Frame steps visibly on a slow drag.
- **A grid sheet.** Rejected: every plugin would need its own drawing code to find a Frame.

## Consequences

- A plugin that draws its editor with OpenGL can't load these Filmstrips as single textures; revisit this then.
