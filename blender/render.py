"""Render a Spec in headless Blender.

    blender -b --factory-startup -P blender/render.py -- specs/<name>.json [--final]

Builds the scene from scratch (ADR 0005), with one orthographic camera
looking straight down at the Panel and one shared light rig, then renders
the Backplate into out/<name>/backplate.png and each Component's Frames
into out/<name>/frames/<id>/, and Overlays such as a VU Meter's bezel and
glass into out/<name>/overlays/. Each Frame and Overlay carries its own
shadow, caught on an invisible floor (ADR 0007). It records what it
rendered in out/<name>/render.json for tools/pack.py to check against.

Units: 1 Blender unit is 100 px at 1x. Spec positions are 1x pixels from
the Panel's top-left corner; the Panel lies in the XY plane facing +Z.
"""

import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backplate import build_backplate  # noqa: E402
from parts import BUILDERS, OVERLAY_BUILDERS, PX, panel_to_world, scale_marks, states  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DRAFT_MAX_FRAMES = 16


def parse_args():
    """The Spec's path, and whether this is a Final (`--final`) rather than a Draft."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    final = "--final" in argv
    paths = [a for a in argv if a != "--final"]
    if len(paths) != 1:
        sys.exit("usage: blender -b --factory-startup -P blender/render.py -- specs/<name>.json [--final]")
    return Path(paths[0]), final


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    return scene


def set_look(scene, spec):
    """Tone mapping: AgX by default, for highlights that roll off and colour
    that stays rich (ADR 0009). Spec colours are material colours."""
    light = spec.get("light", {})
    scene.view_settings.view_transform = light.get("view", "AgX")
    scene.view_settings.look = light.get("look", "AgX - Medium High Contrast")
    scene.view_settings.exposure = light.get("exposure", 0.25)


def set_quality(scene, quality):
    """Cycles for both: Eevee has no shadow catcher. A Draft takes fewer samples."""
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 256 if quality == "final" else 16
    scene.cycles.use_denoising = True
    # Denoise guided by albedo and normals so micro-relief survives it.
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.denoising_prefilter = "ACCURATE"
    # Glass shows only its reflections in the alpha, so what's under an Overlay shows through.
    scene.cycles.film_transparent_glass = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    if any(d.type == "METAL" for d in prefs.devices):
        for d in prefs.devices:
            d.use = d.type == "METAL"
        scene.cycles.device = "GPU"


def build_world(spec):
    """What shiny surfaces reflect. By default a procedural studio (`light.env`
    "rig"): a camera looking straight down sees each spot reflect the point
    straight above it, so cards hung over the Panel would light every Knob
    differently. An environment depends only on direction, so every part
    reflects the same studio. `light.env` "hdri" uses `light.hdri` instead."""
    light = spec.get("light", {})
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    background = nodes["Background"]
    if light.get("env", "rig") == "hdri":
        env = nodes.new("ShaderNodeTexEnvironment")
        hdri = Path(bpy.utils.system_resource("DATAFILES", path="studiolights")) / "world" / light.get("hdri", "studio.exr")
        env.image = bpy.data.images.load(str(hdri))
        background.inputs["Strength"].default_value = light.get("hdri_strength", 0.6)
        links.new(env.outputs["Color"], background.inputs["Color"])
    else:
        links.new(reflection_rig(nodes, links, light), background.inputs["Strength"])
        background.inputs["Color"].default_value = (1, 1, 1, 1)
    # The studio shows only in reflections. Lighting surfaces with it would
    # darken the floor around every Component (occlusion), and a Frame's edge
    # would cut that off in a visible line. The fill light does its job instead.
    world.cycles_visibility.diffuse = False


def reflection_rig(nodes, links, light):
    """The rig's brightness by direction, as a node output: a soft hot spot
    high toward the top-left (the streak on a spun cap, the shine on a
    glossy top), a low ring brighter on the top-left side (rims, knurls and
    bevels), and black elsewhere, for contrast."""
    direction = nodes.new("ShaderNodeTexCoord").outputs["Generated"]

    def toward(vector):
        dot = nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        links.new(direction, dot.inputs[0])
        dot.inputs[1].default_value = Vector(vector).normalized()
        return dot.outputs["Value"]

    def ramp(value, lo, hi, out_lo=0.0, out_hi=1.0):
        node = nodes.new("ShaderNodeMapRange")
        node.interpolation_type = "SMOOTHSTEP"
        node.inputs["From Min"].default_value, node.inputs["From Max"].default_value = lo, hi
        node.inputs["To Min"].default_value, node.inputs["To Max"].default_value = out_lo, out_hi
        links.new(value, node.inputs["Value"])
        return node.outputs["Result"]

    def times(a, b):
        node = nodes.new("ShaderNodeMath")
        node.operation = "MULTIPLY"
        for i, v in enumerate((a, b)):
            if isinstance(v, float):
                node.inputs[i].default_value = v
            else:
                links.new(v, node.inputs[i])
        return node.outputs["Value"]

    def plus(a, b):
        node = nodes.new("ShaderNodeMath")
        node.operation = "ADD"
        links.new(a, node.inputs[0])
        links.new(b, node.inputs[1])
        return node.outputs["Value"]

    # Well clear of straight up, which is what every flat top reflects: a
    # spot overhead would turn black bakelite and the Panel milky.
    elevation = math.radians(light.get("spot_elevation_deg", 52))
    spot_dir = (-math.cos(elevation) / math.sqrt(2), math.cos(elevation) / math.sqrt(2), math.sin(elevation))
    spot = times(ramp(toward(spot_dir), math.cos(math.radians(16)), math.cos(math.radians(5))), light.get("spot", 12.0))
    up = toward((0, 0, 1))
    band = times(ramp(up, 0.02, 0.12), ramp(up, 0.25, 0.4, 1.0, 0.0))
    side = ramp(toward((-1, 1, 0)), -1.0, 1.0, 0.35, 1.0)
    ring = times(times(band, side), light.get("ring", 3.0))
    # A dim, broad wash overhead: a satin sheen across glossy black tops,
    # far too faint to turn them milky.
    sky = times(ramp(toward((-0.25, 0.25, 1)), 0.75, 1.0), light.get("sky", 0.12))
    return plus(plus(spot, ring), sky)


METALS = ("chrome", "zinc", "nickel", "spun_aluminium", "brushed_aluminium")


def metal_dome(spec, objects):
    """Soft bright patches near straight up, so far away they act as part of
    the environment, that only metal can see (light linking). Flat
    metal reflects straight up and needs something bright there; flat black
    bakelite and paint must not see it, or they go milky."""
    light = spec.get("light", {})
    metal = [obj for obj in objects if obj.type == "MESH"
             and any(m and m.name.split(".")[0] in METALS for m in obj.data.materials)]
    if not metal:
        return None
    receivers = bpy.data.collections.new("Metal")
    for obj in metal:
        receivers.objects.link(obj)
    # Two soft patches on opposite sides of straight up, the top-left one
    # brighter: spun caps show the bright "bow-tie" of two wedges with dark
    # wedges between, as on the yardstick plugins.
    strength = light.get("dome", 40.0)
    patches = [(math.radians(135), light.get("dome_elevation_deg", 52), 6, strength),
               (math.radians(-45), 56, 5, strength * 0.6)]
    for i, (azimuth, elevation_deg, radius_deg, power) in enumerate(patches):
        patch = dome_patch(f"metal_dome_{i}", azimuth, math.radians(elevation_deg), radius_deg, power)
        patch.light_linking.receiver_collection = receivers
    return receivers


def dome_patch(name, azimuth, elevation, radius_deg, power, distance=500.0):
    """A soft emissive disc `distance` away in a direction, seen only in
    reflections: far enough that every part sees it in the same direction."""
    direction = Vector((math.cos(azimuth) * math.cos(elevation), math.sin(azimuth) * math.cos(elevation),
                        math.sin(elevation)))
    radius = distance * math.tan(math.radians(radius_deg))
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type="NGON", location=direction * distance)
    patch = bpy.context.object
    patch.name = name
    patch.rotation_euler = (-direction).to_track_quat("Z", "Y").to_euler()

    mat = bpy.data.materials.new(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes["Principled BSDF"])
    emission = nodes.new("ShaderNodeEmission")
    # Brightest in the middle, fading to nothing at the rim: a softbox, not a disc.
    coords = nodes.new("ShaderNodeTexCoord")
    length = nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    fade = nodes.new("ShaderNodeMapRange")
    fade.interpolation_type = "SMOOTHSTEP"
    fade.inputs["From Min"].default_value, fade.inputs["From Max"].default_value = radius, radius * 0.3
    fade.inputs["To Max"].default_value = power
    links.new(coords.outputs["Object"], length.inputs[0])
    links.new(length.outputs["Value"], fade.inputs["Value"])
    links.new(fade.outputs["Result"], emission.inputs["Strength"])
    links.new(emission.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    patch.data.materials.append(mat)
    for ray in ("visible_camera", "visible_diffuse", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        setattr(patch, ray, False)
    return patch


def build_key_light(spec):
    """The key, from the top-left at `key_angle_deg` above the Panel: a sun
    for crisp shadows, and a softbox in the same direction so glossy surfaces
    show a highlight on their top-left shoulders. Returns the unit vector
    toward the light. Tuned so a light grey Panel renders near its colour."""
    light = spec.get("light", {})
    elevation = math.radians(light.get("key_angle_deg", 38))
    toward_light = Vector((-1, 1, 0)).normalized() * math.cos(elevation) + Vector((0, 0, math.sin(elevation)))
    aim = toward_light.to_track_quat("Z", "Y").to_euler()

    sun = bpy.data.lights.new("Key", "SUN")
    sun.energy = light.get("key_energy", 1.1)
    sun.angle = math.radians(light.get("key_softness_deg", 5))
    key = bpy.data.objects.new("Key", sun)
    key.rotation_euler = aim
    bpy.context.scene.collection.objects.link(key)

    area = bpy.data.lights.new("Softbox", "AREA")
    area.shape = "DISK"
    # Small for its distance: bright enough per area that a glossy cap shows a
    # crisp highlight, while the light falling on the Panel stays modest.
    area.size = 3
    area.energy = light.get("softbox_energy", 600)
    softbox = bpy.data.objects.new("Softbox", area)
    softbox.location = toward_light * 15
    softbox.rotation_euler = aim
    bpy.context.scene.collection.objects.link(softbox)

    # Even ambient light from straight above. It casts no shadow, so the
    # shadow catcher keeps only the key's shadows.
    fill_data = bpy.data.lights.new("Fill", "AREA")
    fill_data.size = 40
    fill_data.energy = light.get("fill_energy", 3200)
    fill_data.use_shadow = False  # see also unblock_fill()
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.location = (0, 0, 20)
    fill.visible_glossy = False  # lights surfaces, but never shows as a highlight
    bpy.context.scene.collection.objects.link(fill)
    return toward_light


def unblock_fill(objects):
    """Let the fill pass through `objects`. use_shadow alone still lets the
    shadow catcher see a Component blocking the fill, as a dark halo around it."""
    blockers = bpy.data.collections.new("Fill blockers")
    for obj in objects:
        blockers.objects.link(obj)
    for entry in blockers.collection_objects:
        entry.light_linking.link_state = "EXCLUDE"
    bpy.data.objects["Fill"].light_linking.blocker_collection = blockers


def build_camera():
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    camera = bpy.data.objects.new("Camera", data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def frame_camera(camera, scene, spec, rect, scale):
    """Point the camera straight down at `rect` (x, y, w, h in 1x Panel px)."""
    x, y, w, h = rect
    cx, cy = panel_to_world(spec, x + w / 2, y + h / 2)
    camera.location = (cx, cy, 10)
    camera.rotation_euler = (0, 0, 0)
    camera.data.ortho_scale = max(w, h) * PX
    scene.render.resolution_x = round(w * scale)
    scene.render.resolution_y = round(h * scale)


def frame_rect(comp, extent, height, toward_light):
    """The 1x px rectangle a Component's Frames cover: the part itself at any
    angle, plus its shadow, which falls away from the light. `extent` is a
    size centred on `pos`, or a reach (left, top, right, bottom) from it.
    Whole pixels, so Frames line up with the Backplate's pixels."""
    margin = comp.get("margin", 4)
    # A point `height` above the Panel casts its shadow this far, in px; Panel y grows downward.
    run = height / toward_light.z
    shadow_x, shadow_y = -toward_light.x * run, toward_light.y * run
    left, top_, right, bottom = (extent / 2,) * 4 if isinstance(extent, (int, float)) else extent
    x, y = comp["pos"]
    x0 = math.floor(x - left - margin + min(0, shadow_x))
    y0 = math.floor(y - top_ - margin + min(0, shadow_y))
    x1 = math.ceil(x + right + margin + max(0, shadow_x))
    y1 = math.ceil(y + bottom + margin + max(0, shadow_y))
    return [x0, y0, x1 - x0, y1 - y0]


