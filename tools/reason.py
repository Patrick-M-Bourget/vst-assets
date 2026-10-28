"""Reason Rack Extension output, for a Spec with `"target": "reason"` (ADR 0008).

A Rack Extension's 2D GUI is PNGs plus GUI2D/device_2D.lua, which places
them. Its full-resolution panels are 3770 px wide: 345 px per rack unit for
the front and back, 150 for the folded strips. A reason Spec works in
Reason's 1/5 coordinate space (754 wide, 69 per U) and renders its Final at
5x, so every 1x position times 5 is a device_2D.lua offset.

Plain Python, no Blender: render.py imports it to check a Spec, pack.py to
write the GUI2D folder.
"""

import re

WIDTH = 754
U_HEIGHT = 69
FOLDED_HEIGHT = 30
SCALE = 5
# Each backdrop's section in device_2D.lua and the image file it ships as.
BACKDROPS = {
    "front": "Panel_Front",
    "back": "Panel_Back",
    "folded_front": "Panel_Folded_Front",
    "folded_back": "Panel_Folded_Back",
}
LUA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def check_spec(spec):
    """The problems that stop a Spec rendering for Reason, as a list of strings."""
    errors = []
    w, h = spec["panel"]["size"]
    if w != WIDTH:
        errors.append(f"panel width is {w}; a Reason Panel is {WIDTH} wide at 1x (3770 at 5x)")
    if h < U_HEIGHT or h % U_HEIGHT:
        errors.append(f"panel height is {h}; a Reason Panel is {U_HEIGHT} per rack unit at 1x (69, 138, 207, ...)")
    for comp in spec["components"]:
        if not LUA_NAME.match(comp["id"]):
            errors.append(f"Component id {comp['id']!r} isn't a Lua name: letters, digits and _, not starting with a digit")
    return errors


def backdrop_sizes(spec):
    """Each backdrop's 1x size: the back matches the front, the folded strips are 30 tall."""
    w, h = spec["panel"]["size"]
    return {"front": [w, h], "back": [w, h], "folded_front": [w, FOLDED_HEIGHT], "folded_back": [w, FOLDED_HEIGHT]}


def backdrop_panel(spec, side):
    """The `panel` block a backdrop renders from: the front's own, or for the
    back and folded strips the front's material with that side's own labels and
    screws (Spec blocks `back`, `folded_front`, `folded_back`) and no hinge."""
    panel = spec["panel"]
    if side == "front":
        return panel
    block = spec.get(side, {})
    return {
        **{k: v for k, v in panel.items() if k in ("scale", "material", "color", "texture", "grain",
                                                   "screw_head", "screw_color")},
        **block,
        "size": backdrop_sizes(spec)[side],
    }


def image_name(file):
    """A packed file's GUI2D name: no extension and no `_5x` suffix, as device_2D.lua refers to it."""
    return re.sub(r"_\d+x$", "", file.rsplit(".", 1)[0])


def device_2d(manifest):
    """GUI2D/device_2D.lua for a packed reason Manifest: each backdrop, then a
    node per Component and Overlay in the front section, offset in full-res px."""
    scale = manifest["scale"]

    def node(name, path, frames=1, offset=None):
        lines = [f"  {name} = {{"]
        if offset is not None:
            lines.append(f"    offset = {{ {offset[0]}, {offset[1]} }},")
        lines.append(f'    {{ path = "{path}"' + (f", frames = {frames}" if frames > 1 else "") + " },")
        lines.append("  },")
        return lines

    out = ['format_version = "1.0"', ""]
    for side, backdrop in manifest["backdrops"].items():
        out.append(f"{side} = {{")
        out += node("Bg", image_name(backdrop["file"]))
        if side == "front":
            for item in manifest["components"] + manifest.get("overlays", []):
                x, y = item["bounds"][:2]
                out += node(item["id"], image_name(item["file"]), item.get("frames", 1),
                            (round(x * scale), round(y * scale)))
        out += ["}", ""]
    return "\n".join(out)
