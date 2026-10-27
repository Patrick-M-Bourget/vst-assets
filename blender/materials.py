"""Material presets, with Wear.

Wear (0..1) breaks up each surface's roughness with noise, so a glossy
knob dulls where fingers go and paint loses its even sheen. 0.3 is light
vintage.
"""

import bpy

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
}


def srgb_to_linear(hex_color):
    """'#rrggbb' to linear RGB, as Blender's colour inputs expect."""
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)


def make(preset, wear, color=None):
    """A new material from a preset. `color` ('#rrggbb') overrides the preset's."""
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