def shadow_catcher(spec, rect):
    """An invisible floor at the Panel's face that keeps only the shadows cast on it."""
    x, y, w, h = rect
    cx, cy = panel_to_world(spec, x + w / 2, y + h / 2)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, 0))
    floor = bpy.context.object
    floor.name = "shadow_catcher"
    floor.scale = (w * PX * 1.5, h * PX * 1.5, 1)
    floor.is_shadow_catcher = True
    return floor


def top(objects):
    """How high the highest of `objects` stands above the Panel, in 1x px."""
    return max((obj.matrix_world @ Vector(corner)).z for obj in objects for corner in obj.bound_box) / PX


def frame_angles(comp, quality):
    if "angles" in comp:
        # A Stepped Knob: its few positions, every one in a Draft too.
        return list(comp["angles"])
    start, end = comp.get("angle", [-150, 150])
    count = comp.get("frames", 128)
    if quality != "final":
        count = min(count, DRAFT_MAX_FRAMES)
    if comp.get("bipolar") and count % 2 == 0:
        # A Bipolar Knob needs a Frame at exactly 12 o'clock.
        count += 1
    if count == 1:
        return [start]
    return [start + (end - start) * i / (count - 1) for i in range(count)]


def frame_values(comp, quality):
    """What each Frame shows: ("angles", [...]) for a Knob, ("states", [...]) for a Toggle, Lamp or button."""
    if comp["type"] in ("knob", "vu_meter"):
        return "angles", frame_angles(comp, quality)
    return "states", states(comp)


