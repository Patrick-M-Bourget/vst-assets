"""The Backplate: the Panel's plate, rack ears, screws, hinge and printed
labels, including each Knob's Scale Marks and each VU Meter's face (ADR 0002).

Everything here is static and rendered once, into the Backplate. The plate's
face is at z = 0; parts mounted on it sit above.
"""

import math
from pathlib import Path

import bmesh
import bpy

import materials
from parts import PX, frustum, meter_pivot, new_object, panel_to_world, prism, scale_marks, soften

FONTS = Path(__file__).resolve().parent.parent / "fonts"
FONT_FILES = {"book": "Jost-400-Book.ttf", "medium": "Jost-500-Medium.ttf", "bold_italic": "Jost-700-BoldItalic.ttf"}
INK = "#262626"
RED_INK = "#b3261e"
FACE_Z = 0.3  # px: a VU Meter's face sits just proud of the plate
PLATE_THICKNESS = 4  # px


def build_backplate(spec, wear):
    """Every Backplate object, in a list."""
    panel = spec["panel"]
    w, h = panel["size"]
    ear = panel.get("ears", 0)
    plate_mat = materials.make(panel.get("material", "powder_coat"), wear, panel.get("color"),
                               panel.get("texture"), (-w / 2 * PX, -h / 2 * PX, w * PX, h * PX),
                               panel.get("grain", 0.0))
    objects = []

    # The faceplate, and the rack ears either side of it with a hairline seam between.
    gap = 1.5 if ear else 0
    for x0, x1 in [(ear + gap / 2, w - ear - gap / 2)] + ([(0, ear - gap / 2), (w - ear + gap / 2, w)] if ear else []):
        objects.append(slab(spec, f"plate_{x0:g}", (x0, 0, x1, h), plate_mat))

    if ear:
        head = materials.make("bakelite_black", wear)
        washer = materials.make("zinc", wear)
        for x in (ear / 2, w - ear / 2):
            for y in panel.get("rack_screw_y", [0.29 * h, 0.71 * h]):
                objects += rack_screw(spec, (x, y), head, washer)

    steel = materials.make("zinc", wear, panel.get("screw_color"))
    ink = materials.make("paint_white", wear, INK)
    for pos in panel.get("screws", []):
        objects += panel_screw(spec, pos, steel, ink, head=panel.get("screw_head", "slotted"))
    if panel.get("trims"):
        nickel = materials.make("nickel", wear)
        for pos in panel["trims"]:
            objects += trim(spec, pos, nickel, steel, ink)

    if panel.get("hinge"):
        objects += hinge(spec, ear, steel)

    for label in panel.get("labels", []):
        objects.append(text(spec, label, wear))
    for comp in spec["components"]:
        objects += component_print(spec, comp, wear)
    return objects


def slab(spec, name, rect, mat):
    """A plate covering `rect` (x0, y0, x1, y1 in 1x px), its face at z = 0."""
    x0, y0, x1, y1 = rect
    cx, cy = panel_to_world(spec, (x0 + x1) / 2, (y0 + y1) / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, -PLATE_THICKNESS / 2 * PX))
    obj = bpy.context.object
    obj.name = name
    obj.scale = ((x1 - x0) * PX, (y1 - y0) * PX, PLATE_THICKNESS * PX)
    bpy.ops.object.transform_apply(scale=True)
    soften(obj, 0.8 * PX, segments=3)
    obj.data.materials.append(mat)
    return obj


