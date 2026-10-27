"""Procedural Component generators.

Each builder makes one Component at the scene origin, moves it to its
place on the Panel, and returns (root object, Frame size in 1x px, pose).
Everything is parented to the root. pose(value) sets the Component to what
one Frame shows: a Knob's angle, or a Toggle's or Lamp's State.
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

    def pose(angle):
        # Spec angles are clockwise from 12 o'clock as seen on screen; Blender's +Z rotation is counter-clockwise.
        body.rotation_euler.z = -math.radians(angle)

    return body, 2 * extent / PX, pose


def states(comp):
    return comp.get("states", ["off", "on"])


def build_toggle(spec, comp, wear):
    """A bat-handle toggle switch on a hex nut. The bat leans toward the
    bottom of the Panel in the first State and toward the top in the last;
    any States between are spread evenly."""
    nut_r = comp.get("diameter", 30) / 2 / math.cos(math.radians(30)) * PX  # diameter across flats
    bat = comp.get("bat_length", 36) * PX
    tilt = comp.get("tilt_deg", 22)
    metal = materials.make(comp.get("material", "nickel"), wear)

    hexagon = [(nut_r * math.cos(math.radians(60 * i + 30)), nut_r * math.sin(math.radians(60 * i + 30)))
               for i in range(6)]
    nut = prism(f"{comp['id']}_nut", hexagon, 0, 4 * PX)
    soften(nut, 0.8 * PX, segments=3)
    bushing = frustum(f"{comp['id']}_bushing", 6.5 * PX, 6.5 * PX, 4 * PX, 9 * PX, segments=64)
    soften(bushing, 0.8 * PX, segments=3)
    pivot = bpy.data.objects.new(f"{comp['id']}_pivot", None)
    bpy.context.scene.collection.objects.link(pivot)
    pivot.location.z = 9 * PX
    handle = frustum(f"{comp['id']}_bat", 3.6 * PX, 2.2 * PX, 0, bat, segments=48)
    soften(handle, 0.6 * PX, segments=2)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=3.6 * PX, location=(0, 0, bat))
    tip = bpy.context.object
    tip.name = f"{comp['id']}_tip"
    bpy.ops.object.shade_smooth()
    for obj in (nut, bushing, handle, tip):
        obj.data.materials.append(metal)
    for obj in (bushing, pivot):
        obj.parent = nut
    for obj in (handle, tip):
        obj.parent = pivot

    nut.location.xy = panel_to_world(spec, *comp["pos"])
    names = states(comp)
    reach = (bat + 3.6 * PX) * math.sin(math.radians(tilt)) + 3.6 * PX

    def pose(state):
        i = names.index(state)
        lean = -tilt + 2 * tilt * i / (len(names) - 1)
        # Rotating about -X leans the bat toward +Y, the top of the Panel.
        pivot.rotation_euler.x = -math.radians(lean)

    return nut, 2 * max(nut_r, reach) / PX, pose


def build_lamp(spec, comp, wear):
    """A jewel pilot Lamp: a faceted glass dome in a bezel, over a bulb that
    is dark in the first State and fully lit in the last."""
    r = comp.get("diameter", 24) / 2 * PX
    bezel = frustum(f"{comp['id']}_bezel", r, r * 0.9, 0, 2.5 * PX, segments=64)
    soften(bezel, 0.8 * PX, segments=3)
    bezel.data.materials.append(materials.make(comp.get("material", "nickel"), wear))

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0),
                           plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.scale(bm, vec=(r * 0.75, r * 0.75, r * 0.7), verts=bm.verts)
    jewel = new_object(f"{comp['id']}_jewel", bm)  # flat-shaded: the facets catch the light
    jewel.location.z = 2 * PX
    glass = materials.make("jewel_red", wear, comp.get("color"))
    jewel.data.materials.append(glass)

    bulb = frustum(f"{comp['id']}_bulb", r * 0.6, r * 0.6, 0, 2 * PX, segments=48)
    bulb_mat = materials.make("paint_white", wear, "#4a4440")  # an unlit bulb behind the glass
    bulb.data.materials.append(bulb_mat)
    for obj in (jewel, bulb):
        obj.parent = bezel
        # A Frame can't show light spilling onto the Panel, only shadow: keep the glow inside the Lamp.
        obj.visible_diffuse = False

    bezel.location.xy = panel_to_world(spec, *comp["pos"])
    names = states(comp)
    glow = comp.get("glow", 1.0)

    glowing = []
    for mat, color, strength in ((glass, None, 1.5), (bulb_mat, (1, 0.55, 0.3, 1), 12)):
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Emission Color"].default_value = color or tuple(bsdf.inputs["Base Color"].default_value)
        glowing.append((bsdf.inputs["Emission Strength"], strength * glow))

    def pose(state):
        lit = names.index(state) / (len(names) - 1)
        for emission, strength in glowing:
            emission.default_value = strength * lit

    return bezel, 2 * r / PX, pose


def box(name, width, length, at):
    """A thin inlay of paint lying on a surface at `at`, running along +Y."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(width, length, 0.0015), verts=bm.verts)
    bmesh.ops.translate(bm, vec=at, verts=bm.verts)
    return new_object(name, bm)


BUILDERS = {"knob": build_knob, "toggle": build_toggle, "lamp": build_lamp}
