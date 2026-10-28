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
    "bakelite_black": {"color": "#050505", "roughness": 0.18, "coat": 0.35},
    "chrome": {"color": "#e8e8e8", "metallic": 1.0, "roughness": 0.08},
    # Zinc-plated hardware. Not metallic: from straight above, metal would
    # only mirror the dark studio ceiling.
    "zinc": {"color": "#a4a6a6", "roughness": 0.35},
    "brushed_aluminium": {"color": "#c8c8c8", "metallic": 1.0, "roughness": 0.3, "anisotropic": 0.8},
    "powder_coat": {"color": "#c4c6c4", "roughness": 0.55},
    "paint_white": {"color": "#e6e2d6", "roughness": 0.45},
    # Toggle hardware. Part metal only, for the same reason as zinc.
    "nickel": {"color": "#c9c6bf", "metallic": 0.6, "roughness": 0.2},
    "jewel_red": {"color": "#d0201a", "roughness": 0.03, "transmission": 1.0},
    "bezel_grey": {"color": "#3c3e40", "roughness": 0.3, "coat": 0.2},
    "glass": {"color": "#ffffff", "roughness": 0.0, "transmission": 1.0},
    "meter_face": {"color": "#ead9a8", "roughness": 0.6},
    # A knob cap spun from aluminium. Part metal only, for the same reason as zinc.
    "spun_aluminium": {"color": "#d8d8d5", "metallic": 0.7, "roughness": 0.14, "anisotropic": 0.95},
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