def dome(name, radius, height):
    """A shallow screw-head dome sitting on z = 0."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (radius, radius, height)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    return obj


def rack_screw(spec, pos, head_mat, washer_mat):
    """A rack screw: a black domed head on a cup washer."""
    x, y = panel_to_world(spec, *pos)
    washer = frustum("rack_washer", 12 * PX, 10.5 * PX, 0, 1.6 * PX, segments=64)
    soften(washer, 0.6 * PX, segments=3)
    washer.data.materials.append(washer_mat)
    head = dome("rack_screw", 8.5 * PX, 4.5 * PX)
    head.location.z = 1.4 * PX
    head.data.materials.append(head_mat)
    for obj in (washer, head):
        obj.location.x, obj.location.y = x, y
    return [washer, head]


def panel_screw(spec, pos, steel, ink, radius=4.5, head="slotted"):
    """A small panel screw, `slotted` or `phillips` (a cross of two shorter
    slots). The slot sits at a fixed, slightly random-looking angle, as
    screws do."""
    x, y = panel_to_world(spec, *pos)
    dome_obj = dome("panel_screw", radius * PX, 1.8 * PX)
    dome_obj.data.materials.append(steel)
    turn = (pos[0] * 37 + pos[1] * 11) % 180
    slots = [(1.7, 0.9, turn)] if head == "slotted" else [(1.3, 0.8, turn), (1.3, 0.8, turn + 90)]
    objects = [dome_obj]
    for length, width, angle in slots:
        slot = box_obj("panel_screw_slot", (radius * length * PX, width * PX, 1.0 * PX))
        slot.location.z = 1.5 * PX
        slot.rotation_euler.z = math.radians(angle)
        slot.data.materials.append(ink)
        objects.append(slot)
    for obj in objects:
        obj.location.x, obj.location.y = x, y
    return objects


def trim(spec, pos, nut_mat, steel, ink, across_flats=26):
    """A trimmer adjusted with a screwdriver: a hex bushing with a slotted
    screw sunk in its middle, as beside an LA-2A's Limit/Compress switch."""
    r = across_flats / 2 / math.cos(math.radians(30)) * PX
    hexagon = [(r * math.cos(math.radians(60 * i)), r * math.sin(math.radians(60 * i))) for i in range(6)]
    nut = prism("trim_nut", hexagon, 0, 5 * PX)
    soften(nut, 0.8 * PX, segments=3)
    nut.data.materials.append(nut_mat)
    x, y = panel_to_world(spec, *pos)
    nut.location.xy = (x, y)
    screw, slot = panel_screw(spec, pos, steel, ink, radius=7)
    for obj in (screw, slot):
        obj.location.z += 5 * PX
    return [nut, screw, slot]


def hinge(spec, ear, steel):
    """A piano hinge along the bottom edge: knuckles with hairline gaps."""
    w, h = spec["panel"]["size"]
    radius, knuckle = 3.2, 24
    objects = []
    x = ear + 4
    while x + knuckle <= w - ear - 4:
        cx, cy = panel_to_world(spec, x + knuckle / 2, h - radius - 1)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius * PX, depth=(knuckle - 0.8) * PX,
                                            location=(cx, cy, 0), rotation=(0, math.pi / 2, 0))
        obj = bpy.context.object
        obj.name = "hinge_knuckle"
        soften(obj, 0.5 * PX, segments=2)
        obj.data.materials.append(steel)
        objects.append(obj)
        x += knuckle
    return objects


def box_obj(name, size):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return obj


_fonts = {}


def font(name):
    if name not in _fonts:
        _fonts[name] = bpy.data.fonts.load(str(FONTS / FONT_FILES[name]))
    return _fonts[name]


def text(spec, label, wear, angle_deg=0.0, z=0.0):
    """Printed text centred on `pos`, `size` px tall (cap height), turned
    clockwise by `angle_deg`, on a surface `z` px above the plate.
    Silkscreen: a very thin raised layer of paint."""
    curve = bpy.data.curves.new(f"text_{label['text']}", "FONT")
    curve.body = label["text"]
    curve.font = font(label.get("font", "medium"))
    curve.size = label.get("size", 8) / 0.7 * PX  # Jost's cap height is about 0.7 em
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.extrude = 0.08 * PX
    curve.space_character = label.get("tracking", 1.0)
    obj = bpy.data.objects.new(curve.name, curve)
    bpy.context.scene.collection.objects.link(obj)
    x, y = panel_to_world(spec, *label["pos"])
    obj.location = (x, y, (z + 0.08) * PX)
    obj.rotation_euler.z = -math.radians(angle_deg)
    curve.materials.append(materials.make("paint_white", wear, label.get("color", INK)))
    return obj


def component_print(spec, comp, wear):
    """A Component's label and Scale Marks, printed on the Backplate, or a VU Meter's face."""
    if comp["type"] == "vu_meter":
        return meter_face(spec, comp, wear)
    objects = []
    cx, cy = comp["pos"]
    if "label" in comp:
        label = dict(comp["label"])
        dx, dy = label.pop("offset", [0, 0])
        objects.append(text(spec, {**label, "pos": [cx + dx, cy + dy]}, wear))
    marks = comp.get("scale_marks")
    ticks = scale_marks(comp)
    if not ticks:
        return objects
    color, size = marks.get("color", INK), marks.get("size", 8)
    for mark in ticks:
        pos = polar((cx, cy), marks["radius"], mark["angle"])
        turn = 0.0 if marks.get("upright") else mark["angle"]
        objects.append(text(spec, {"text": mark["value"], "pos": pos, "size": size, "color": color}, wear, turn))
    if "dots" in marks:
        # A printed dot between each pair of marks, as on an 1176's dials.
        ink = materials.make("paint_white", wear, color)
        for a, b in zip(ticks, ticks[1:]):
            objects.append(dot(spec, polar((cx, cy), marks["dots"], (a["angle"] + b["angle"]) / 2), size * 0.3, ink))
    return objects


