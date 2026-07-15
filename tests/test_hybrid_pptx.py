import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "skills/image-to-editable-ppt/cli/editppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from _input_normalization import normalize_inputs  # noqa: E402
from build_pptx_from_manifest import page_entries_from_deck_manifest, write_deck, write_pptx  # noqa: E402
from prepare_deck_run import upgrade_deck_manifest  # noqa: E402


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class HybridPptxTests(unittest.TestCase):
    def test_preserves_native_objects_and_replaces_only_embedded_picture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_image = root / "flattened.png"
            Image.new("RGB", (800, 400), "#ddeeff").save(source_image)
            source_manifest = {
                "source": {"width_px": 1600, "height_px": 900},
                "slide": {"width": 13.333, "height": 7.5},
                "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
                "text_boxes": [{"text": "KEEP ME", "box_px": [80, 40, 400, 70], "font_size": 22}],
                "shapes": [],
                "images": [{"path": str(source_image), "box_px": [200, 240, 1000, 500]}],
            }
            source_pptx = root / "source.pptx"
            write_pptx(source_manifest, source_pptx, root / "source.json")

            run_dir = root / "run"
            deck_path = normalize_inputs([source_pptx], job_dir=run_dir)
            deck = upgrade_deck_manifest(deck_path, 2)
            self.assertEqual("hybrid-pptx", deck["input_type"])
            self.assertEqual(1, deck["page_count"])
            self.assertIn("replacement_target", deck["pages"][0])

            page_dir = run_dir / "pages/page_001"
            rebuilt = {
                "source": {"width_px": 800, "height_px": 400},
                "slide": {"width": 13.333, "height": 6.6665},
                "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 6.6665},
                "text_boxes": [{"text": "REBUILT", "box_px": [40, 30, 300, 60], "font_size": 18}],
                "shapes": [{"type": "rect", "box_px": [20, 20, 500, 100], "fill": "#ffffff", "stroke": "none"}],
                "images": [],
            }
            write_json(page_dir / "manifest.json", rebuilt)
            deck, entries, notes = page_entries_from_deck_manifest(deck_path)
            output = root / "hybrid-output.pptx"
            write_deck(deck, entries, output, notes)

            with zipfile.ZipFile(output) as pptx:
                slide = ET.fromstring(pptx.read("ppt/slides/slide1.xml"))
                texts = [node.text or "" for node in slide.findall(".//a:t", NS)]
                self.assertIn("KEEP ME", texts)
                self.assertIn("REBUILT", texts)
                self.assertEqual([], slide.findall(".//p:pic", NS))
                rels = ET.fromstring(pptx.read("ppt/slides/_rels/slide1.xml.rels"))
                image_rels = [rel for rel in rels.findall("rel:Relationship", NS) if rel.attrib.get("Type", "").endswith("/image")]
                self.assertEqual([], image_rels)
                self.assertEqual([], [name for name in pptx.namelist() if name.startswith("ppt/media/")])


if __name__ == "__main__":
    unittest.main()
