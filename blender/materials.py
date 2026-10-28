"""Material presets, with Wear.

Wear (0..1) breaks up each surface's roughness with noise, so a glossy
knob dulls where fingers go and paint loses its even sheen. 0.3 is light
vintage.

A flat surface can take an image `texture` in place of its colour,
stretched over an area of the Panel.
"""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parent.parent

PRESETS = {
    "bakelite_black": {"color": "#050505", "roughness": 0.18, "coat": 0.35, "relief": ("noise", 400, 0.15)},
    "chrome": {"color": "#e8e8e8", "metallic": 1.0, "roughness": 0.08, "relief": ("noise", 900, 0.08)},
    # Zinc-plated hardware. Fully metallic: the reflection rig (render.py)
    # gives metal something to mirror from straight above.
    "zinc": {"color": "#a4a6a6", "metallic": 1.0, "roughness": 0.3, "relief": ("noise", 600, 0.15)},
    "brushed_aluminium": {"color": "#c8c8c8", "metallic": 1.0, "roughness": 0.3, "anisotropic": 0.8},
    "powder_coat": {"color": "#c4c6c4", "roughness": 0.5, "relief": ("noise", 60, 0.2)},  # orange peel
    "paint_white": {"color": "#e6e2d6", "roughness": 0.32},  # satin print, a touch glossier than the plate
    # Toggle hardware.
    "nickel": {"color": "#d4d1ca", "metallic": 1.0, "roughness": 0.16, "relief": ("noise", 900, 0.08)},
    "jewel_red": {"color": "#d0201a", "roughness": 0.03, "transmission": 1.0},
    "bezel_grey": {"color": "#3c3e40", "roughness": 0.3, "coat": 0.2},
    "glass": {"color": "#ffffff", "roughness": 0.0, "transmission": 1.0},
    "meter_face": {"color": "#ead9a8", "roughness": 0.6, "relief": ("noise", 250, 0.1)},  # paper tooth
    # A knob cap spun from aluminium: brushed in circles.
    "spun_aluminium": {"color": "#dcdcd8", "metallic": 1.0, "roughness": 0.18, "anisotropic": 0.9,
                       "relief": ("rings", 90, 0.35)},  # lathe grooves
    # A tinted clear-plastic knob skirt: the Panel shows through it, darkened.
    "smoked_acrylic": {"color": "#9a9aa0", "roughness": 0.04, "transmission": 1.0, "coat": 0.5},
}


def srgb_to_linear(hex_color):
    """'#rrggbb' to linear RGB, as Blender's colour inputs expect."""
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)


def make(preset, wear, color=None, texture=None, area=None, grain=0.0):
    """A new material from a preset. `color` ('#rrggbb') overrides the preset's.
    `texture` (an image path, relative to the repo) replaces the colour,
    stretched over `area`: (x, y, w, h) in Blender units, its bottom-left corner first.
    `grain` (0-1) brushes the colour with fine streaks along X, as on a brushed faceplate."""
    p = PRESETS[preset]
    mat = bpy.data.materials.new(preset)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*srgb_to_linear(color or p["color"]), 1)
    bsdf.inputs["Metallic"].default_value = p.get("metallic", 0.0)
    bsdf.inputs["Coat Weight"].default_value = p.get("coat", 0.0)
    bsdf.inputs["Coat Roughness"].default_value = 0.05 + 0.3 * wear
    bsdf.inputs["Transmission Weight"].default_value = p.get("transmission", 0.0)
    if p.get("anisotropic"):
        bsdf.inputs["Anisotropic"].default_value = p["anisotropic"]
        # Spun metal: brushed in circles around the knob's axis.
        tangent = nodes.new("ShaderNodeTangent")
        tangent.direction_type = "RADIAL"
        tangent.axis = "Z"
        links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])

    if texture:
        stretch(mat, bsdf, texture, area)
    elif grain:
        brush(mat, bsdf, grain)
    if grain and not texture:
        relief(mat, bsdf, ("streaks", 1, 0.25 * grain))
    elif p.get("relief"):
        relief(mat, bsdf, p["relief"])

    roughness = p["roughness"]
    coords = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    # Smudges and dull patches, not grit.
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 3.0
    spread = nodes.new("ShaderNodeMapRange")
    spread.inputs["To Min"].default_value = max(0.0, roughness - 0.05 * wear)
    spread.inputs["To Max"].default_value = min(1.0, roughness + 0.25 * wear)
    links.new(coords.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], spread.inputs["Value"])
    links.new(spread.outputs["Result"], bsdf.inputs["Roughness"])
    return mat


def relief(mat, bsdf, spec):
    """Micro-relief through a Bump node, so highlights break up the way they
    do on real surfaces. `spec` is (kind, scale, strength): `noise` (grain,
    orange peel, polishing marks; scale is features per Blender unit),
    `rings` (lathe grooves around the part's own axis), or `streaks`
    (brushing along X, matching brush())."""
    kind, scale, strength = spec
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    if kind == "rings":
        tex = nodes.new("ShaderNodeTexWave")
        tex.wave_type = "RINGS"
        tex.rings_direction = "Z"
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Distortion"].default_value = 0.6
        tex.inputs["Detail"].default_value = 2.0
        source = tex.outputs["Fac"]
        links.new(coords.outputs["Object"], tex.inputs["Vector"])
    else:
        tex = nodes.new("ShaderNodeTexNoise")
        tex.inputs["Detail"].default_value = 4.0
        tex.inputs["Scale"].default_value = 1.0 if kind == "streaks" else scale
        source = tex.outputs["Fac"]
        if kind == "streaks":
            mapping = nodes.new("ShaderNodeMapping")
            mapping.inputs["Scale"].default_value = (0.4, 70, 1)
            links.new(coords.outputs["Object"], mapping.inputs["Vector"])
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        else:
            links.new(coords.outputs["Object"], tex.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.002
    links.new(source, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def brush(mat, bsdf, grain):
    """Multiply the base colour by noise stretched along X: streaks a few px
    apart at 2x and hundreds long, at any Scale since it's procedural."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.4, 70, 1)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 6.0
    shade = nodes.new("ShaderNodeMapRange")
    shade.inputs["From Min"].default_value = 0.3
    shade.inputs["From Max"].default_value = 0.7
    shade.inputs["To Min"].default_value = 1 - grain
    shade.inputs["To Max"].default_value = 1 + grain
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
    links.new(coords.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], shade.inputs["Value"])
    links.new(shade.outputs["Result"], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])


def stretch(mat, bsdf, texture, area):
    """Feed the image at `texture` into the base colour, covering `area` once."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(str(REPO / texture), check_existing=True)
    image.extension = "EXTEND"
    x, y, w, h = area
    position = nodes.new("ShaderNodeNewGeometry")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1 / w, 1 / h, 1)
    mapping.inputs["Location"].default_value = (-x / w, -y / h, 0)
    links.new(position.outputs["Position"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], image.inputs["Vector"])
    links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(image.outputs["Color"], bsdf.inputs["Emission Color"])  # a backlit face glows in its own colours
