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


def marker_shape(shape_id, name, x):
    p_ns = NS["p"]
    a_ns = NS["a"]
    shape = ET.Element(f"{{{p_ns}}}sp")
    non_visual = ET.SubElement(shape, f"{{{p_ns}}}nvSpPr")
    ET.SubElement(non_visual, f"{{{p_ns}}}cNvPr", id=str(shape_id), name=name)
    ET.SubElement(non_visual, f"{{{p_ns}}}cNvSpPr")
    ET.SubElement(non_visual, f"{{{p_ns}}}nvPr")
    properties = ET.SubElement(shape, f"{{{p_ns}}}spPr")
    transform = ET.SubElement(properties, f"{{{a_ns}}}xfrm")
    ET.SubElement(transform, f"{{{a_ns}}}off", x=str(x), y="0")
    ET.SubElement(transform, f"{{{a_ns}}}ext", cx="100000", cy="100000")
    geometry = ET.SubElement(properties, f"{{{a_ns}}}prstGeom", prst="rect")
    ET.SubElement(geometry, f"{{{a_ns}}}avLst")
    return shape


def wrap_picture_in_group(pptx_path):
    """Move the source picture into a real group with a non-identity transform."""
    p_ns = NS["p"]
    a_ns = NS["a"]
    ET.register_namespace("a", a_ns)
    ET.register_namespace("p", p_ns)
    ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
    with zipfile.ZipFile(pptx_path) as source:
        parts = {name: source.read(name) for name in source.namelist()}

    slide = ET.fromstring(parts["ppt/slides/slide1.xml"])
    shape_tree = slide.find(".//p:spTree", NS)
    picture = shape_tree.find("p:pic", NS)
    picture_index = list(shape_tree).index(picture)
    shape_tree.remove(picture)

    group = ET.Element(f"{{{p_ns}}}grpSp")
    non_visual = ET.SubElement(group, f"{{{p_ns}}}nvGrpSpPr")
    ET.SubElement(non_visual, f"{{{p_ns}}}cNvPr", id="20", name="Test Group")
    ET.SubElement(non_visual, f"{{{p_ns}}}cNvGrpSpPr")
    ET.SubElement(non_visual, f"{{{p_ns}}}nvPr")
    group_properties = ET.SubElement(group, f"{{{p_ns}}}grpSpPr")
    transform = ET.SubElement(group_properties, f"{{{a_ns}}}xfrm")
    ET.SubElement(transform, f"{{{a_ns}}}off", x="100000", y="200000")
    ET.SubElement(transform, f"{{{a_ns}}}ext", cx="8000000", cy="4000000")
    ET.SubElement(transform, f"{{{a_ns}}}chOff", x="0", y="0")
    ET.SubElement(transform, f"{{{a_ns}}}chExt", cx="12191695", cy="6858000")
    group.append(marker_shape(21, "Before Picture", 10000))
    group.append(picture)
    group.append(marker_shape(22, "After Picture", 12000000))
    shape_tree.insert(picture_index, group)
    parts["ppt/slides/slide1.xml"] = ET.tostring(slide, encoding="utf-8", xml_declaration=True)

    rewritten = pptx_path.with_name("grouped-source.pptx")
    with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as output:
        for name, data in parts.items():
            output.writestr(name, data)
    return rewritten


def source_manifest(source_image):
    return {
        "source": {"width_px": 1600, "height_px": 900},
        "slide": {"width": 13.333, "height": 7.5},
        "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
        "text_boxes": [{"text": "KEEP ME", "box_px": [80, 40, 400, 70], "font_size": 22}],
        "shapes": [],
        "images": [{"path": str(source_image), "box_px": [200, 240, 1000, 500]}],
    }


def rebuilt_manifest():
    return {
        "source": {"width_px": 800, "height_px": 400},
        "slide": {"width": 13.333, "height": 6.6665},
        "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 6.6665},
        "text_boxes": [{"text": "REBUILT", "box_px": [40, 30, 300, 60], "font_size": 18}],
        "shapes": [{"type": "rect", "box_px": [20, 20, 500, 100], "fill": "#ffffff", "stroke": "none"}],
        "images": [],
    }


