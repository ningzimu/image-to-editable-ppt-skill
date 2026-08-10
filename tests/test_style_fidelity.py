import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "skills/image-to-editable-ppt/cli/editppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from build_pptx_from_manifest import (  # noqa: E402
    effect_lst_xml,
    gradient_stops,
    normalize_manifest,
    shape_fill,
    shape_line_xml,
    shape_xml,
    text_box_xml,
)
from style_audit import run_audit  # noqa: E402
from validate_pptx import REQUIRED_QUALITY_CHECKS  # noqa: E402


def base_manifest():
    return {
        "slide": {"width": 13.333, "height": 7.5},
        "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
        "source": {"width_px": 1280, "height_px": 720},
        "text_inventory": [],
        "visual_inventory": [],
        "background_strategy": {"mode": "native-or-script", "comparison_note": "checked"},
        "quality_checks": {
            "font_size_calibrated": True,
            "visual_inventory_matched": True,
            "background_strategy_checked": True,
            "shape_corner_geometry_checked": True,
            "style_audit_completed": True,
        },
        "text_boxes": [],
        "shapes": [],
        "images": [],
        "asset_provenance": [],
    }


class GradientFillTest(unittest.TestCase):
    def test_gradient_fill_renders_grad_fill(self):
        xml = shape_fill({"gradient": {"angle": 90, "stops": [{"pos": 0, "color": "#1D4ED8"}, {"pos": 100, "color": "#7C3AED"}]}})
        self.assertIn("<a:gradFill>", xml)
        self.assertIn('ang="5400000"', xml)
        self.assertIn('pos="0"', xml)
        self.assertIn('pos="100000"', xml)
        self.assertIn('val="1D4ED8"', xml)
        self.assertIn('val="7C3AED"', xml)

    def test_gradient_stops_accept_fractional_positions(self):
        angle, stops = gradient_stops({"stops": [{"pos": 0.0, "color": "#000000"}, {"pos": 1.0, "color": "#FFFFFF"}]})
        self.assertEqual(0.0, angle)
        self.assertEqual([(0, "000000"), (100000, "FFFFFF")], stops)

    def test_solid_and_none_fill_unchanged(self):
        self.assertIn("solidFill", shape_fill("#FF0000"))
        self.assertEqual("<a:noFill/>", shape_fill("none"))


class EffectXmlTest(unittest.TestCase):
    def test_shadow_renders_outer_shadow(self):
        xml = effect_lst_xml({"shadow": {"color": "#1A3A6B", "blur_px": 8, "offset_x_px": 3, "offset_y_px": 4, "alpha": 0.4}})
        self.assertIn("<a:outerShdw", xml)
        self.assertIn('blurRad="76200"', xml)
        self.assertIn('val="1A3A6B"', xml)
        self.assertIn('<a:alpha val="40000"/>', xml)

    def test_glow_renders_glow(self):
        xml = effect_lst_xml({"glow": {"color": "#38BDF8", "radius_px": 6, "alpha": 0.6}})
        self.assertIn("<a:glow", xml)
        self.assertIn('rad="57150"', xml)
        self.assertIn('val="38BDF8"', xml)

    def test_no_effects_returns_empty_string(self):
        self.assertEqual("", effect_lst_xml({}))
        self.assertEqual("", effect_lst_xml({"shadow": {"enabled": False}}))

    def test_shape_and_text_box_embed_effect_list(self):
        shape = shape_xml(2, {"type": "rect", "left": 0, "top": 0, "width": 1, "height": 1, "fill": "#FFFFFF", "stroke": "none", "shadow": {"color": "#000000", "alpha": 0.3}})
        self.assertIn("<a:effectLst>", shape)
        text = text_box_xml(3, {"left": 0, "top": 0, "width": 2, "height": 0.5, "text": "t", "glow": {"color": "#FFFFFF", "radius_px": 4}})
        self.assertIn("<a:glow", text)


