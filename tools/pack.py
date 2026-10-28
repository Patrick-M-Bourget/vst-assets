"""Pack a Render into the files a plugin ships, and check them.

    python3 tools/pack.py out/<name>

Reads out/<name>/render.json (written by blender/render.py) and the Frames,
Backplate and Overlays beside it. Writes into out/<name>/final/ one
Filmstrip per Component, the Backplate, the Overlays and manifest.json, and
into out/<name>/ the Contact Sheet, a preview GIF per Component, and, when
the Spec lists Refs, compare.png: the Contact Sheet beside the moodboard.

Exits 1, listing every problem, when the Frames don't match render.json.
"""

import json
import math
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageMath

import refboard

MAX_TEXTURE = 16384
EDGE_ALPHA = 24  # above this on a Frame's border, something runs off its edge; below, render noise
FEATHER = 3  # px at 1x over which a Frame's alpha fades to nothing at its border
PREVIEW_BACKGROUND = (128, 128, 128, 255)


class PackError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


def load(path):
    """Open an image fully and close its file."""
    with Image.open(path) as image:
        image.load()
    return image


def frame_values(comp):
    """What each Frame shows: a Knob's angles, or a Toggle's or Lamp's States."""
    return ("angles", comp["angles"]) if "angles" in comp else ("states", comp["states"])


