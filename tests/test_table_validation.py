import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

RUNTIME = Path(__file__).resolve().parents[1] / "skills/image-to-editable-ppt/cli/editppt/runtime"
sys.path.insert(0, str(RUNTIME))
from build_pptx_from_manifest import write_pptx
from validate_pptx import NS, page_contract_violations, table_structure_violations


def manifest():
    return {
        "source": {"width_px": 960, "height_px": 540},
        "slide": {"width": 13.333, "height": 7.5},
        "tables": [{"box_px": [50, 100, 600, 200], "cells": [
            [{"text": "合并表头", "col_span": 2}, ""],
            ["任务", "状态"], ["测试\n多行", "已完成"],
        ]}],
        "visual_inventory": [],
        "background_strategy": {"mode": "native-or-script", "comparison_note": "white"},
        "quality_checks": dict.fromkeys([
            "font_size_calibrated", "visual_inventory_matched",
            "background_strategy_checked", "shape_corner_geometry_checked",
        ], True),
    }


class TableValidationTest(unittest.TestCase):
    def build(self, data, directory):
        source = Path(directory) / "manifest.json"
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        pptx = Path(directory) / "page.pptx"
        write_pptx(data, pptx, source)
        with zipfile.ZipFile(pptx) as archive:
            root = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
        return source, pptx, root

    def test_table_only_page_is_editable_and_text_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            source, pptx, _ = self.build(manifest(), directory)
            result = subprocess.run([sys.executable, str(RUNTIME / "validate_pptx.py"),
                                     str(pptx), "--manifest", str(source)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(1, report["native_tables"])
            self.assertEqual(0, report["editable_text_shapes"])
            self.assertEqual(5, report["editable_table_cells"])
            self.assertIn("已完成", report["required_text"])

    def test_missing_or_modified_native_structure_is_rejected(self):
        data = manifest()
        with tempfile.TemporaryDirectory() as directory:
            _, _, original = self.build(data, directory)
            self.assertEqual([], table_structure_violations(data, original))
            for xpath, attribute, value in [
                (".//a:gridCol", "w", "1"),
                (".//a:tr", "h", "1"),
                (".//a:tc", "gridSpan", "1"),
                (".//p:graphicFrame/p:xfrm/a:off", "x", "1"),
            ]:
                root = copy.deepcopy(original)
                root.find(xpath, NS).set(attribute, value)
                self.assertTrue(table_structure_violations(data, root), xpath)
            root = copy.deepcopy(original)
            root.find(".//a:t", NS).text = "篡改"
            self.assertTrue(table_structure_violations(data, root))
            root = copy.deepcopy(original)
            root.find("p:cSld/p:spTree", NS).remove(root.find(".//p:graphicFrame", NS))
            self.assertTrue(table_structure_violations(data, root))

    def test_source_screenshot_cannot_hide_under_table(self):
        data = manifest()
        data["images"] = [{"path": "source.png", "left": 0, "top": 0,
                           "width": 13.333, "height": 7.5}]
        self.assertTrue(page_contract_violations(data))

    def test_final_deck_rechecks_actual_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            source, pptx, _ = self.build(manifest(), directory)
            page_validation = Path(directory) / "validation.json"
            page_validation.write_text('{"passed": true}')
            deck = Path(directory) / "deck_manifest.json"
            deck.write_text(json.dumps({"page_count": 1, "pages": [{
                "page_id": "page-001", "manifest": str(source), "validation": str(page_validation),
            }]}))
            command = [sys.executable, str(RUNTIME / "validate_pptx.py"), str(pptx), "--deck-manifest", str(deck)]
            good = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, good.returncode, good.stdout + good.stderr)
            with zipfile.ZipFile(pptx) as archive:
                parts = {name: archive.read(name) for name in archive.namelist()}
            root = ET.fromstring(parts["ppt/slides/slide1.xml"])
            root.find("p:cSld/p:spTree", NS).remove(root.find(".//p:graphicFrame", NS))
            parts["ppt/slides/slide1.xml"] = ET.tostring(root)
            with zipfile.ZipFile(pptx, "w") as archive:
                for name, content in parts.items():
                    archive.writestr(name, content)
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertTrue(json.loads(bad.stdout)["page_contract_violations"])


if __name__ == "__main__":
    unittest.main()
