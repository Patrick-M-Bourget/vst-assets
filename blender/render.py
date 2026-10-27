"""Render a Spec in headless Blender.

    blender -b --factory-startup -P blender/render.py -- specs/<name>.json [--final]

Builds the scene from scratch (ADR 0005), with one orthographic camera
looking straight down at the Panel and one shared light rig, then renders
each Component's Frames into out/<name>/frames/<id>/. It records what it
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
from parts import BUILDERS, PX  # noqa: E402

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
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    if quality == "final":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 128
        scene.cycles.use_denoising = True
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        if any(d.type == "METAL" for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == "METAL"
            scene.cycles.device = "GPU"
    else:
        scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"


def build_world(spec):
    light = spec.get("light", {})
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nodes = world.node_tree.nodes
    env = nodes.new("ShaderNodeTexEnvironment")
    hdri = Path(bpy.utils.system_resource("DATAFILES", path="studiolights")) / "world" / light.get("hdri", "studio.exr")
    env.image = bpy.data.images.load(str(hdri))
    background = nodes["Background"]
    background.inputs["Strength"].default_value = light.get("hdri_strength", 0.25)
    world.node_tree.links.new(env.outputs["Color"], background.inputs["Color"])


def build_key_light(spec):
    """The key, from the top-left at `key_angle_deg` above the Panel: a sun
    for crisp shadows, and a large softbox in the same direction so glossy
    surfaces show a soft highlight on their top-left shoulders."""
    light = spec.get("light", {})
    elevation = math.radians(light.get("key_angle_deg", 45))
    toward_light = Vector((-1, 1, 0)).normalized() * math.cos(elevation) + Vector((0, 0, math.sin(elevation)))
    aim = toward_light.to_track_quat("Z", "Y").to_euler()

    sun = bpy.data.lights.new("Key", "SUN")
    sun.energy = light.get("key_energy", 2.5)
    sun.angle = math.radians(light.get("key_softness_deg", 8))
    key = bpy.data.objects.new("Key", sun)
    key.rotation_euler = aim
    bpy.context.scene.collection.objects.link(key)

    area = bpy.data.lights.new("Softbox", "AREA")
    area.shape = "DISK"
    area.size = 12
    area.energy = light.get("softbox_energy", 15000)
    softbox = bpy.data.objects.new("Softbox", area)
    softbox.location = toward_light * 15
    softbox.rotation_euler = aim
    bpy.context.scene.collection.objects.link(softbox)


def build_camera():
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    camera = bpy.data.objects.new("Camera", data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def frame_camera(camera, scene, center_xy, size_px, scale):
    """Point the camera straight down at a square region of the Panel."""
    camera.location = (center_xy[0], center_xy[1], 10)
    camera.rotation_euler = (0, 0, 0)
    camera.data.ortho_scale = size_px * PX
    scene.render.resolution_x = round(size_px * scale)
    scene.render.resolution_y = round(size_px * scale)


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


def render_component(scene, camera, comp, root, extent, out_dir, scale, quality):
    """Render one Component's Frames; return its entry for render.json."""
    size = math.ceil(extent) + 2 * comp.get("margin", 4)
    frame_camera(camera, scene, root.location.xy, size, scale)
    frames_dir = out_dir / "frames" / comp["id"]
    frames_dir.mkdir(parents=True, exist_ok=True)
    angles = frame_angles(comp, quality)
    for i, angle in enumerate(angles):
        # Spec angles are clockwise from 12 o'clock as seen on screen; Blender's +Z rotation is counter-clockwise.
        root.rotation_euler.z = -math.radians(angle)
        scene.render.filepath = str(frames_dir / f"{comp['id']}_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    x, y = comp["pos"]
    return {
        "id": comp["id"],
        "type": comp["type"],
        "bipolar": bool(comp.get("bipolar")),
        "angles": angles,
        "bounds": [x - size / 2, y - size / 2, size, size],
    }



def main():
    spec_path, final = parse_args()
    spec = json.loads(spec_path.read_text())
    quality = "final" if final else "draft"
    scale = spec["panel"].get("scale", 2) if quality == "final" else 1
    out_dir = REPO / "out" / spec["name"]

    scene = reset_scene()
    set_quality(scene, quality)
    build_world(spec)
    build_key_light(spec)
    camera = build_camera()

    # Frames left from an earlier Render would be packed as if they were new.
    shutil.rmtree(out_dir / "frames", ignore_errors=True)
    wear = spec.get("wear", 0.3)
    built = {comp["id"]: BUILDERS[comp["type"]](spec, comp, wear) for comp in spec["components"]}
    rendered = []
    for comp in spec["components"]:
        for other_id, (other, _) in built.items():
            hidden = other_id != comp["id"]
            for obj in [other, *other.children_recursive]:
                obj.hide_render = hidden
        root, extent = built[comp["id"]]
        rendered.append(render_component(scene, camera, comp, root, extent, out_dir, scale, quality))

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
