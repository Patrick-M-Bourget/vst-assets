"""Procedural Component generators.

Each builder makes one Component at the scene origin, moves it to its
place on the Panel, and returns (root object, extent, pose). Everything is
parented to the root. The extent is the Frame's size in 1x px, or for a part
not centred on `pos`, its reach (left, top, right, bottom) from `pos`.
pose(value) sets the Component to what one Frame shows: a Knob's angle, or
a Toggle's or Lamp's State.
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


def knurled(radius, teeth, depth, segments_per_tooth=4):
    """A circle cut with `teeth` straight grooves `depth` deep: a knurled edge's outline."""
    points = []
    for i in range(teeth * segments_per_tooth):
        theta = 2 * math.pi * i / (teeth * segments_per_tooth)
        groove = 0.5 - 0.5 * math.cos(2 * math.pi * i / segments_per_tooth)  # 0 on a ridge, 1 in a groove
        r = radius - depth * groove
        points.append((r * math.sin(theta), r * math.cos(theta)))
    return points


def build_skirt_cap_knob(spec, comp, wear):
    """A Knob stacked from parts, as on an 1176: an optional thin `skirt`, a
    knurled `knurl` ring or body, and a spun metal `cap` on top. The pointer
    is a white `line` on the skirt or the cap, or a black `dot` near the
    cap's edge. Sizes are 1x px."""
    style = comp["style"]
    z, parts, reach = 0.0, {}, 0.0
    for key in ("skirt", "knurl", "cap"):
        part = style.get(key)
        if not part:
            continue
        r, h = part["diameter"] / 2 * PX, part["height"] * PX
        mat = materials.make(part.get("material", {"skirt": "smoked_acrylic", "knurl": "bakelite_black",
                                                    "cap": "spun_aluminium"}[key]), wear)
        if key == "knurl":
            obj = prism(f"{comp['id']}_knurl", knurled(r, part.get("teeth", 60), r * 0.05), z, z + h)
            soften(obj, h * 0.06, segments=2, angle_deg=60)
        else:
            obj = frustum(f"{comp['id']}_{key}", r, r * (0.97 if key == "cap" else 0.99), z, z + h)
            soften(obj, min(h * 0.35, r * 0.1), segments=5)
        obj.data.materials.append(mat)
        parts[key] = (obj, r, z + h)
        z += h
        reach = max(reach, r)

    root = next(iter(parts.values()))[0]
    for obj, _, _ in parts.values():
        if obj is not root:
            obj.parent = root

    pointer = style.get("pointer", "line")
    on = style.get("pointer_on", "skirt" if "skirt" in parts else "cap")
    _, r_on, top = parts[on]
    if pointer == "dot":
        # A small black dot set into the cap, two thirds of the way out.
        dot = frustum(f"{comp['id']}_dot", r_on * 0.12, r_on * 0.12, top - 0.2 * PX, top + 0.05 * PX, segments=32)
        dot.location.y = r_on * 0.62
        dot.data.materials.append(materials.make("bakelite_black", wear))
        dot.parent = root
    else:
        # On a skirt the line runs from the part under it out to the skirt's rim.
        inner = next((r for k, (_, r, _) in parts.items() if k != on and r < r_on), 0.0) if on == "skirt" else 0.1 * r_on
        line = box(f"{comp['id']}_line", r_on * 0.04 if on == "skirt" else r_on * 0.07,
                   (r_on - inner) * 0.92, (0, inner + (r_on - inner) * 0.5, top))
        line.data.materials.append(materials.make("paint_white", wear))
        line.parent = root

    root.location.xy = panel_to_world(spec, *comp["pos"])

    def pose(angle):
        root.rotation_euler.z = -math.radians(angle)

    return root, 2 * reach / PX, pose


def build_knob(spec, comp, wear):
    """A Knob. Styles: `pointer_skirt` (round cap on a teardrop skirt whose
    tail points away from the line, as on an LA-2A), `plain` (a bevelled
    cylinder), both with a white line on the cap pointing at the value, and
    `skirt_cap` (build_skirt_cap_knob)."""
    style = comp.get("style", {})
    shape = style.get("shape", "plain")
    if shape == "skirt_cap":
        return build_skirt_cap_knob(spec, comp, wear)
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
    return comp.get("states", ["up", "down"] if comp["type"] == "button" else ["off", "on"])


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