def dot(spec, pos, diameter, mat):
    """A printed dot, `diameter` px across, as thin as a label."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=diameter / 2 * PX, depth=0.08 * PX)
    obj = bpy.context.object
    obj.name = "print_dot"
    obj.location = (*panel_to_world(spec, *pos), 0.12 * PX)
    obj.data.materials.append(mat)
    return obj


def meter_face(spec, comp, wear):
    """A VU Meter's backlit face: an arc, black up to `red_from` and a thick
    red band after it, a tick and a number at each Scale Mark, an inner ring
    of numbers, and labels such as "VU"."""
    face = comp.get("face", {})
    marks = comp["scale_marks"]
    radius, red_from = marks["radius"], marks.get("red_from", float("inf"))
    pivot = meter_pivot(spec, comp)
    black = materials.make("paint_white", wear, INK)
    red = materials.make("paint_white", wear, RED_INK)

    # The face reaches a little under the bezel, so no edge shows in the window.
    w, h = (d + 8 for d in comp["window"])
    cx, cy = panel_to_world(spec, *comp["pos"])
    plate = slab(spec, f"{comp['id']}_face", (comp["pos"][0] - w / 2, comp["pos"][1] - h / 2,
                                               comp["pos"][0] + w / 2, comp["pos"][1] + h / 2),
                 materials.make("meter_face", wear, face.get("color"), face.get("texture"),
                                (cx - w / 2 * PX, cy - h / 2 * PX, w * PX, h * PX)))
    plate.scale.z = FACE_Z / PLATE_THICKNESS
    plate.location.z = FACE_Z / 2 * PX
    glow = plate.data.materials[0].node_tree.nodes["Principled BSDF"]
    # Always lit from behind.
    glow.inputs["Emission Color"].default_value = glow.inputs["Base Color"].default_value
    glow.inputs["Emission Strength"].default_value = face.get("glow", 0.25)
    objects = [plate]

    ticks = scale_marks(comp)
    first, last = ticks[0]["angle"], ticks[-1]["angle"]
    objects.append(arc(spec, pivot, radius, 0.8, first, min(red_from, last), black))
    if red_from < last:
        objects.append(arc(spec, pivot, radius + 1.2, 3.2, red_from, last, red))
    for mark in ticks:
        ink = red if mark["angle"] >= red_from else black
        objects.append(tick(spec, pivot, radius, 4.5, mark["angle"], ink))
        objects.append(text(spec, {"text": mark["value"], "pos": polar(pivot, radius + 10, mark["angle"]),
                                   "size": marks.get("size", 6), "color": RED_INK if ink is red else INK},
                            wear, mark["angle"], FACE_Z))
    inner = comp.get("inner_marks")
    if inner:
        for value, angle in inner["marks"]:
            objects.append(text(spec, {"text": value, "pos": polar(pivot, inner["radius"], angle),
                                       "size": inner.get("size", 4.5)}, wear, angle, FACE_Z))
    for label in face.get("labels", []):
        label = dict(label)
        dx, dy = label.pop("offset")
        objects.append(text(spec, {**label, "pos": [comp["pos"][0] + dx, comp["pos"][1] + dy]}, wear, 0, FACE_Z))
    return objects


def polar(centre, radius, angle_deg):
    """The 1x Panel point `radius` px from `centre` at `angle_deg` clockwise from 12 o'clock."""
    a = math.radians(angle_deg)
    return [centre[0] + radius * math.sin(a), centre[1] - radius * math.cos(a)]


def arc(spec, centre, radius, width, start_deg, end_deg, mat):
    """A printed band `width` px wide along a circle on the meter face."""
    bm = bmesh.new()
    steps = max(2, int(abs(end_deg - start_deg)))
    rows = []
    for i in range(steps + 1):
        angle = start_deg + (end_deg - start_deg) * i / steps
        rows.append([bm.verts.new((*panel_to_world(spec, *polar(centre, r, angle)), (FACE_Z + 0.05) * PX))
                     for r in (radius - width / 2, radius + width / 2)])
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        bm.faces.new((a0, a1, b1, b0))
    obj = new_object("meter_arc", bm)
    obj.data.materials.append(mat)
    return obj


def tick(spec, centre, radius, length, angle_deg, mat):
    """A tick standing out from the arc at `angle_deg`."""
    obj = box_obj("meter_tick", (0.8 * PX, length * PX, 0.1 * PX))
    x, y = panel_to_world(spec, *polar(centre, radius + length / 2, angle_deg))
    obj.location = (x, y, (FACE_Z + 0.05) * PX)
    obj.rotation_euler.z = -math.radians(angle_deg)
    obj.data.materials.append(mat)
    return obj
