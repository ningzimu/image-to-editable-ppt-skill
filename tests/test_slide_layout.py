import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "skills/image-to-editable-ppt/cli/editppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from build_pptx_from_manifest import content_box_for_manifest, emu, normalize_manifest, px_to_inches, slide_size_type  # noqa: E402
from prepare_deck_run import fit_content_box, slide_for_source  # noqa: E402


class SlideLayoutTest(unittest.TestCase):
    def test_non_wide_source_uses_source_pixel_size(self):
        slide = slide_for_source(1536, 1024)

        self.assertEqual("source", slide["size_mode"])
        self.assertAlmostEqual(16, slide["width"])
        self.assertAlmostEqual(10.6666667, slide["height"])

        box = fit_content_box(1536, 1024, slide)
        self.assertAlmostEqual(0, box["left"])
        self.assertAlmostEqual(0, box["top"])
        self.assertAlmostEqual(slide["width"], box["width"])
        self.assertAlmostEqual(slide["height"], box["height"])

    def test_near_wide_source_snaps_to_standard_wide_without_stretching(self):
        slide = slide_for_source(1918, 1080)

        self.assertEqual("wide", slide["size_mode"])
        self.assertAlmostEqual(13.333, slide["width"])
        self.assertAlmostEqual(7.5, slide["height"])

        box = fit_content_box(1918, 1080, slide)
        self.assertAlmostEqual(7.5, box["height"])
        self.assertGreater(box["left"], 0)
        self.assertLess(box["width"], slide["width"])

    def test_pixel_coordinates_map_to_content_box(self):
        manifest = {
            "source": {"width_px": 1536, "height_px": 1024},
            "slide": {"width": 13.333, "height": 7.5},
        }

        box = content_box_for_manifest(manifest)
        self.assertAlmostEqual(1.0415, box["left"], places=3)
        self.assertAlmostEqual(0, box["top"])
        self.assertAlmostEqual(11.25, box["width"])
        self.assertAlmostEqual(7.5, box["height"])

        position = px_to_inches(manifest, 0, 0, 1536, 1024)
        self.assertAlmostEqual(box["left"], position["left"])
        self.assertAlmostEqual(box["top"], position["top"])
        self.assertAlmostEqual(box["width"], position["width"])
        self.assertAlmostEqual(box["height"], position["height"])

    def test_non_wide_presentation_size_is_custom(self):
        self.assertEqual("custom", slide_size_type(emu(16), emu(10.6666667)))
        self.assertEqual("wide", slide_size_type(emu(13.333), emu(7.5)))

    def test_text_font_size_is_clamped_to_source_box(self):
        manifest = {
            "source": {"width_px": 1600, "height_px": 900},
            "slide": {"width": 13.333, "height": 7.5},
            "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
            "text_boxes": [
                {
                    "text": "Dense label",
                    "box_px": [100, 100, 260, 24],
                    "font_size": 24,
                }
            ],
        }

        normalized = normalize_manifest(manifest)
        text_box = normalized["text_boxes"][0]

        self.assertLess(text_box["font_size"], 24)
        self.assertEqual(24, text_box["_requested_font_size"])

    def test_text_font_size_fit_can_be_disabled(self):
        manifest = {
            "source": {"width_px": 1600, "height_px": 900},
            "slide": {"width": 13.333, "height": 7.5},
            "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
            "text_boxes": [
                {
                    "text": "Locked label",
                    "box_px": [100, 100, 260, 24],
                    "font_size": 24,
                    "fit_text": False,
                }
            ],
        }

        normalized = normalize_manifest(manifest)

        self.assertEqual(24, normalized["text_boxes"][0]["font_size"])

    def test_wrapped_text_fit_does_not_force_single_line_width(self):
        manifest = {
            "source": {"width_px": 1600, "height_px": 900},
            "slide": {"width": 13.333, "height": 7.5},
            "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
            "text_boxes": [
                {
                    "text": "Long body copy should wrap across multiple natural lines",
                    "box_px": [100, 100, 420, 120],
                    "font_size": 18,
                    "wrap": "square",
                }
            ],
        }

        normalized = normalize_manifest(manifest)

        self.assertGreater(normalized["text_boxes"][0]["font_size"], 10)
        self.assertLessEqual(normalized["text_boxes"][0]["font_size"], 18)


if __name__ == "__main__":
    unittest.main()
