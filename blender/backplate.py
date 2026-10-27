"""The Backplate: the Panel's plate, rack ears, screws, hinge and printed
labels, including each Knob's Scale Marks (ADR 0002).

Everything here is static and rendered once, into the Backplate. The plate's
face is at z = 0; parts mounted on it sit above.
"""

import math
from pathlib import Path

import bpy

import materials
from parts import PX, frustum, new_object, panel_to_world, soften

FONTS = Path(__file__).resolve().parent.parent / "fonts"
FONT_FILES = {"book": "Jost-400-Book.ttf", "medium": "Jost-500-Medium.ttf", "bold_italic": "Jost-700-BoldItalic.ttf"}
INK = "#262626"
PLATE_THICKNESS = 4  # px


def build_backplate(spec, wear):
    """Every Backplate object, in a list."""
    panel = spec["panel"]
    w, h = panel["size"]
    ear = panel.get("ears", 0)
    plate_mat = materials.make(panel.get("material", "powder_coat"), wear, panel.get("color"))
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

    steel = materials.make("zinc", wear)
    ink = materials.make("paint_white", wear, INK)
    for pos in panel.get("screws", []):
        objects += panel_screw(spec, pos, steel, ink)

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


def panel_screw(spec, pos, steel, ink, radius=4.5):
    """A small slotted panel screw. The slot sits at a fixed, slightly
    random-looking angle, as screws do."""
    x, y = panel_to_world(spec, *pos)
    head = dome("panel_screw", radius * PX, 1.8 * PX)
    head.data.materials.append(steel)
    slot = box_obj("panel_screw_slot", (radius * 1.7 * PX, 0.9 * PX, 1.0 * PX))
    slot.location.z = 1.5 * PX
    slot.rotation_euler.z = math.radians((pos[0] * 37 + pos[1] * 11) % 180)
    slot.data.materials.append(ink)
    for obj in (head, slot):
        obj.location.x, obj.location.y = x, y
    return [head, slot]


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


def text(spec, label, wear, angle_deg=0.0):
    """Printed text centred on `pos`, `size` px tall (cap height), turned
    clockwise by `angle_deg`. Silkscreen: a very thin raised layer of paint."""
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
    obj.location = (x, y, 0.08 * PX)
    obj.rotation_euler.z = -math.radians(angle_deg)
    curve.materials.append(materials.make("paint_white", wear, label.get("color", INK)))
    return obj


def component_print(spec, comp, wear):
    """A Component's label and Scale Marks, printed on the Backplate."""
    objects = []
    cx, cy = comp["pos"]
    if "label" in comp:
        label = dict(comp["label"])
        dx, dy = label.pop("offset", [0, 0])
        objects.append(text(spec, {**label, "pos": [cx + dx, cy + dy]}, wear))
    marks = comp.get("scale_marks")
    if marks:
        start, end = comp.get("angle", [-150, 150])
        values = marks["values"]
        for i, value in enumerate(values):
            angle = start + (end - start) * i / (len(values) - 1)
            a = math.radians(angle)
            pos = [cx + marks["radius"] * math.sin(a), cy - marks["radius"] * math.cos(a)]
            objects.append(text(spec, {"text": str(value), "pos": pos, "size": marks.get("size", 8)}, wear, angle))
    return objects
