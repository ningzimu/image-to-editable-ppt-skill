import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

RUNTIME = Path(__file__).resolve().parents[1] / "skills/image-to-editable-ppt/cli/editppt/runtime"
sys.path.insert(0, str(RUNTIME))
from build_pptx_from_manifest import normalize_manifest, render_preview, write_pptx
from validate_pptx import NS, line_geometry_violations


def curve():
    return {
        "type": "path", "box_px": [10, 10, 180, 80], "fill": "none",
        "stroke": "#000000", "stroke_width": 2, "dash": "dash", "end_arrow": "triangle",
        "path_px": [
            {"op": "moveTo", "points": [[10, 90]]},
            {"op": "cubicBezTo", "points": [[50, 10], [150, 10], [190, 90]]},
        ],
    }


def manifest(shapes=None):
    return {
        "source": {"width_px": 200, "height_px": 100},
        "slide": {"width": 2, "height": 1, "background": "#FFFFFF"},
        "content_box": {"left": 0, "top": 0, "width": 2, "height": 1},
        "preview_scale": 100,
        "shapes": shapes if shapes is not None else [curve()],
        "text_boxes": [], "images": [], "text_inventory": [], "visual_inventory": [],
        "background_strategy": {"mode": "native-or-script", "comparison_note": "white"},
        "quality_checks": dict.fromkeys([
            "font_size_calibrated", "visual_inventory_matched", "background_strategy_checked",
            "shape_corner_geometry_checked",
        ], True),
    }


