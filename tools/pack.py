"""Pack a Render into the files a plugin ships, and check them.

    python3 tools/pack.py out/<name>

Reads out/<name>/render.json (written by blender/render.py) and the Frames,
Backplate and Overlays beside it. Writes into out/<name>/final/ one
Filmstrip per Component, the Backplate, the Overlays and manifest.json, and
into out/<name>/ the Contact Sheet and a preview GIF per Component.

Exits 1, listing every problem, when the Frames don't match render.json.
"""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops

MAX_TEXTURE = 16384
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


def check_frames(comp, frame_paths, scale):
    """Every problem with one Component's Frames, as messages."""
    cid = comp["id"]
    expected = len(comp["angles"])
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


def stitch(frame_paths):
    frames = [load(p) for p in frame_paths]
    w, h = frames[0].size
    strip = Image.new("RGBA", (w, h * len(frames)))
    for i, frame in enumerate(frames):
        strip.paste(frame, (0, h * i))
    return strip


def contact_sheet(record, backplate, strips):
    """The Panel three times, stacked: every Component at its first, middle and last Frame."""
    scale = record["scale"]
    w, h = (round(d * scale) for d in record["panel"]["size"])
    sheet = Image.new("RGBA", (w, h * 3), PREVIEW_BACKGROUND)
    for row in range(3):
        if backplate is not None:
            sheet.alpha_composite(backplate, (0, h * row))
        for comp, frames in strips:
            index = [0, len(frames) // 2, len(frames) - 1][row]
            x, y = comp["bounds"][:2]
            sheet.alpha_composite(load(frames[index]), (round(x * scale), round(y * scale) + h * row))
    return sheet


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
        shutil.copyfile(backplate_path, final / file)
        manifest["backplate"] = {"file": file, "size": list(panel_size)}
        backplate = load(backplate_path)

    for comp in record["components"]:
        strip = stitch(frames[comp["id"]])
        count = len(frames[comp["id"]])
        file = f"{comp['type']}_{comp['id']}_{count}f_{scale}x.png"
        strip.save(final / file, optimize=True)
        if max(strip.size) > MAX_TEXTURE:
            manifest["warnings"].append(
                f"{file} is {strip.size[0]}x{strip.size[1]}, over the {MAX_TEXTURE} px texture limit many hosts have")
        manifest["components"].append({
            "id": comp["id"],
            "type": comp["type"],
            "file": file,
            "frame_size": [strip.size[0], strip.size[1] // count],
            "frames": count,
            "angles": [round(a, 4) for a in comp["angles"]],
            "bounds": comp["bounds"],
        })
        preview_gif(frames[comp["id"]], out_dir / f"preview_{comp['id']}.gif")

    if record.get("overlays"):
        manifest["overlays"] = []
    for overlay in record.get("overlays", []):
        file = f"overlay_{overlay['id']}_{scale}x.png"
        shutil.copyfile(out_dir / "overlays" / f"{overlay['id']}.png", final / file)
        manifest["overlays"].append({"id": overlay["id"], "file": file, "bounds": overlay["bounds"]})

    (final / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    contact_sheet(record, backplate, [(c, frames[c["id"]]) for c in record["components"]]).save(out_dir / "contact_sheet.png")
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
