import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import refboard  # noqa: E402


def two_tone(size=(120, 80), left=(200, 30, 30), right=(20, 40, 160), split=0.75):
    im = Image.new("RGB", size, right)
    im.paste(left, (0, 0, int(size[0] * split), size[1]))
    return im


class RefboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dominant_colours_come_most_common_first(self):
        colours = refboard.dominant_colours(two_tone(), count=4)
        self.assertEqual(colours[:2], ["#c81e1e", "#1428a0"])

    def test_moodboard_shows_every_ref_with_its_swatches(self):
        paths = []
        for i in range(3):
            paths.append(self.root / f"ref{i}.png")
            two_tone().save(paths[-1])
        board, swatches = refboard.moodboard(paths)
        self.assertEqual(board.mode, "RGB")
        self.assertEqual(board.size, (2 * refboard.TILE[0], 2 * (refboard.TILE[1] + refboard.SWATCH)))
        self.assertEqual(list(swatches), ["ref0.png", "ref1.png", "ref2.png"])
        self.assertEqual(swatches["ref0.png"][0], "#c81e1e")


if __name__ == "__main__":
    unittest.main()