def render_component(scene, camera, spec, comp, pose, rect, out_dir, scale, quality):
    """Render one Component's Frames; return its entry for render.json."""
    frame_camera(camera, scene, spec, rect, scale)
    frames_dir = out_dir / "frames" / comp["id"]
    frames_dir.mkdir(parents=True, exist_ok=True)
    key, values = frame_values(comp, quality)
    for i, value in enumerate(values):
        pose(value)
        scene.render.filepath = str(frames_dir / f"{comp['id']}_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    entry = {
        "id": comp["id"],
        "type": comp["type"],
        "bipolar": bool(comp.get("bipolar")),
        key: values,
        "bounds": rect,
    }
    if comp.get("scale_marks"):
        entry["scale_marks"] = scale_marks(comp)
    return entry


def show_only(groups, visible):
    """Render only the objects in group `visible`."""
    for name, objects in groups.items():
        for obj in objects:
            obj.hide_render = name != visible


def main():
    spec_path, final = parse_args()
    spec = json.loads(spec_path.read_text())
    quality = "final" if final else "draft"
    scale = spec["panel"].get("scale", 2) if quality == "final" else 1
    out_dir = REPO / "out" / spec["name"]

    scene = reset_scene()
    set_look(scene, spec)
    set_quality(scene, quality)
    build_world(spec)
    toward_light = build_key_light(spec)
    camera = build_camera()

    # Frames left from an earlier Render would be packed as if they were new.
    shutil.rmtree(out_dir / "frames", ignore_errors=True)
    shutil.rmtree(out_dir / "overlays", ignore_errors=True)
    wear = spec.get("wear", 0.3)
    groups = {"backplate": build_backplate(spec, wear)}
    rects = {}
    poses = {}
    overlays = {}
    for comp in spec["components"]:
        root, extent, poses[comp["id"]] = BUILDERS[comp["type"]](spec, comp, wear)
        parts = [root, *root.children_recursive]
        rects[comp["id"]] = frame_rect(comp, extent, top(parts), toward_light)
        groups[comp["id"]] = [*parts, shadow_catcher(spec, rects[comp["id"]])]
        if comp["type"] in OVERLAY_BUILDERS:
            parts, extent = OVERLAY_BUILDERS[comp["type"]](spec, comp, wear)
            overlay_id = f"{comp['id']}_glass"
            overlays[overlay_id] = frame_rect(comp, extent, top(parts), toward_light)
            groups[overlay_id] = [*parts, shadow_catcher(spec, overlays[overlay_id])]

    unblock_fill([obj for name, objects in groups.items() if name != "backplate" for obj in objects])
    metal_dome(spec, [obj for objects in groups.values() for obj in objects])
    show_only(groups, "backplate")
    frame_camera(camera, scene, spec, [0, 0, *spec["panel"]["size"]], scale)
    scene.render.filepath = str(out_dir / "backplate.png")
    bpy.ops.render.render(write_still=True)

    rendered = []
    for comp in spec["components"]:
        show_only(groups, comp["id"])
        rendered.append(render_component(scene, camera, spec, comp, poses[comp["id"]], rects[comp["id"]],
                                         out_dir, scale, quality))

    for overlay_id, rect in overlays.items():
        show_only(groups, overlay_id)
        frame_camera(camera, scene, spec, rect, scale)
        scene.render.filepath = str(out_dir / "overlays" / f"{overlay_id}.png")
        bpy.ops.render.render(write_still=True)

    # What tools/pack.py checks the Frames against.
    record = {
        "name": spec["name"],
        "quality": quality,
        "scale": scale,
        "panel": {"size": spec["panel"]["size"]},
        "components": rendered,
        "overlays": [{"id": overlay_id, "bounds": rect} for overlay_id, rect in overlays.items()],
        # Where this machine keeps the Refs, for compare.png (ADR 0003: never committed).
        "refs": [str(REPO / "refs" / spec["name"] / ref) for ref in spec.get("notes", {}).get("refs", [])],
    }
    (out_dir / "render.json").write_text(json.dumps(record, indent=2) + "\n")


main()