class HybridPptxTests(unittest.TestCase):
    def test_preserves_native_objects_and_replaces_only_embedded_picture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_image = root / "flattened.png"
            Image.new("RGB", (800, 400), "#ddeeff").save(source_image)
            source_pptx = root / "source.pptx"
            write_pptx(source_manifest(source_image), source_pptx, root / "source.json")

            run_dir = root / "run"
            deck_path = normalize_inputs([source_pptx], job_dir=run_dir)
            deck = upgrade_deck_manifest(deck_path, 2)
            self.assertEqual("hybrid-pptx", deck["input_type"])
            self.assertEqual(1, deck["page_count"])
            self.assertIn("replacement_target", deck["pages"][0])

            page_dir = run_dir / "pages/page_001"
            write_json(page_dir / "manifest.json", rebuilt_manifest())
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

    def test_replaces_picture_inside_group_with_group_local_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_image = root / "flattened.png"
            Image.new("RGB", (800, 400), "#ddeeff").save(source_image)
            source_pptx = root / "source.pptx"
            write_pptx(source_manifest(source_image), source_pptx, root / "source.json")
            grouped_pptx = wrap_picture_in_group(source_pptx)

            run_dir = root / "run"
            deck_path = normalize_inputs([grouped_pptx], job_dir=run_dir)
            deck = upgrade_deck_manifest(deck_path, 2)
            target = deck["pages"][0]["replacement_target"]
            self.assertEqual("hybrid-pptx", deck["input_type"])
            self.assertEqual(3, target["z_index"])

            page_dir = run_dir / "pages/page_001"
            write_json(page_dir / "manifest.json", rebuilt_manifest())
            deck, entries, notes = page_entries_from_deck_manifest(deck_path)
            output = root / "grouped-output.pptx"
            write_deck(deck, entries, output, notes)

            with zipfile.ZipFile(output) as pptx:
                slide = ET.fromstring(pptx.read("ppt/slides/slide1.xml"))
                group = next(
                    candidate
                    for candidate in slide.findall(".//p:grpSp", NS)
                    if candidate.find("p:nvGrpSpPr/p:cNvPr", NS).attrib.get("name") == "Test Group"
                )
                group_transform = group.find("p:grpSpPr/a:xfrm", NS)
                self.assertEqual({"x": "100000", "y": "200000"}, group_transform.find("a:off", NS).attrib)
                self.assertEqual({"cx": "8000000", "cy": "4000000"}, group_transform.find("a:ext", NS).attrib)

                object_names = []
                generated_rect = None
                for shape in group.findall("p:sp", NS):
                    properties = shape.find("p:nvSpPr/p:cNvPr", NS)
                    name = properties.attrib.get("name")
                    object_names.append(name)
                    if name.startswith("Rect"):
                        generated_rect = shape
                self.assertEqual(4, len(object_names))
                self.assertEqual("Before Picture", object_names[0])
                self.assertTrue(object_names[1].startswith("Rect"))
                self.assertTrue(object_names[2].startswith("TextBox"))
                self.assertEqual("After Picture", object_names[3])

                frame = target["frame_emu"]
                expected_x = round(frame["x"] + 20 / 800 * frame["cx"])
                expected_y = round(frame["y"] + 20 / 400 * frame["cy"])
                rect_offset = generated_rect.find("p:spPr/a:xfrm/a:off", NS)
                self.assertEqual(expected_x, int(rect_offset.attrib["x"]))
                self.assertEqual(expected_y, int(rect_offset.attrib["y"]))

                self.assertEqual([], slide.findall(".//p:pic", NS))
                rels = ET.fromstring(pptx.read("ppt/slides/_rels/slide1.xml.rels"))
                image_rels = [rel for rel in rels.findall("rel:Relationship", NS) if rel.attrib.get("Type", "").endswith("/image")]
                self.assertEqual([], image_rels)
                self.assertEqual([], [name for name in pptx.namelist() if name.startswith("ppt/media/")])


if __name__ == "__main__":
    unittest.main()
