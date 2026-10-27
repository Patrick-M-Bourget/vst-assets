"""Procedural Component generators.

Each builder makes one Component at the scene origin, moves it to its
place on the Panel, and returns (root object, Frame size in 1x px). The
root is what turns; everything else is parented to it.
"""

import math

import bmesh
import bpy

import materials

PX = 0.01  # Blender units per 1x pixel


def panel_to_world(spec, x, y):
    """1x Panel pixels (top-left origin, y down) to Blender XY (centre origin, y up)."""
    w, h = spec["panel"]["size"]
    return (x - w / 2) * PX, (h / 2 - y) * PX


def new_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def soften(obj, width, segments=4, angle_deg=40):
    """Round the hard edges so they catch a highlight, and smooth-shade the rest."""
    bevel = obj.modifiers.new("Bevel", "BEVEL")
    bevel.width = width
    bevel.segments = segments
    bevel.limit_method = "ANGLE"
    bevel.harden_normals = True
    for poly in obj.data.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))
    obj.select_set(False)


def prism(name, outline, z0, z1):
    """A solid from a closed XY outline, between heights z0 and z1."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in outline]
    face = bm.faces.new(bottom)
    extruded = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [v for v in extruded["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object(name, bm)


def frustum(name, r_bottom, r_top, z0, z1, segments=128):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r_bottom, radius2=r_top, depth=z1 - z0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, (z0 + z1) / 2))
    return new_object(name, bm)


def teardrop(radius, tip, half_width_deg, segments=256):
    """A circle pulled out to a point at 12 o'clock (+Y): a skirt's outline."""
    points = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        off = math.degrees(min(theta, 2 * math.pi - theta))  # degrees away from 12 o'clock
        pull = max(0.0, 1 - off / half_width_deg) ** 1.2
        r = radius + (tip - radius) * pull
        points.append((r * math.sin(theta), r * math.cos(theta)))
    return points


def build_knob(spec, comp, wear):
    """A Knob. Styles: `pointer_skirt` (round cap on a teardrop skirt whose
    tail points away from the line, as on an LA-2A) and `plain` (a bevelled
    cylinder). Both carry a white line on the cap pointing at the value."""
    style = comp.get("style", {})
    shape = style.get("shape", "plain")
    r = comp["diameter"] / 2 * PX
    h = r * style.get("height", 0.9)
    body_mat = materials.make(comp.get("material", "bakelite_black"), wear)
    line_mat = materials.make("paint_white", wear)

    body = frustum(f"{comp['id']}_body", r, r * 0.93, 0, h)
    soften(body, r * 0.18, segments=8)
    body.data.materials.append(body_mat)
    extent = r

    if shape == "pointer_skirt":
        # The skirt's tail points away from the line, as on an LA-2A.
        skirt_r, tip = r * 1.1, r * style.get("tip", 1.5)
        skirt_h = h * 0.3
        outline = [(x, -y) for x, y in teardrop(skirt_r, tip, style.get("tip_width_deg", 50))]
        skirt = prism(f"{comp['id']}_skirt", outline, 0, skirt_h)
        soften(skirt, skirt_h * 0.35, segments=5)
        skirt.data.materials.append(body_mat)
        skirt.parent = body
        extent = tip

    line = box(f"{comp['id']}_line", r * 0.07, r * 0.8, (0, r * 0.45, h))
    line.data.materials.append(line_mat)
    line.parent = body

    body.location.xy = panel_to_world(spec, *comp["pos"])
    return body, 2 * extent / PX


def box(name, width, length, at):
    """A thin inlay of paint lying on a surface at `at`, running along +Y."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(width, length, 0.0015), verts=bm.verts)
    bmesh.ops.translate(bm, vec=at, verts=bm.verts)
    return new_object(name, bm)


BUILDERS = {"knob": build_knob}
