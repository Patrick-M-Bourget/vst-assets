# A Reason target renders in Reason's own coordinates

A Spec can set `"target": "reason"` to render a Rack Extension's 2D GUI instead of a JUCE editor's assets. Reason fixes a device's panel sizes: 3770 px wide at full resolution, 345 px per rack unit for the front and back, 150 for the folded strips. So a reason Spec's 1× space is Reason's 1/5 one, 754 wide and 69 per unit, and its Final renders at 5×: every Spec position times 5 is the offset `GUI2D/device_2D.lua` gives that image, with no rounding to fight. `pack.py` writes that file, the four backdrops (front, back, folded front, folded back) and the Filmstrips under `final/GUI2D/`. The `juce` target, the default, is unchanged.

The formats were checked against an open-source Rack Extension's GUI2D folder (pongasoft/re-vac-6) and a locally deployed one, not yet against Reason itself.

## Considered Options

- **Render at the JUCE size and resample to 3770.** Rejected: 3770/1100 isn't whole, so offsets and Frame edges land between pixels, and a 1100×200 Panel isn't a whole number of rack units.
- **Write hdgui_2D.lua too.** Rejected: it binds images to widgets and motherboard properties, which are the plugin's code, not its look.

## Consequences

- One layout serves one target. A Panel for both JUCE and Reason is two Specs, or a JUCE editor sized 754 × 69·U.
- The back panel gets plate, screws and labels only; jacks and cables are Reason's or the developer's.
