import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import lookdev  # noqa: E402


def record(**extra):
    return {"scale": 2, "panel": {"size": [300, 100]},
            "components": [{"id": "gain", "bounds": [10, 10, 40, 40]}, {"id": "vu", "bounds": [150, 30, 20, 40]}],
            **extra}


class CloseUps(unittest.TestCase):
    def test_one_tile_per_part_at_the_close_up_height(self):
        row = Image.new("RGBA", (600, 200), (50, 50, 50, 255))
        tiles = lookdev.close_ups(row, record())
        self.assertEqual(len(tiles), 2)
        self.assertTrue(all(t.height == lookdev.CLOSE_UP for t in tiles))

    def test_a_vu_meter_is_shown_by_its_overlay(self):
        row = Image.new("RGBA", (600, 200), (50, 50, 50, 255))
        rec = record(overlays=[{"id": "vu_glass", "bounds": [120, 10, 100, 80]}])
        tiles = lookdev.close_ups(row, rec)
        self.assertEqual(len(tiles), 2)  # gain, and the VU by its bezel, not its needle
        self.assertGreater(tiles[1].width, tiles[1].height)


class Flow(unittest.TestCase):
    def test_wraps_to_the_width(self):
        images = [Image.new("RGBA", (100, 50)) for _ in range(5)]
        canvas = lookdev.flow(images, 250, gap=10)
        self.assertEqual(canvas.size, (250, 50 * 3 + 10 * 2))


class Build(unittest.TestCase):
    def test_writes_now_before_and_close_ups(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "render.json").write_text(json.dumps(record()))
            Image.new("RGBA", (600, 600), (60, 60, 60, 255)).save(out / "contact_sheet.png")
            Image.new("RGBA", (600, 200), (90, 90, 90, 255)).save(out / "before.png")
            sheet, now = lookdev.build(out)
            self.assertEqual(now.size, (600, 200))
            self.assertGreater(sheet.height, 3 * 200)


if __name__ == "__main__":
    unittest.main()
