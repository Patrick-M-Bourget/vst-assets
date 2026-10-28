import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import pack  # noqa: E402

PANEL = [200, 100]


def knob_frame(size, angle, color=(30, 30, 30, 255)):
    """A fake Frame: a disc with a pointer at `angle` (clockwise from 12 o'clock),
    clear of the border as a real Frame's margin keeps it."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    pad = size // 5
    draw.ellipse([pad, pad, size - 1 - pad, size - 1 - pad], fill=color)
    c = size / 2
    a = math.radians(angle)
    draw.line([c, c, c + math.sin(a) * c * 0.5, c - math.cos(a) * c * 0.5], fill=(240, 240, 240, 255), width=3)
    return im


class Render:
    """Builds a fake out/<name>/ directory as blender/render.py would leave it."""

    def __init__(self, root, scale=1):
        self.dir = Path(root) / "test"
        self.scale = scale
        self.record = {"name": "test", "quality": "draft", "scale": scale, "panel": {"size": PANEL}, "components": []}

    def knob(self, id, angles, size=40, pos=(50, 50), bipolar=False, frames=None, scale_marks=None):
        x, y = pos
        self.record["components"].append({
            "id": id, "type": "knob", "bipolar": bipolar, "angles": angles,
            "bounds": [x - size / 2, y - size / 2, size, size],
            **({"scale_marks": scale_marks} if scale_marks else {}),
        })
        frames_dir = self.dir / "frames" / id
        frames_dir.mkdir(parents=True)
        px = size * self.scale
        for i, frame in enumerate(frames or [knob_frame(px, a) for a in angles]):
            frame.save(frames_dir / f"{id}_{i:04d}.png")
        return self

    def toggle(self, id, states=("off", "on"), size=30, pos=(150, 50)):
        x, y = pos
        self.record["components"].append({
            "id": id, "type": "toggle", "bipolar": False, "states": list(states),
            "bounds": [x - size / 2, y - size / 2, size, size],
        })
        frames_dir = self.dir / "frames" / id
        frames_dir.mkdir(parents=True)
        px = size * self.scale
        for i in range(len(states)):
            knob_frame(px, 180 * i).save(frames_dir / f"{id}_{i:04d}.png")
        return self

    def backplate(self, size=None):
        w, h = size or [d * self.scale for d in PANEL]
        Image.new("RGBA", (w, h), (90, 90, 95, 255)).save(self.dir / "backplate.png")
        return self

    def overlay(self, id, size=20, pos=(150, 50), color=(255, 255, 255, 40)):
        x, y = pos
        self.record.setdefault("overlays", []).append({"id": id, "bounds": [x - size / 2, y - size / 2, size, size]})
        (self.dir / "overlays").mkdir(exist_ok=True)
        Image.new("RGBA", (size * self.scale,) * 2, color).save(self.dir / "overlays" / f"{id}.png")
        return self

    def reason(self, sizes):
        """A reason-target Render: the extra backdrops beside the front Backplate."""
        self.record["target"] = "reason"
        self.record["backdrops"] = sizes
        for side, (w, h) in sizes.items():
            Image.new("RGBA", (w * self.scale, h * self.scale), (20, 20, 20, 255)).save(self.dir / f"backdrop_{side}.png")
        return self

    def refs(self, paths):
        self.record["refs"] = [str(p) for p in paths]
        return self

    def write(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "render.json").write_text(json.dumps(self.record))
        return self.dir


def linear(start, end, count):
    return [start + (end - start) * i / (count - 1) for i in range(count)]


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def assertPackFails(self, out_dir, fragment):
        with self.assertRaises(pack.PackError) as caught:
            pack.pack(out_dir)
        self.assertTrue(any(fragment in e for e in caught.exception.errors), caught.exception.errors)

    def test_stitches_frames_into_a_vertical_filmstrip(self):
        out = Render(self.root, scale=2).knob("gain", linear(-150, 150, 8)).backplate().write()
        pack.pack(out)
        strip = Image.open(out / "final" / "knob_gain_8f_2x.png")
        self.assertEqual(strip.size, (80, 640))
        self.assertEqual(strip.mode, "RGBA")
        third = Image.open(out / "frames" / "gain" / "gain_0002.png")
        self.assertEqual(strip.crop((0, 160, 80, 240)).tobytes(), third.tobytes())

    def test_writes_the_manifest(self):
        out = Render(self.root, scale=2).knob("gain", linear(-150, 150, 8), pos=(60, 40)).backplate().write()
        pack.pack(out)
        manifest = json.loads((out / "final" / "manifest.json").read_text())
        self.assertEqual(manifest["scale"], 2)
        self.assertEqual(manifest["backplate"], {"file": "bg_test_2x.png", "size": [400, 200]})
        [gain] = manifest["components"]
        self.assertEqual(gain["file"], "knob_gain_8f_2x.png")
        self.assertEqual(gain["frame_size"], [80, 80])
        self.assertEqual(gain["frames"], 8)
        self.assertEqual(gain["bounds"], [40, 20, 40, 40])
        self.assertEqual(gain["angles"][0], -150)
        self.assertEqual(gain["angles"][-1], 150)

    def test_writes_the_contact_sheet_and_previews(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 8)).backplate().write()
        pack.pack(out)
        sheet = Image.open(out / "contact_sheet.png")
        self.assertEqual(sheet.size, (200, 300))  # first, middle and last Frames, stacked
        preview = Image.open(out / "preview_gain.gif")
        self.assertEqual(preview.n_frames, 8)

    def test_contact_sheet_without_a_backplate(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).write()
        pack.pack(out)
        self.assertEqual(Image.open(out / "contact_sheet.png").size, (200, 300))
        self.assertNotIn("backplate", json.loads((out / "final" / "manifest.json").read_text()))

    def test_writes_compare_beside_the_contact_sheet_when_there_are_refs(self):
        ref = Path(self.root) / "ref.jpg"
        Image.new("RGB", (300, 200), (180, 30, 30)).save(ref)
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).backplate().refs([ref]).write()
        self.assertEqual(pack.pack(out)["warnings"], [])
        compare = Image.open(out / "compare.png")
        sheet = Image.open(out / "contact_sheet.png")
        self.assertEqual(compare.height, sheet.height)
        self.assertGreater(compare.width, sheet.width)

    def test_warns_and_skips_compare_when_refs_are_missing(self):
        # A fresh clone has no Refs: they stay on the user's machine (ADR 0003).
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).refs([Path(self.root) / "gone.jpg"]).write()
        self.assertEqual(pack.pack(out)["warnings"], ["no Refs found (gone.jpg): compare.png not written"])
        self.assertFalse((out / "compare.png").exists())

    def test_no_compare_without_refs(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).write()
        pack.pack(out)
        self.assertFalse((out / "compare.png").exists())

    def test_copies_overlays(self):
        out = Render(self.root, scale=2).knob("gain", linear(-150, 150, 4)).overlay("vu_glass").write()
        manifest = pack.pack(out)
        self.assertTrue((out / "final" / "overlay_vu_glass_2x.png").exists())
        self.assertEqual(manifest["overlays"], [{"id": "vu_glass", "file": "overlay_vu_glass_2x.png", "bounds": [140, 40, 20, 20]}])

    def test_contact_sheet_draws_overlays_above_the_filmstrips(self):
        # A VU Meter's bezel covers the foot of its needle.
        out = (Render(self.root).knob("needle", linear(-45, 45, 4), pos=(50, 50))
               .overlay("bezel", size=10, pos=(50, 50), color=(200, 0, 0, 255)).write())
        pack.pack(out)
        self.assertEqual(Image.open(out / "contact_sheet.png").getpixel((50, 50)), (200, 0, 0, 255))

    def test_lists_scale_marks_in_the_manifest(self):
        marks = [{"value": "-20", "angle": -38.6}, {"value": "0", "angle": 18.7}]
        out = Render(self.root).knob("vu", linear(-45, 45, 4), scale_marks=marks).write()
        [vu] = pack.pack(out)["components"]
        self.assertEqual(vu["scale_marks"], marks)

    def test_rejects_a_frame_count_that_differs_from_the_render(self):
        angles = linear(-150, 150, 8)
        out = Render(self.root).knob("gain", angles, frames=[knob_frame(40, a) for a in angles[:7]]).write()
        self.assertPackFails(out, "gain: 7 Frames, expected 8")

    def test_rejects_frames_of_different_sizes(self):
        frames = [knob_frame(40, -150), knob_frame(40, 0), knob_frame(42, 150)]
        out = Render(self.root).knob("gain", [-150, 0, 150], frames=frames).write()
        self.assertPackFails(out, "gain_0002.png is 42x42, expected 40x40")

    def test_rejects_frames_without_alpha(self):
        frames = [knob_frame(40, a).convert("RGB") if a == 0 else knob_frame(40, a) for a in (-150, 0, 150)]
        out = Render(self.root).knob("gain", [-150, 0, 150], frames=frames).write()
        self.assertPackFails(out, "gain_0001.png has no alpha channel")

    def test_rejects_a_fully_transparent_frame(self):
        frames = [knob_frame(40, -150), Image.new("RGBA", (40, 40)), knob_frame(40, 150)]
        out = Render(self.root).knob("gain", [-150, 0, 150], frames=frames).write()
        self.assertPackFails(out, "gain_0001.png is fully transparent")

    def test_rejects_a_frame_identical_to_the_one_before(self):
        frames = [knob_frame(40, -150), knob_frame(40, -150), knob_frame(40, 150)]
        out = Render(self.root).knob("gain", [-150, 0, 150], frames=frames).write()
        self.assertPackFails(out, "gain_0001.png is identical to the Frame before it")

    def test_frames_that_differ_only_in_colour_are_not_identical(self):
        # Same alpha, different colour: ImageChops.difference(...).getbbox() alone would miss this.
        frames = [knob_frame(40, 0, color=(30, 30, 30, 255)), knob_frame(40, 0, color=(200, 40, 40, 255))]
        out = Render(self.root).knob("clip", [0, 0], frames=frames).write()
        pack.pack(out)

    def test_rejects_a_bipolar_knob_with_an_even_frame_count(self):
        out = Render(self.root).knob("makeup", linear(-150, 150, 8), bipolar=True).write()
        self.assertPackFails(out, "makeup: a Bipolar Knob needs an odd Frame count, has 8")

    def test_rejects_a_bipolar_knob_whose_centre_frame_is_off_zero(self):
        out = Render(self.root).knob("makeup", linear(-150, 140, 9), bipolar=True).write()
        self.assertPackFails(out, "makeup: centre Frame is at -5")

    def test_accepts_a_centred_bipolar_knob(self):
        out = Render(self.root).knob("makeup", linear(-150, 150, 9), bipolar=True).write()
        pack.pack(out)

    def test_rejects_a_backplate_of_the_wrong_size(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).backplate(size=[100, 100]).write()
        self.assertPackFails(out, "backplate.png is 100x100, expected 200x100")

    def test_reports_every_error_at_once(self):
        frames = [knob_frame(40, -150), knob_frame(40, -150)]
        out = (Render(self.root)
               .knob("gain", [-150, 150], frames=frames)
               .knob("trim", linear(-150, 150, 4), frames=[knob_frame(40, 0)] * 1)
               .write())
        with self.assertRaises(pack.PackError) as caught:
            pack.pack(out)
        self.assertEqual(len(caught.exception.errors), 2)

    def test_warns_when_a_filmstrip_exceeds_the_texture_limit(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 100), size=200).write()
        manifest = pack.pack(out)
        self.assertEqual(manifest["warnings"], ["knob_gain_100f_1x.png is 200x20000, over the 16384 px texture limit many hosts have"])

    def test_warns_when_a_frame_is_cut_off_at_its_edge(self):
        angles = linear(-150, 150, 3)
        frames = [knob_frame(40, a) for a in angles]
        ImageDraw.Draw(frames[1]).rectangle([0, 30, 39, 39], fill=(0, 0, 0, 90))  # a shadow running off the bottom
        out = Render(self.root).knob("gain", angles, frames=frames).write()
        self.assertEqual(pack.pack(out)["warnings"],
                         ["gain_0001.png reaches its edge (alpha 90): a shadow or part is cut off; widen the Frame"])

    def test_feathers_render_noise_off_frame_edges(self):
        # Faint denoiser noise on a Frame's border would draw a seam on the Backplate.
        angles = linear(-150, 150, 3)
        frames = [knob_frame(40, a) for a in angles]
        for frame in frames:
            ImageDraw.Draw(frame).rectangle([0, 0, 39, 39], outline=(0, 0, 0, 4))
        out = Render(self.root).knob("gain", angles, frames=frames).write()
        pack.pack(out)
        strip = Image.open(out / "final" / "knob_gain_3f_1x.png")
        border = [strip.getpixel((x, 0))[3] for x in range(40)] + [strip.getpixel((0, y))[3] for y in range(120)]
        self.assertEqual(max(border), 0)
        self.assertEqual(strip.getpixel((20, 20)), frames[0].getpixel((20, 20)))  # the Knob itself is untouched

    def test_lists_a_toggles_states_in_the_manifest(self):
        out = Render(self.root).toggle("mode", states=["compress", "limit"]).write()
        [mode] = pack.pack(out)["components"]
        self.assertEqual(mode["file"], "toggle_mode_2f_1x.png")
        self.assertEqual(mode["states"], ["compress", "limit"])
        self.assertNotIn("angles", mode)

    def test_rejects_a_frame_count_that_differs_from_the_states(self):
        out = Render(self.root).toggle("mode", states=["down", "middle", "up"]).write()
        (out / "frames" / "mode" / "mode_0002.png").unlink()
        self.assertPackFails(out, "mode: 2 Frames, expected 3")

    def test_no_warnings_for_a_normal_filmstrip(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 8)).write()
        self.assertEqual(pack.pack(out)["warnings"], [])



class ReasonPackTest(unittest.TestCase):
    SIDES = {"back": PANEL, "folded_front": [200, 30], "folded_back": [200, 30]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def render(self):
        r = Render(self.root, scale=2).knob("gain", linear(-150, 150, 4), pos=(60, 40)).backplate()
        r.dir.mkdir(parents=True, exist_ok=True)
        return r.overlay("glass").reason(self.SIDES).write()

    def test_writes_the_gui2d_folder(self):
        out = self.render()
        pack.pack(out)
        gui = out / "final" / "GUI2D"
        self.assertEqual(sorted(p.name for p in gui.iterdir()), [
            "Panel_Back.png", "Panel_Folded_Back.png", "Panel_Folded_Front.png", "Panel_Front.png",
            "device_2D.lua", "knob_gain_4f.png", "overlay_glass.png"])
        self.assertEqual(Image.open(gui / "Panel_Folded_Front.png").size, (400, 60))
        lua = (gui / "device_2D.lua").read_text()
        self.assertIn('{ path = "knob_gain_4f", frames = 4 }', lua)
        self.assertIn("offset = { 80, 40 }", lua)

    def test_the_manifest_lists_the_backdrops(self):
        out = self.render()
        manifest = pack.pack(out)
        self.assertEqual(manifest["target"], "reason")
        self.assertEqual(manifest["backdrops"]["back"], {"file": "Panel_Back.png"})

    def test_a_backdrop_of_the_wrong_size_fails(self):
        r = Render(self.root, scale=2).knob("gain", linear(-150, 150, 4)).backplate()
        r.dir.mkdir(parents=True, exist_ok=True)
        r.reason(self.SIDES)
        Image.new("RGBA", (10, 10)).save(r.dir / "backdrop_folded_back.png")
        with self.assertRaises(pack.PackError):
            pack.pack(r.write())

    def test_a_juce_render_writes_no_gui2d(self):
        out = Render(self.root).knob("gain", linear(-150, 150, 4)).backplate().write()
        pack.pack(out)
        self.assertFalse((out / "final" / "GUI2D").exists())


if __name__ == "__main__":
    unittest.main()