def build_button(spec, comp, wear):
    """A latching push button: a rectangular cap standing `height` px proud
    of the Panel when `up` (the first State) and sunk `travel` px when
    `down` (the last). The Panel hides whatever sinks below it."""
    w, h = (v * PX for v in comp["size"])
    height, travel = comp.get("height", 12) * PX, comp.get("travel", 8) * PX
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(w, h, height), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, height / 2), verts=bm.verts)
    cap = new_object(f"{comp['id']}_cap", bm)
    soften(cap, min(w, h) * 0.08, segments=4)
    cap.data.materials.append(materials.make(comp.get("material", "bakelite_black"), wear))

    x, y = panel_to_world(spec, *comp["pos"])
    cap.location = (x, y, 0)
    names = states(comp)

    def pose(state):
        cap.location.z = -travel * names.index(state) / (len(names) - 1)

    return cap, max(comp["size"]), pose


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


def scale_marks(comp):
    """A Component's Scale Marks as [{"value", "angle"}]: a VU Meter lists its
    angles, a Knob spreads its values evenly over its turn."""
    marks = comp.get("scale_marks")
    if not marks:
        return []
    if "marks" in marks:
        return [{"value": v, "angle": a} for v, a in marks["marks"]]
    start, end = comp.get("angle", [-150, 150])
    values = marks["values"]
    return [{"value": str(v), "angle": start + (end - start) * i / (len(values) - 1)} for i, v in enumerate(values)]


def meter_pivot(spec, comp):
    """A VU Meter's needle pivot, in 1x Panel px: below the window, behind the bezel."""
    (x, y), (dx, dy) = comp["pos"], comp["pivot"]
    return x + dx, y + dy


def build_vu_meter(spec, comp, wear):
    """A VU Meter's needle, turning on a pivot hidden behind the bezel. Its
    face is printed on the Backplate and its bezel and glass are an Overlay."""
    length = (comp["scale_marks"]["radius"] + 4) * PX
    hub = frustum(f"{comp['id']}_hub", 2.5 * PX, 2.5 * PX, 0, 3 * PX, segments=32)
    needle = box(f"{comp['id']}_needle", comp.get("needle_width", 1.0) * PX, length, (0, length / 2, 3 * PX))
    ink = materials.make("bakelite_black", wear)
    for obj in (hub, needle):
        obj.data.materials.append(ink)
    needle.parent = hub
    hub.location.xy = panel_to_world(spec, *meter_pivot(spec, comp))

    start, end = comp.get("angle", [-45, 45])
    reach = length / PX * max(abs(math.sin(math.radians(start))), abs(math.sin(math.radians(end))))
    px, py = meter_pivot(spec, comp)
    x, y = comp["pos"]
    extent = (x - px + reach, y - py + length / PX, px - x + reach, py - y + 3)

    def pose(angle):
        hub.rotation_euler.z = -math.radians(angle)

    return hub, extent, pose


def build_vu_overlay(spec, comp, wear):
    """A VU Meter's bezel and glass: everything drawn above its needle. Returns
    (objects, extent) like a builder's."""
    w, h = (d * PX for d in comp["size"])
    ww, wh = (d * PX for d in comp["window"])
    top, inset, lip = 9 * PX, 5 * PX, 1 * PX
    # Four rectangular loops, outside in: the bezel's outer wall, its flat top, and a bevel down to the window.
    loops = [(w / 2, h / 2, 0), (w / 2, h / 2, top), (w / 2 - inset, h / 2 - inset, top), (ww / 2, wh / 2, lip)]
    bm = bmesh.new()
    rings = [[bm.verts.new((sx * hx, sy * hy, z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
             for hx, hy, z in loops]
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bezel = new_object(f"{comp['id']}_bezel", bm)
    bezel.data.materials.append(materials.make("bezel_grey", wear))
    soften(bezel, 0.8 * PX, segments=3, angle_deg=30)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(ww + 2 * PX, wh + 2 * PX, 1), verts=bm.verts)
    glass = new_object(f"{comp['id']}_glass", bm)
    glass.location.z = 4.5 * PX
    glass.data.materials.append(materials.make("glass", wear))
    glass.visible_shadow = False  # a sheet of glass barely darkens what's behind it

    for obj in (bezel, glass):
        obj.location.xy = panel_to_world(spec, *comp["pos"])
    half_w, half_h = (d / 2 for d in comp["size"])
    return [bezel, glass], (half_w, half_h, half_w, half_h)


BUILDERS = {"knob": build_knob, "toggle": build_toggle, "lamp": build_lamp, "vu_meter": build_vu_meter,
            "button": build_button}
OVERLAY_BUILDERS = {"vu_meter": build_vu_overlay}