class PathGeometryTest(unittest.TestCase):
    def build(self, data, directory):
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(data))
        pptx = Path(directory) / "page.pptx"
        write_pptx(data, pptx, path)
        with zipfile.ZipFile(pptx) as archive:
            root = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
        return path, pptx, root

    def test_three_curves_are_three_objects_with_native_dashes_and_arrows(self):
        data = manifest([curve(), curve(), curve()])
        with tempfile.TemporaryDirectory() as directory:
            path, pptx, root = self.build(data, directory)
            self.assertEqual(3, len(root.findall(".//p:sp", NS)))
            self.assertEqual(3, len(root.findall(".//a:cubicBezTo", NS)))
            self.assertEqual(0, len(root.findall(".//a:lnTo", NS)))
            self.assertEqual(3, len(root.findall('.//a:prstDash[@val="dash"]', NS)))
            self.assertEqual(3, len(root.findall('.//a:tailEnd[@type="triangle"]', NS)))
            self.assertEqual([], line_geometry_violations(data, root))
            result = subprocess.run([sys.executable, str(RUNTIME / "validate_pptx.py"), str(pptx), "--manifest", str(path)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_actual_pptx_tampering_fails_validation(self):
        data = manifest()
        with tempfile.TemporaryDirectory() as directory:
            _, _, original = self.build(data, directory)
            for xpath in (".//a:cubicBezTo", ".//a:prstDash", ".//a:tailEnd"):
                root = copy.deepcopy(original)
                target = root.find(xpath, NS)
                parent = next(node for node in root.iter() if target in list(node))
                parent.remove(target)
                self.assertTrue(line_geometry_violations(data, root), xpath)
            root = copy.deepcopy(original)
            root.find("p:cSld/p:spTree", NS).append(copy.deepcopy(root.find(".//p:sp", NS)))
            self.assertTrue(line_geometry_violations(data, root))

    def test_closed_and_quadratic_paths(self):
        item = curve()
        item.pop("end_arrow")
        item["path_px"][1] = {"op": "quadBezTo", "points": [[100, 10], [190, 90]]}
        item["path_px"].append({"op": "close", "points": []})
        item["fill"] = "#CCCCCC"
        with tempfile.TemporaryDirectory() as directory:
            _, _, root = self.build(manifest([item]), directory)
            self.assertEqual(1, len(root.findall(".//a:quadBezTo", NS)))
            self.assertEqual(1, len(root.findall(".//a:close", NS)))

    def test_page_and_deck_validation_reject_removed_dash(self):
        with tempfile.TemporaryDirectory() as directory:
            path, pptx, root = self.build(manifest(), directory)
            line = root.find(".//a:ln", NS)
            line.remove(line.find("a:prstDash", NS))
            with zipfile.ZipFile(pptx) as archive:
                parts = {name: archive.read(name) for name in archive.namelist()}
            parts["ppt/slides/slide1.xml"] = ET.tostring(root)
            with zipfile.ZipFile(pptx, "w") as archive:
                for name, content in parts.items():
                    archive.writestr(name, content)
            validation = Path(directory) / "validation.json"
            validation.write_text('{"passed": true}')
            deck = Path(directory) / "deck_manifest.json"
            deck.write_text(json.dumps({"pages": [{"manifest": str(path), "validation": str(validation)}]}))
            for flag, metadata in [("--manifest", path), ("--deck-manifest", deck)]:
                result = subprocess.run([sys.executable, str(RUNTIME / "validate_pptx.py"), str(pptx), flag, str(metadata)], capture_output=True, text=True)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertFalse(report["passed"])
                self.assertTrue(report.get("line_geometry_violations") or report["page_contract_violations"])

    def test_invalid_contracts_rejected_before_build(self):
        invalid = []
        for field, value in [("flip_h", True), ("flip_v", True), ("dash", "unknown"), ("end_arrow", "bogus"), ("box_px", [0, 0, 0, 80]), ("fill", "#FFFFFF"), ("polygon_px", [[0, 0], [1, 1], [2, 2]])]:
            item = curve(); item[field] = value; invalid.append(item)
        item = curve(); item["path_px"][1]["points"] = [[1, 2]]; invalid.append(item)
        item = curve(); item["path_px"][1]["points"][0][0] = float("nan"); invalid.append(item)
        item = curve(); item["path_px"].append({"op": "moveTo", "points": [[0, 0]]}); invalid.append(item)
        item = curve(); item["path_px"].insert(1, {"op": "close", "points": []}); invalid.append(item)
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                normalize_manifest(manifest([item]))

    def test_declared_fragments_rejected(self):
        first = {"type": "line", "points_px": [10, 10, 20, 20], "semantic_line_id": "curve-1"}
        second = {**first, "points_px": [20, 20, 30, 30]}
        with self.assertRaisesRegex(ValueError, "split"):
            normalize_manifest(manifest([first, second]))

    def test_declared_solid_line_must_survive_in_pptx(self):
        data = manifest([{"type": "line", "points_px": [10, 10, 90, 90], "semantic_line_id": "connector"}])
        with tempfile.TemporaryDirectory() as directory:
            _, _, root = self.build(data, directory)
            root.find("p:cSld/p:spTree", NS).remove(root.find(".//p:sp", NS))
            self.assertTrue(line_geometry_violations(data, root))

    def test_diagonal_dashes_follow_both_directions_and_have_gaps(self):
        for endpoints in ([10, 10, 90, 90], [90, 90, 10, 10], [10, 90, 90, 10]):
            data = manifest([{"type": "line", "points_px": endpoints, "stroke": "#000000", "dash": "dash"}])
            with tempfile.TemporaryDirectory() as directory:
                preview = Path(directory) / "preview.png"
                render_preview(data, Path(directory) / "manifest.json", preview)
                with Image.open(preview) as image:
                    samples = [min(image.getpixel((x, (x if endpoints[0] == endpoints[1] else 100-x) + dy))[0] for dy in (0, -1)) for x in range(15, 85)]
                    self.assertIn(0, samples)
                    self.assertIn(255, samples)
                    self.assertEqual((255, 255, 255), image.getpixel((50, 10)))

    def test_curve_preview_bends_instead_of_using_chord(self):
        item = curve(); item["dash"] = "solid"; item.pop("end_arrow")
        with tempfile.TemporaryDirectory() as directory:
            preview = Path(directory) / "preview.png"
            render_preview(manifest([item]), Path(directory) / "manifest.json", preview)
            with Image.open(preview) as image:
                self.assertLess(image.getpixel((100, 30))[0], 128)
                self.assertEqual((255, 255, 255), image.getpixel((100, 90)))


if __name__ == "__main__":
    unittest.main()