def check_frames(comp, frame_paths, scale):
    """Every problem with one Component's Frames, as messages."""
    cid = comp["id"]
    expected = len(frame_values(comp)[1])
    if len(frame_paths) != expected:
        return [f"{cid}: {len(frame_paths)} Frames, expected {expected}"]

    errors = []
    if comp.get("bipolar"):
        if expected % 2 == 0:
            errors.append(f"{cid}: a Bipolar Knob needs an odd Frame count, has {expected}")
        elif abs(centre := comp["angles"][expected // 2]) > 1e-6:
            errors.append(f"{cid}: centre Frame is at {centre:g}°, not 0°")

    size = round(comp["bounds"][2] * scale), round(comp["bounds"][3] * scale)
    previous = None
    for path in frame_paths:
        frame = load(path)
        if frame.size != size:
            errors.append(f"{path.name} is {frame.size[0]}x{frame.size[1]}, expected {size[0]}x{size[1]}")
            previous = None
            continue
        if frame.mode != "RGBA":
            errors.append(f"{path.name} has no alpha channel")
            previous = None
            continue
        if frame.getchannel("A").getextrema()[1] == 0:
            errors.append(f"{path.name} is fully transparent")
        # Compare every band: getbbox() on an RGBA difference only looks at alpha.
        elif previous is not None and all(hi == 0 for _, hi in ImageChops.difference(frame, previous).getextrema()):
            errors.append(f"{path.name} is identical to the Frame before it")
        previous = frame
    return errors


def check_image(path, size):
    image = load(path)
    if image.size != size:
        return [f"{path.name} is {image.size[0]}x{image.size[1]}, expected {size[0]}x{size[1]}"]
    if image.mode != "RGBA":
        return [f"{path.name} has no alpha channel"]
    return []


def edge_alpha(frame):
    """The most opaque pixel on a Frame's border."""
    alpha = frame.getchannel("A")
    w, h = alpha.size
    border = [alpha.crop(box) for box in [(0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h)]]
    return max(b.getextrema()[1] for b in border)


def feather(frame, width):
    """Fade alpha to zero over `width` px at the border, so faint render noise
    there can't draw a seam on the Backplate."""
    w, h = frame.size
    ramp = Image.new("L", (w, h), 0)
    for i in range(1, width):
        ramp.paste(round(255 * i / width), (i, i, w - i, h - i))
    ramp.paste(255, (width, width, w - width, h - width))
    frame = frame.copy()
    frame.putalpha(ImageChops.multiply(frame.getchannel("A"), ramp))
    return frame


def stitch(frame_paths, feather_px):
    frames = [feather(load(p), feather_px) for p in frame_paths]
    w, h = frames[0].size
    strip = Image.new("RGBA", (w, h * len(frames)))
    for i, frame in enumerate(frames):
        strip.paste(frame, (0, h * i))
    return strip


def light_falloff(image, strength, vignette):
    """`image` under studio light: brighter toward the top-left and darker
    toward the bottom-right by `strength`, darker toward the edges by
    `vignette`. Done here, not in the material: on a dark plate almost all
    the brightness is reflection, which a colour change barely moves."""
    if not strength and not vignette:
        return image
    w, h = image.size
    sw, sh = max(2, w // 8), max(2, h // 8)
    factor = Image.new("F", (sw, sh))
    for j in range(sh):
        v = (j + 0.5) / sh - 0.5  # -0.5 at the top
        for i in range(sw):
            u = (i + 0.5) / sw - 0.5
            tilt = 1 - strength * (u + v)  # 1 + strength at the top-left corner, 1 - strength at the bottom-right
            # Distance from the centre, the long side squeezed so the edges darken evenly.
            d = 2 * math.hypot(u * min(1.0, w / h) if w < h else u * 0.5 * w / h, v)
            edge = 1 - vignette * min(1.0, max(0.0, (d - 0.5) / 0.6)) ** 2
            factor.putpixel((i, j), tilt * edge)
    factor = factor.resize((w, h), Image.BILINEAR)
    bands = image.split()
    lit = [ImageMath.lambda_eval(lambda e: e["convert"](e["b"] * e["f"], "L"), b=band, f=factor) for band in bands[:3]]
    return Image.merge(image.mode, lit + list(bands[3:]))


def contact_sheet(record, backplate, strips, overlays):
    """The Panel three times, stacked: every Component at its first, middle and
    last Frame, cut from the Filmstrips that ship, with the Overlays on top."""
    scale = record["scale"]
    w, h = (round(d * scale) for d in record["panel"]["size"])
    sheet = Image.new("RGBA", (w, h * 3), PREVIEW_BACKGROUND)
    for row in range(3):
        if backplate is not None:
            sheet.alpha_composite(backplate, (0, h * row))
        for comp, strip, count in strips:
            index = [0, count // 2, count - 1][row]
            fh = strip.height // count
            frame = strip.crop((0, fh * index, strip.width, fh * (index + 1)))
            x, y = comp["bounds"][:2]
            sheet.alpha_composite(frame, (round(x * scale), round(y * scale) + h * row))
        for overlay, image in overlays:
            x, y = overlay["bounds"][:2]
            sheet.alpha_composite(image, (round(x * scale), round(y * scale) + h * row))
    return sheet


def compare(sheet, refs, warnings):
    """The Contact Sheet beside a moodboard of the Refs found on this machine, or None."""
    found = [Path(p) for p in refs if Path(p).exists()]
    missing = ", ".join(Path(p).name for p in refs if not Path(p).exists())
    if not found:
        warnings.append(f"no Refs found ({missing}): compare.png not written")
        return None
    if missing:
        warnings.append(f"Refs missing ({missing}): compare.png shows the rest")
    board, _ = refboard.moodboard(found)
    board = board.resize((round(board.width * sheet.height / board.height), sheet.height), Image.LANCZOS)
    image = Image.new("RGB", (sheet.width + board.width, sheet.height))
    image.paste(sheet.convert("RGB"), (0, 0))
    image.paste(board, (sheet.width, 0))
    return image


def preview_gif(frame_paths, path):
    frames = []
    for p in frame_paths:
        image = load(p)
        frame = Image.new("RGBA", image.size, PREVIEW_BACKGROUND)
        frame.alpha_composite(image)
        frames.append(frame.convert("RGB"))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=40, loop=0)


def pack(out_dir):
    """Check and pack one Render; return the Manifest. Raises PackError listing every problem."""
    out_dir = Path(out_dir)
    record = json.loads((out_dir / "render.json").read_text())
    name, scale = record["name"], record["scale"]
    panel_size = tuple(round(d * scale) for d in record["panel"]["size"])

    errors = []
    frames = {}
    for comp in record["components"]:
        frames[comp["id"]] = sorted((out_dir / "frames" / comp["id"]).glob("*.png"))
        errors += check_frames(comp, frames[comp["id"]], scale)
    backplate_path = out_dir / "backplate.png"
    if backplate_path.exists():
        errors += check_image(backplate_path, panel_size)
    for overlay in record.get("overlays", []):
        size = round(overlay["bounds"][2] * scale), round(overlay["bounds"][3] * scale)
        errors += check_image(out_dir / "overlays" / f"{overlay['id']}.png", size)
    if errors:
        raise PackError(errors)

    final = out_dir / "final"
    shutil.rmtree(final, ignore_errors=True)
    final.mkdir()
    manifest = {"name": name, "scale": scale, "panel_size": record["panel"]["size"], "components": [], "warnings": []}

    backplate = None
    if backplate_path.exists():
        file = f"bg_{name}_{scale}x.png"
        backplate = light_falloff(load(backplate_path), *record.get("falloff", [0, 0]))
        backplate.save(final / file)
        manifest["backplate"] = {"file": file, "size": list(panel_size)}

    strips = []
    for comp in record["components"]:
        strip = stitch(frames[comp["id"]], FEATHER * scale)
        strips.append((comp, strip, len(frames[comp["id"]])))
        count = len(frames[comp["id"]])
        file = f"{comp['type']}_{comp['id']}_{count}f_{scale}x.png"
        strip.save(final / file, optimize=True)
        cut = [(p, a) for p in frames[comp["id"]] if (a := edge_alpha(load(p))) > EDGE_ALPHA]
        if cut:
            path, alpha = max(cut, key=lambda c: c[1])
            manifest["warnings"].append(
                f"{path.name} reaches its edge (alpha {alpha}): a shadow or part is cut off; widen the Frame")
        if max(strip.size) > MAX_TEXTURE:
            manifest["warnings"].append(
                f"{file} is {strip.size[0]}x{strip.size[1]}, over the {MAX_TEXTURE} px texture limit many hosts have")
        key, values = frame_values(comp)
        manifest["components"].append({
            "id": comp["id"],
            "type": comp["type"],
            "file": file,
            "frame_size": [strip.size[0], strip.size[1] // count],
            "frames": count,
            key: [round(a, 4) for a in values] if key == "angles" else values,
            "bounds": comp["bounds"],
            **({"scale_marks": comp["scale_marks"]} if "scale_marks" in comp else {}),
        })
        preview_gif(frames[comp["id"]], out_dir / f"preview_{comp['id']}.gif")

    if record.get("overlays"):
        manifest["overlays"] = []
    overlays = []
    for overlay in record.get("overlays", []):
        file = f"overlay_{overlay['id']}_{scale}x.png"
        shutil.copyfile(out_dir / "overlays" / f"{overlay['id']}.png", final / file)
        manifest["overlays"].append({"id": overlay["id"], "file": file, "bounds": overlay["bounds"]})
        overlays.append((overlay, load(final / file)))

    (final / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sheet = contact_sheet(record, backplate, strips, overlays)
    sheet.save(out_dir / "contact_sheet.png")
    if record.get("refs"):
        side_by_side = compare(sheet, record["refs"], manifest["warnings"])
        if side_by_side:
            side_by_side.save(out_dir / "compare.png")
        (final / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 tools/pack.py out/<name>")
    try:
        manifest = pack(sys.argv[1])
    except PackError as e:
        print("pack failed:", *e.errors, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    for warning in manifest["warnings"]:
        print("warning:", warning, file=sys.stderr)
    print(f"packed {len(manifest['components'])} Filmstrips into {Path(sys.argv[1]) / 'final'}")


if __name__ == "__main__":
    main()
