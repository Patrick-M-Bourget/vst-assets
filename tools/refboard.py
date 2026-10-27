"""Turn a Spec's Refs into a moodboard with dominant-colour swatches.

    python3 tools/refboard.py specs/<name>.json

Reads the Refs listed in the Spec's `notes.refs` from refs/<name>/, writes
out/<name>/moodboard.png, and prints each Ref's swatches as hex colours to
write the Look Brief from. Everything stays under gitignored out/ (ADR 0003).
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
TILE = (640, 400)  # each Ref is fitted into this box
SWATCH = 64  # height of the swatch row under each Ref
SWATCHES = 6
COLUMNS = 2
BACKGROUND = (40, 40, 40)


def dominant_colours(image, count=SWATCHES):
    """The image's `count` main colours as '#rrggbb', most common first."""
    small = image.convert("RGB")
    small.thumbnail((200, 200))
    quantized = small.quantize(colors=count, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    used = sorted(quantized.getcolors(), reverse=True)  # (pixel count, palette index)
    return ["#{:02x}{:02x}{:02x}".format(*palette[i * 3:i * 3 + 3]) for _, i in used]


def moodboard(paths):
    """A grid of the Refs, each over its swatches. Returns (image, {file name: swatches})."""
    rows = -(-len(paths) // COLUMNS)
    tile_h = TILE[1] + SWATCH
    board = Image.new("RGB", (TILE[0] * min(COLUMNS, len(paths)), tile_h * rows), BACKGROUND)
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=14)
    swatches = {}
    for n, path in enumerate(paths):
        x, y = TILE[0] * (n % COLUMNS), tile_h * (n // COLUMNS)
        with Image.open(path) as ref:
            ref = ref.convert("RGB")
        swatches[Path(path).name] = colours = dominant_colours(ref)
        ref.thumbnail(TILE)
        board.paste(ref, (x + (TILE[0] - ref.width) // 2, y + (TILE[1] - ref.height) // 2))
        width = TILE[0] // len(colours)
        for i, colour in enumerate(colours):
            box = (x + width * i, y + TILE[1], x + width * (i + 1) - 1, y + tile_h - 1)
            draw.rectangle(box, fill=colour)
            light = sum(int(colour[k:k + 2], 16) for k in (1, 3, 5)) > 384
            draw.text((box[0] + 6, box[1] + 6), colour, fill=(0, 0, 0) if light else (255, 255, 255), font=font)
    return board, swatches


def ref_paths(spec):
    """Where the Spec's Refs live on this machine."""
    return [REPO / "refs" / spec["name"] / name for name in spec.get("notes", {}).get("refs", [])]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 tools/refboard.py specs/<name>.json")
    spec = json.loads(Path(sys.argv[1]).read_text())
    paths = ref_paths(spec)
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        sys.exit(f"missing from refs/{spec['name']}/: {', '.join(missing)}")
    if not paths:
        sys.exit("the Spec lists no Refs in notes.refs")
    board, swatches = moodboard(paths)
    out = REPO / "out" / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    board.save(out / "moodboard.png")
    for name, colours in swatches.items():
        print(f"{name}: {' '.join(colours)}")
    print(f"wrote {out / 'moodboard.png'}")


if __name__ == "__main__":
    main()
