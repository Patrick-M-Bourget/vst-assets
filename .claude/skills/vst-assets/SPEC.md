# Spec fields

Sizes and positions are in 1× px; `pos` is from the Panel's top-left. Angles are degrees clockwise from 12 o'clock. `specs/opto_leveler.json` uses every field.

## Top level

- `name`: output goes to `out/<name>/`.
- `notes.look_brief` (lines of text) and `notes.refs` (file names in `refs/<name>/`).
- `wear`: 0–1, default 0.3.
- `light`: `key_angle_deg` (45), `key_energy`, `softbox_energy`, `fill_energy`, `hdri` (a Blender studio light), `hdri_strength`.

## panel

`size`, `scale` (2), `material`, `color`, `texture`, `ears` (rack-ear width), `rack_screw_y`, `hinge`, `screws` (positions), `screw_head` (`slotted` or `phillips`), `trims` (positions of slotted trimmers on hex bushings), `labels`.

A label is `{text, pos, size, font, color, tracking}`, where `size` is cap height and `font` is `book`, `medium` (the default) or `bold_italic`.

## components

Every Component has `id`, `type`, `pos`, and optionally `margin` (px of Frame around the part, default 4).

- `knob`:
  - Shape and finish: `diameter`, `material`, `style` (`shape`: `plain` or `pointer_skirt`; `height`, `tip`, `tip_width_deg`).
  - Or `style.shape: "skirt_cap"`, a Knob stacked from parts, as on an 1176: an optional `skirt`, a `knurl` ring or body (`teeth`), and a `cap`, each {`diameter`, `height` in px, `material`}; defaults are `smoked_acrylic`, `bakelite_black` and `spun_aluminium`. `pointer`: `line` (white) or `dot` (black, on the cap); `pointer_on`: `skirt` (the default when there is one) or `cap`. `diameter` is unused; the widest part sets the Frame.
  - Frames: `frames` (128) and `angle` [start, end]; or `angles` [...] for a Stepped Knob; `bipolar`.
  - Printing: `label` ({text, offset, size}) and `scale_marks`: `values` spread evenly over the turn, or `marks` [[value, angle], ...]; `radius`, `size`, `color` (dark ink by default), `upright` (numbers stay level instead of turning to their angle) and `dots` (the radius of a dot printed between each pair of marks).
- `toggle`: `diameter` (nut, across flats), `bat_length`, `tilt_deg`, `material`, `states` (the bat leans down in the first State, up in the last).
- `button`: a latching rectangular push button. `size` [w, h], `height` (px proud when up, 12), `travel` (px it sinks when down, 8), `material`, `states` (`up` first, `down` last). One Component per button; interlocking a column is the plugin's job.
- `lamp`: `diameter`, `color`, `glow`, `states` (dark first, lit last).
- `vu_meter`:
  - Layout: `size` (bezel), `window`, `pivot` (offset from `pos`).
  - Needle: `frames`, `angle`.
  - Face: `scale_marks` ({radius, size, red_from, marks: [[value, angle], ...]}), `inner_marks`, `face` ({color, texture, glow, labels with `offset`}).

Materials: `bakelite_black`, `chrome`, `zinc`, `nickel`, `brushed_aluminium`, `powder_coat`, `paint_white`, `jewel_red`, `bezel_grey`, `glass`, `meter_face`, `spun_aluminium`, `smoked_acrylic` (in `blender/materials.py`).