class ArrowAndAliasTest(unittest.TestCase):
    def test_arrow_end_renders_tail_end(self):
        xml = shape_line_xml("#2563EB", 3, arrow_end=True)
        self.assertIn('<a:tailEnd type="triangle" w="med" len="med"/>', xml)

    def test_no_arrow_end_by_default(self):
        self.assertNotIn("tailEnd", shape_line_xml("#2563EB", 3))

    def test_shape_aliases_normalize_to_canonical_fields(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40], "line_color": "#FF0000", "line_width": 2}]
        normalized = normalize_manifest(manifest)
        self.assertEqual("#FF0000", normalized["shapes"][0]["stroke"])
        self.assertEqual(2, normalized["shapes"][0]["stroke_width"])

    def test_canonical_field_wins_over_alias(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40], "stroke": "#00FF00", "line_color": "#FF0000"}]
        normalized = normalize_manifest(manifest)
        self.assertEqual("#00FF00", normalized["shapes"][0]["stroke"])

    def test_text_aliases_normalize(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [{"box_px": [0, 0, 100, 30], "text": "x", "font_size": 12, "font_color": "#123456", "font_family": "Menlo", "fit_text": False}]
        normalized = normalize_manifest(manifest)
        self.assertEqual("#123456", normalized["text_boxes"][0]["color"])
        self.assertEqual("Menlo", normalized["text_boxes"][0]["font"])


class StyleAuditTest(unittest.TestCase):
    def run_page_audit(self, manifest):
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            (page_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            return run_audit(page_dir, "manifest.json")

    def levels(self, report):
        return report["summary"]

    def test_fully_styled_manifest_has_no_errors(self):
        manifest = base_manifest()
        manifest["shapes"] = [
            {"type": "roundRect", "box_px": [40, 40, 300, 70], "fill": "#FFFFFF", "stroke": "#0F766E", "stroke_width": 1.5, "source_corner_radius_px": 12, "z_index": 20}
        ]
        manifest["text_boxes"] = [
            {"box_px": [60, 50, 260, 40], "text": "标题", "font_size": 24, "color": "#111111", "font": "PingFang SC", "font_size_source": "measured", "z_index": 40}
        ]
        report = self.run_page_audit(manifest)
        self.assertEqual(0, report["summary"]["errors"], json.dumps(report["findings"], ensure_ascii=False))

    def test_missing_style_declarations_are_errors(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40]}]
        manifest["text_boxes"] = [{"box_px": [0, 0, 100, 30], "text": "x"}]
        report = self.run_page_audit(manifest)
        fields = {(f["object"], f["field"]) for f in report["findings"] if f["level"] == "error"}
        self.assertIn(("shapes[0]", "fill"), fields)
        self.assertIn(("shapes[0]", "stroke"), fields)
        self.assertIn(("text_boxes[0]", "font_size"), fields)
        self.assertIn(("text_boxes[0]", "color"), fields)

    def test_stroke_aliases_satisfy_declaration(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40], "fill": "#FFFFFF", "line_color": "#000000", "line_width": 1, "z_index": 10}]
        report = self.run_page_audit(manifest)
        errors = [f for f in report["findings"] if f["level"] == "error"]
        self.assertEqual([], errors)

    def test_out_of_canvas_is_error(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [1200, 700, 400, 100], "fill": "#FFFFFF", "stroke": "none", "z_index": 10}]
        report = self.run_page_audit(manifest)
        self.assertTrue(any(f["level"] == "error" and "canvas" in f["issue"] for f in report["findings"]))

    def test_unknown_preset_is_error(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "shape", "preset": "starNotReal", "box_px": [0, 0, 100, 40], "fill": "#FFFFFF", "stroke": "none"}]
        report = self.run_page_audit(manifest)
        self.assertTrue(any(f["field"] == "preset" and f["level"] == "error" for f in report["findings"]))

    def test_line_shape_needs_no_fill_and_may_have_zero_thickness(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "line", "points_px": [10, 50, 300, 50], "stroke": "#2563EB", "stroke_width": 2, "arrow_end": True, "z_index": 20}]
        report = self.run_page_audit(manifest)
        self.assertEqual([], [f for f in report["findings"] if f["level"] in ("error", "warning")])

    def test_invalid_gradient_is_error(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40], "fill": {"gradient": {"stops": [{"pos": 0, "color": "#FFF"}]}}, "stroke": "none"}]
        report = self.run_page_audit(manifest)
        self.assertTrue(any(f["field"] == "fill" and f["level"] == "error" for f in report["findings"]))

    def test_invalid_shadow_spec_is_error(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40], "fill": "#FFFFFF", "stroke": "none", "shadow": {"color": "not-a-color"}}]
        report = self.run_page_audit(manifest)
        self.assertTrue(any(f["field"] == "shadow.color" and f["level"] == "error" for f in report["findings"]))

    def test_covered_text_is_warning(self):
        manifest = base_manifest()
        manifest["images"] = []
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 400, 300], "fill": "#FFFFFF", "stroke": "none", "z_index": 500}]
        manifest["text_boxes"] = [{"box_px": [40, 40, 200, 40], "text": "covered", "font_size": 18, "color": "#111111", "z_index": 300}]
        report = self.run_page_audit(manifest)
        self.assertTrue(any(f["level"] == "warning" and "covered" in f["issue"] for f in report["findings"]))

    def test_font_size_deviation_from_hints_is_warning(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [{"box_px": [40, 40, 400, 60], "text": "端到端主链", "font_size": 40, "color": "#111111", "z_index": 300}]
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            (page_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            hints = {"lines": [{"id": "P01", "text": "端到端主链", "box_px": [45, 45, 390, 50], "font_pt_if_cjk": 24.0, "font_pt_if_latin": 32.0}]}
            (page_dir / "text_hints.json").write_text(json.dumps(hints), encoding="utf-8")
            report = run_audit(page_dir, "manifest.json")
        self.assertTrue(any(f["level"] == "warning" and "deviates" in f["issue"] for f in report["findings"]))

    def test_style_audit_completed_is_required_quality_check(self):
        self.assertIn("style_audit_completed", REQUIRED_QUALITY_CHECKS)


if __name__ == "__main__":
    unittest.main()
