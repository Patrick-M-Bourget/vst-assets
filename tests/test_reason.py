import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import reason  # noqa: E402


def spec(size=(754, 138), ids=("gain",), **blocks):
    return {"panel": {"size": list(size), "material": "powder_coat", "color": "#111111", "hinge": True,
                      "labels": [{"text": "FRONT", "pos": [10, 10]}]},
            "components": [{"id": i, "type": "knob"} for i in ids], **blocks}


class CheckSpec(unittest.TestCase):
    def test_a_2u_panel_passes(self):
        self.assertEqual(reason.check_spec(spec()), [])

    def test_any_whole_number_of_rack_units_passes(self):
        for u in (1, 3, 4):
            self.assertEqual(reason.check_spec(spec((754, 69 * u))), [])

    def test_wrong_width_fails(self):
        errors = reason.check_spec(spec((1100, 138)))
        self.assertEqual(len(errors), 1)
        self.assertIn("754", errors[0])

    def test_height_between_rack_units_fails(self):
        self.assertIn("69 per rack unit", reason.check_spec(spec((754, 200)))[0])

    def test_an_id_that_isnt_a_lua_name_fails(self):
        errors = reason.check_spec(spec(ids=("gain", "2nd-knob")))
        self.assertEqual(len(errors), 1)
        self.assertIn("2nd-knob", errors[0])


class Backdrops(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(reason.backdrop_sizes(spec()), {
            "front": [754, 138], "back": [754, 138], "folded_front": [754, 30], "folded_back": [754, 30]})

    def test_front_is_the_spec_panel(self):
        s = spec()
        self.assertIs(reason.backdrop_panel(s, "front"), s["panel"])

    def test_back_keeps_the_finish_and_takes_its_own_labels(self):
        s = spec(back={"labels": [{"text": "BACK", "pos": [5, 5]}], "screws": [[10, 10]]})
        back = reason.backdrop_panel(s, "back")
        self.assertEqual(back["color"], "#111111")
        self.assertEqual(back["size"], [754, 138])
        self.assertEqual([l["text"] for l in back["labels"]], ["BACK"])
        self.assertEqual(back["screws"], [[10, 10]])
        self.assertNotIn("hinge", back)

    def test_a_folded_strip_with_no_block_is_a_plain_plate(self):
        folded = reason.backdrop_panel(spec(), "folded_front")
        self.assertEqual(folded["size"], [754, 30])
        self.assertNotIn("labels", folded)


class Device2D(unittest.TestCase):
    MANIFEST = {
        "scale": 5,
        "backdrops": {side: {"file": f"{name}_5x.png"} for side, name in reason.BACKDROPS.items()},
        "components": [
            {"id": "gain", "file": "knob_gain_128f_5x.png", "frames": 128, "bounds": [100, 20, 60, 60]},
            {"id": "ratio_4", "file": "button_ratio_4_2f_5x.png", "frames": 2, "bounds": [300.4, 40.2, 30, 30]},
        ],
        "overlays": [{"id": "vu_glass", "file": "overlay_vu_glass_5x.png", "bounds": [400, 10, 120, 80]}],
    }

    def test_image_names_drop_the_extension_and_scale(self):
        self.assertEqual(reason.image_name("knob_gain_128f_5x.png"), "knob_gain_128f")
        self.assertEqual(reason.image_name("Panel_Front.png"), "Panel_Front")

    def test_every_section_has_its_backdrop(self):
        lua = reason.device_2d(self.MANIFEST)
        self.assertTrue(lua.startswith('format_version = "1.0"'))
        for side, name in reason.BACKDROPS.items():
            self.assertIn(f"{side} = {{\n  Bg = {{\n    {{ path = \"{name}\" }},", lua)

    def test_components_are_offset_in_full_res_px_with_their_frame_counts(self):
        lua = reason.device_2d(self.MANIFEST)
        self.assertIn('  gain = {\n    offset = { 500, 100 },\n    { path = "knob_gain_128f", frames = 128 },', lua)
        self.assertIn('  ratio_4 = {\n    offset = { 1502, 201 },\n    { path = "button_ratio_4_2f", frames = 2 },', lua)

    def test_an_overlay_is_a_single_image_on_the_front(self):
        lua = reason.device_2d(self.MANIFEST)
        front = lua.split("back = {")[0]
        self.assertIn('  vu_glass = {\n    offset = { 2000, 50 },\n    { path = "overlay_vu_glass" },', front)

    def test_only_the_front_carries_components(self):
        back = reason.device_2d(self.MANIFEST).split("back = {")[1]
        self.assertNotIn("gain", back)


if __name__ == "__main__":
    unittest.main()
