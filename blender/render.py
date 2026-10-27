"""Render a Spec in headless Blender.

    blender -b --factory-startup -P blender/render.py -- specs/<name>.json [--final]

Builds the scene from scratch (ADR 0005), with one orthographic camera
looking straight down at the Panel and one shared light rig, then renders
the Backplate into out/<name>/backplate.png and each Component's Frames
into out/<name>/frames/<id>/. Each Frame carries the Component's own
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
from parts import BUILDERS, PX, panel_to_world  # noqa: E402

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
    scene.view_settings.view_transform = "Standard"
    return scene


def set_quality(scene, quality):
    """Cycles for both: Eevee has no shadow catcher. A Draft takes fewer samples."""
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128 if quality == "final" else 16
    scene.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    if any(d.type == "METAL" for d in prefs.devices):
        for d in prefs.devices:
            d.use = d.type == "METAL"
        scene.cycles.device = "GPU"


def build_world(spec):
    light = spec.get("light", {})
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nodes = world.node_tree.nodes
    env = nodes.new("ShaderNodeTexEnvironment")
    hdri = Path(bpy.utils.system_resource("DATAFILES", path="studiolights")) / "world" / light.get("hdri", "studio.exr")
    env.image = bpy.data.images.load(str(hdri))
    background = nodes["Background"]
    background.inputs["Strength"].default_value = light.get("hdri_strength", 0.6)
    world.node_tree.links.new(env.outputs["Color"], background.inputs["Color"])
    # The studio shows only in reflections. Lighting surfaces with it would
    # darken the floor around every Component (occlusion), and a Frame's edge
    # would cut that off in a visible line. The fill light does its job instead.
    world.cycles_visibility.diffuse = False


def build_key_light(spec):
    """The key, from the top-left at `key_angle_deg` above the Panel: a sun
    for crisp shadows, and a softbox in the same direction so glossy surfaces
    show a highlight on their top-left shoulders. Returns the unit vector
    toward the light. Tuned so a light grey Panel renders near its colour."""
    light = spec.get("light", {})
    elevation = math.radians(light.get("key_angle_deg", 45))
    toward_light = Vector((-1, 1, 0)).normalized() * math.cos(elevation) + Vector((0, 0, math.sin(elevation)))
    aim = toward_light.to_track_quat("Z", "Y").to_euler()

    sun = bpy.data.lights.new("Key", "SUN")
    sun.energy = light.get("key_energy", 0.85)
    sun.angle = math.radians(light.get("key_softness_deg", 8))
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
    fill_data.energy = light.get("fill_energy", 5000)
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
    angle, plus its shadow, which falls away from the light. Whole pixels, so
    Frames line up with the Backplate's pixels."""
    margin = comp.get("margin", 4)
    # A point `height` above the Panel casts its shadow this far, in px; Panel y grows downward.
    run = height / toward_light.z
    shadow_x, shadow_y = -toward_light.x * run, toward_light.y * run
    half = extent / 2 + margin
    x, y = comp["pos"]
    x0 = math.floor(x - half + min(0, shadow_x))
    y0 = math.floor(y - half + min(0, shadow_y))
    x1 = math.ceil(x + half + max(0, shadow_x))
    y1 = math.ceil(y + half + max(0, shadow_y))
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


def top(root):
    """How high a Component stands above the Panel, in 1x px."""
    return max((obj.matrix_world @ Vector(corner)).z for obj in [root, *root.children_recursive]
               for corner in obj.bound_box) / PX


def frame_angles(comp, quality):
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


def render_component(scene, camera, spec, comp, root, rect, out_dir, scale, quality):
    """Render one Component's Frames; return its entry for render.json."""
    frame_camera(camera, scene, spec, rect, scale)
    frames_dir = out_dir / "frames" / comp["id"]
    frames_dir.mkdir(parents=True, exist_ok=True)
    angles = frame_angles(comp, quality)
    for i, angle in enumerate(angles):
        # Spec angles are clockwise from 12 o'clock as seen on screen; Blender's +Z rotation is counter-clockwise.
        root.rotation_euler.z = -math.radians(angle)
        scene.render.filepath = str(frames_dir / f"{comp['id']}_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    return {
        "id": comp["id"],
        "type": comp["type"],
        "bipolar": bool(comp.get("bipolar")),
        "angles": angles,
        "bounds": rect,
    }


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
    set_quality(scene, quality)
    build_world(spec)
    toward_light = build_key_light(spec)
    camera = build_camera()

    # Frames left from an earlier Render would be packed as if they were new.
    shutil.rmtree(out_dir / "frames", ignore_errors=True)
    wear = spec.get("wear", 0.3)
    groups = {"backplate": build_backplate(spec, wear)}
    rects = {}
    roots = {}
    for comp in spec["components"]:
        root, extent = BUILDERS[comp["type"]](spec, comp, wear)
        rects[comp["id"]] = frame_rect(comp, extent, top(root), toward_light)
        roots[comp["id"]] = root
        groups[comp["id"]] = [root, *root.children_recursive, shadow_catcher(spec, rects[comp["id"]])]

    unblock_fill([obj for name, objects in groups.items() if name != "backplate" for obj in objects])
    show_only(groups, "backplate")
    frame_camera(camera, scene, spec, [0, 0, *spec["panel"]["size"]], scale)
    scene.render.filepath = str(out_dir / "backplate.png")
    bpy.ops.render.render(write_still=True)

    rendered = []
    for comp in spec["components"]:
        show_only(groups, comp["id"])
        rendered.append(render_component(scene, camera, spec, comp, roots[comp["id"]], rects[comp["id"]],
                                         out_dir, scale, quality))

    # What tools/pack.py checks the Frames against.
    record = {
        "name": spec["name"],
        "quality": quality,
        "scale": scale,
        "panel": {"size": spec["panel"]["size"]},
        "components": rendered,
    }
    (out_dir / "render.json").write_text(json.dumps(record, indent=2) + "\n")


main()
