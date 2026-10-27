"""Render a Spec in headless Blender.

    blender -b --factory-startup -P blender/render.py -- specs/<name>.json

Builds the scene from scratch (ADR 0005), with one orthographic camera
looking straight down at the Panel and one shared light rig, then renders
each Component's Frames into out/<name>/frames/<id>/.

Units: 1 Blender unit is 100 px at 1x. Spec positions are 1x pixels from
the Panel's top-left corner; the Panel lies in the XY plane facing +Z.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PX = 0.01  # Blender units per 1x pixel
REPO = Path(__file__).resolve().parent.parent
DRAFT_MAX_FRAMES = 16


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 1:
        sys.exit("usage: blender -b --factory-startup -P blender/render.py -- specs/<name>.json")
    return Path(argv[0])


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
    else:
        scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"


def panel_to_world(spec, x, y):
    """1x Panel pixels (top-left origin, y down) to Blender XY (centre origin, y up)."""
    w, h = spec["panel"]["size"]
    return (x - w / 2) * PX, (h / 2 - y) * PX


def build_world(spec):
    light = spec.get("light", {})
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nodes = world.node_tree.nodes
    env = nodes.new("ShaderNodeTexEnvironment")
    hdri = Path(bpy.utils.system_resource("DATAFILES", path="studiolights")) / "world" / light.get("hdri", "studio.exr")
    env.image = bpy.data.images.load(str(hdri))
    background = nodes["Background"]
    background.inputs["Strength"].default_value = light.get("hdri_strength", 0.4)
    world.node_tree.links.new(env.outputs["Color"], background.inputs["Color"])


def build_key_light(spec):
    """A sun from the top-left, `key_angle_deg` above the Panel."""
    light = spec.get("light", {})
    elevation = math.radians(light.get("key_angle_deg", 45))
    data = bpy.data.lights.new("Key", "SUN")
    data.energy = light.get("key_energy", 3.0)
    data.angle = math.radians(light.get("key_softness_deg", 8))
    key = bpy.data.objects.new("Key", data)
    bpy.context.scene.collection.objects.link(key)
    toward_light = Vector((-1, 1, 0)).normalized() * math.cos(elevation) + Vector((0, 0, math.sin(elevation)))
    key.rotation_euler = toward_light.to_track_quat("Z", "Y").to_euler()


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


def material(name, color, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_knob(spec, comp):
    """Smoke-test Knob: a bevelled cylinder with a pointer bar. Returns its root object."""
    radius = comp["diameter"] / 2 * PX
    height = radius * 0.8
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=height, location=(0, 0, height / 2))
    body = bpy.context.object
    body.name = f"{comp['id']}_body"
    bevel = body.modifiers.new("Bevel", "BEVEL")
    bevel.width = radius * 0.08
    bevel.segments = 4
    bpy.ops.object.shade_smooth()
    body.data.materials.append(material("knob_body", (0.05, 0.05, 0.05), roughness=0.35))

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, radius * 0.55, height + 0.002))
    pointer = bpy.context.object
    pointer.name = f"{comp['id']}_pointer"
    pointer.scale = (radius * 0.08, radius * 0.7, 0.004)
    pointer.data.materials.append(material("pointer", (0.9, 0.9, 0.88), roughness=0.4))
    pointer.parent = body

    body.location.xy = panel_to_world(spec, *comp["pos"])
    return body


def frame_angles(comp, quality):
    start, end = comp.get("angle", [-150, 150])
    count = comp.get("frames", 128)
    if quality != "final":
        count = min(count, DRAFT_MAX_FRAMES)
    if count == 1:
        return [start]
    return [start + (end - start) * i / (count - 1) for i in range(count)]


def render_component(scene, camera, spec, comp, root, out_dir, scale, quality):
    margin = comp.get("margin", 4)
    size = comp["diameter"] + 2 * margin
    frame_camera(camera, scene, root.location.xy, size, scale)
    frames_dir = out_dir / "frames" / comp["id"]
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, angle in enumerate(frame_angles(comp, quality)):
        # Spec angles are clockwise from 12 o'clock as seen on screen; Blender's +Z rotation is counter-clockwise.
        root.rotation_euler.z = -math.radians(angle)
        scene.render.filepath = str(frames_dir / f"{comp['id']}_{i:04d}.png")
        bpy.ops.render.render(write_still=True)


BUILDERS = {"knob": build_knob}


def main():
    spec_path = parse_args()
    spec = json.loads(spec_path.read_text())
    quality = spec.get("quality", "draft")
    scale = spec["panel"].get("scale", 2) if quality == "final" else 1
    out_dir = REPO / "out" / spec["name"]

    scene = reset_scene()
    set_quality(scene, quality)
    build_world(spec)
    build_key_light(spec)
    camera = build_camera()

    roots = {comp["id"]: BUILDERS[comp["type"]](spec, comp) for comp in spec["components"]}
    for comp in spec["components"]:
        for other_id, other in roots.items():
            hidden = other_id != comp["id"]
            for obj in [other, *other.children_recursive]:
                obj.hide_render = hidden
        render_component(scene, camera, spec, comp, roots[comp["id"]], out_dir, scale, quality)


main()
