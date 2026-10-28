"""The look-dev sheet: judge a look change against the yardstick (#28).

    python3 tools/lookdev.py out/lookdev [--keep-before]

Reads a packed Render (normally of specs/lookdev.json) and writes
out/<name>/sheet.png: the Panel as rendered now, the same Panel from the
last time --keep-before was given (out/<name>/before.png), a close-up of
every part at full Scale, and the Refs, which for look-dev are the
yardstick screenshots in refs/lookdev/. Never commit the sheet: it carries
the Refs (ADR 0003).

--keep-before saves this render as the new before.png, after writing the sheet.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

WIDTH = 2200
GAP = 16
CLOSE_UP = 300  # px: the height each part's close-up is scaled to
BACKGROUND = (236, 236, 232, 255)
INK = (30, 30, 30, 255)


def panel_row(sheet_path, record):
    """The contact sheet's first row: the Panel with every part at its first Frame."""
    sheet = Image.open(sheet_path).convert("RGBA")
    h = round(record["panel"]["size"][1] * record["scale"])
    return sheet.crop((0, 0, sheet.width, h))


def close_ups(row, record, pad=6):
    """Each Component cut out of `row` with a little Panel around it, all at one height."""
    scale = record["scale"]
    tiles = []
    # A VU Meter's Frame is just its needle; its close-up is the whole bezel, its Overlay.
    covered = {o["id"].rsplit("_glass", 1)[0] for o in record.get("overlays", [])}
    items = [c for c in record["components"] if c["id"] not in covered] + record.get("overlays", [])
    for comp in items:
        x, y, w, h = comp["bounds"]
        box = [round((x - pad) * scale), round((y - pad) * scale), round((x + w + pad) * scale), round((y + h + pad) * scale)]
        box = [max(0, box[0]), max(0, box[1]), min(row.width, box[2]), min(row.height, box[3])]
        tile = row.crop(box)
        tiles.append(tile.resize((round(tile.width * CLOSE_UP / tile.height), CLOSE_UP), Image.LANCZOS))
    return tiles


def flow(images, width, gap=GAP):
    """Lay `images` left to right, wrapping to new rows, inside `width`; return the canvas."""
    rows, current, used = [], [], 0
    for im in images:
        if current and used + gap + im.width > width:
            rows.append(current)
            current, used = [], 0
        current.append(im)
        used += (gap if used else 0) + im.width
    if current:
        rows.append(current)
    height = sum(max(im.height for im in r) for r in rows) + gap * (len(rows) - 1)
    canvas = Image.new("RGBA", (width, max(height, 1)), BACKGROUND)
    y = 0
    for r in rows:
        x = 0
        for im in r:
            canvas.alpha_composite(im, (x, y))
            x += im.width + gap
        y += max(im.height for im in r) + gap
    return canvas


def fit(image, width):
    return image.resize((width, round(image.height * width / image.width)), Image.LANCZOS) if image.width > width else image


def labelled(title, image):
    """`image` under a one-line title."""
    out = Image.new("RGBA", (image.width, image.height + 28), BACKGROUND)
    ImageDraw.Draw(out).text((0, 6), title, fill=INK)
    out.alpha_composite(image, (0, 28))
    return out


def build(out_dir):
    out_dir = Path(out_dir)
    record = json.loads((out_dir / "render.json").read_text())
    after = panel_row(out_dir / "contact_sheet.png", record)
    sections = [labelled("NOW", fit(after, WIDTH))]
    before = out_dir / "before.png"
    if before.exists():
        sections.append(labelled("BEFORE", fit(Image.open(before).convert("RGBA"), WIDTH)))
    sections.append(labelled("CLOSE-UPS (full Scale)", flow(close_ups(after, record), WIDTH)))
    refs = [Path(p) for p in record.get("refs", []) if Path(p).exists()]
    if refs:
        thumbs = [fit(Image.open(p).convert("RGBA"), (WIDTH - GAP * 2) // 3) for p in refs]
        sections.append(labelled("YARDSTICK (local only, never commit)", flow(thumbs, WIDTH)))
    height = sum(s.height for s in sections) + GAP * (len(sections) + 1)
    sheet = Image.new("RGBA", (WIDTH + GAP * 2, height), BACKGROUND)
    y = GAP
    for s in sections:
        sheet.alpha_composite(s, (GAP, y))
        y += s.height + GAP
    return sheet, after


def main():
    args = sys.argv[1:]
    keep = "--keep-before" in args
    paths = [a for a in args if a != "--keep-before"]
    if len(paths) != 1:
        sys.exit("usage: python3 tools/lookdev.py out/<name> [--keep-before]")
    out_dir = Path(paths[0])
    sheet, after = build(out_dir)
    sheet.convert("RGB").save(out_dir / "sheet.png")
    if keep:
        after.save(out_dir / "before.png")
    print(f"wrote {out_dir / 'sheet.png'}" + (" and saved this render as before.png" if keep else ""))


if __name__ == "__main__":
    main()
