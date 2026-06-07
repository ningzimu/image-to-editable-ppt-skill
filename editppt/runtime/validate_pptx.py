#!/usr/bin/env python3
import argparse
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_pptx_from_manifest import normalize_manifest


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

ALLOWED_SOURCE_TYPES = {
    "imagegen",
    "user-provided",
    "user-approved-rasterization",
    "source-derived-rasterization",
}
REQUIRED_QUALITY_CHECKS = {
    "font_size_calibrated",
    "visual_inventory_matched",
    "background_strategy_checked",
    "shape_corner_geometry_checked",
}


def read_manifest(path):
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_full_slide_image(item, slide):
    width = float(slide.get("width", 13.333))
    height = float(slide.get("height", 7.5))
    left = float(item.get("left", 0))
    top = float(item.get("top", 0))
    image_width = float(item.get("width", 0))
    image_height = float(item.get("height", 0))
    return (
        abs(left) <= 0.02
        and abs(top) <= 0.02
        and image_width >= width * 0.98
        and image_height >= height * 0.98
    )


def page_contract_violations(manifest):
    violations = []
    slide = manifest.get("slide", {})
    images = manifest.get("images", [])
    text_boxes = manifest.get("text_boxes", [])
    provenance_by_path = {
        Path(entry.get("path", "")).as_posix(): entry
        for entry in manifest.get("asset_provenance", [])
        if entry.get("path")
    }
    for image in images:
        path = Path(image.get("path", "")).as_posix()
        provenance = provenance_by_path.get(path, {})
        source_type = provenance.get("source_type")
        if is_full_slide_image(image, slide) and Path(path).name == "source.png" and text_boxes:
            violations.append(
                {
                    "field": "images",
                    "path": path,
                    "reason": "full-slide source.png background with editable text overlays causes baked-text overlap",
                }
            )
        if (
            is_full_slide_image(image, slide)
            and source_type in {"user-provided", "user-approved-rasterization", "source-derived-rasterization"}
            and text_boxes
        ):
            violations.append(
                {
                    "field": "asset_provenance",
                    "path": path,
                    "reason": "full-slide raster background cannot be assembled with editable text",
                }
            )

    return violations


def source_region_size(entry):
    region = entry.get("source_region_px")
    if isinstance(region, list) and len(region) == 4:
        return float(region[2]), float(region[3])
    bbox = entry.get("source_bbox_px")
    if isinstance(bbox, list) and len(bbox) == 4:
        return abs(float(bbox[2]) - float(bbox[0])), abs(float(bbox[3]) - float(bbox[1]))
    return None


def quality_contract_violations(manifest):
    violations = []

    if "visual_inventory" not in manifest:
        violations.append(
            {
                "field": "visual_inventory",
                "reason": "page manifest must record the non-text visual inventory, even when it is empty",
            }
        )
    elif not isinstance(manifest.get("visual_inventory"), list):
        violations.append({"field": "visual_inventory", "reason": "visual_inventory must be a list"})

    background_strategy = manifest.get("background_strategy")
    if not background_strategy:
        violations.append(
            {
                "field": "background_strategy",
                "reason": "page manifest must record how the background was rebuilt or preserved",
            }
        )

    quality_checks = manifest.get("quality_checks")
    if not isinstance(quality_checks, dict):
        violations.append({"field": "quality_checks", "reason": "quality_checks must be an object"})
    else:
        for key in sorted(REQUIRED_QUALITY_CHECKS):
            if quality_checks.get(key) is not True:
                violations.append(
                    {
                        "field": f"quality_checks.{key}",
                        "reason": "required page QA check must be explicitly true",
                    }
                )

    for index, shape in enumerate(manifest.get("shapes", [])):
        is_round_rect = shape.get("type") == "roundRect" or shape.get("preset") == "roundRect"
        if is_round_rect and not shape.get("source_corner_radius_px"):
            violations.append(
                {
                    "field": f"shapes[{index}]",
                    "reason": "roundRect requires source_corner_radius_px; use rect for source straight-corner containers",
                }
            )
        if is_round_rect and shape.get("source_corner_radius_px") and shape.get("box_px"):
            box = shape.get("box_px")
            radius = float(shape.get("source_corner_radius_px") or 0)
            min_dim = max(1.0, min(float(box[2]), float(box[3])))
            if radius > min_dim / 2:
                violations.append(
                    {
                        "field": f"shapes[{index}].source_corner_radius_px",
                        "reason": "roundRect source radius cannot exceed half of the smaller shape dimension",
                    }
                )

    return violations


def alpha_edge_violations(image_path, edge_padding=3):
    try:
        from PIL import Image
    except Exception as exc:
        return [{"field": "asset_alpha", "reason": f"unable to import Pillow for asset edge check: {exc}"}]

    try:
        image = Image.open(image_path).convert("RGBA")
    except Exception as exc:
        return [{"field": "asset_alpha", "reason": f"unable to open asset for edge check: {exc}"}]

    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if not bbox:
        return [{"field": "asset_alpha", "reason": "asset has no visible opaque pixels"}]
    left, top, right, bottom = bbox
    width, height = image.size
    problems = []
    if left < edge_padding or top < edge_padding or width - right < edge_padding or height - bottom < edge_padding:
        problems.append(
            {
                "field": "asset_alpha",
                "reason": "visible pixels touch the asset edge; inspect source/contact sheet or add safe padding when this asset requires edge-safe alpha",
            }
        )
    return problems


def pixel_authoring_violations(manifest):
    violations = []
    source = manifest.get("source", {})
    if not source.get("width_px") or not source.get("height_px"):
        violations.append(
            {
                "field": "source.width_px/source.height_px",
                "reason": "page manifest must record the source image pixel size",
            }
        )

    for section in ("text_boxes", "images"):
        for index, item in enumerate(manifest.get(section, [])):
            if "box_px" not in item:
                violations.append(
                    {
                        "field": f"{section}[{index}].box_px",
                        "reason": "positioned text and image objects must use source-image pixel coordinates",
                    }
                )

    for index, item in enumerate(manifest.get("shapes", [])):
        if item.get("type") == "line":
            if "points_px" not in item:
                violations.append(
                    {
                        "field": f"shapes[{index}].points_px",
                        "reason": "line shapes must use source-image pixel endpoints",
                    }
                )
        elif "box_px" not in item:
            violations.append(
                {
                    "field": f"shapes[{index}].box_px",
                    "reason": "positioned shapes must use source-image pixel coordinates",
                }
            )

    return violations


def normalize_for_validation(manifest):
    violations = pixel_authoring_violations(manifest)
    try:
        return normalize_manifest(manifest), violations
    except Exception as exc:
        violations.append({"field": "manifest", "reason": str(exc)})
        return manifest, violations


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def collect_text(xml_bytes):
    root = ET.fromstring(xml_bytes)
    return "".join(node.text or "" for node in root.findall(".//a:t", NS))


def collect_paragraph_text(xml_bytes):
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//a:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//a:t", NS))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def collect_notes_texts(z, names):
    notes = {}
    for name in sorted(n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)):
        match = re.search(r"notesSlide(\d+)\.xml$", name)
        if not match:
            continue
        notes[int(match.group(1))] = collect_paragraph_text(z.read(name))
    return notes


def validate_deck(args):
    deck_path = Path(args.deck_manifest).resolve()
    deck = read_manifest(deck_path)
    root = Path(deck.get("job_dir", deck_path.parent)).resolve()
    expected_pages = int(deck.get("page_count", len(deck.get("pages", []))))
    notes_manifest = {}
    notes_path = deck.get("notes_manifest")
    if notes_path:
        notes_file = Path(notes_path)
        if not notes_file.is_absolute():
            notes_file = root / notes_file
        if notes_file.exists():
            notes_manifest = read_manifest(notes_file)

    report = {
        "pptx": str(Path(args.pptx).resolve()),
        "deck_manifest": str(deck_path),
        "expected_pages": expected_pages,
        "slides": 0,
        "page_manifests_missing": [],
        "page_validation_missing": [],
        "failed_page_validations": [],
        "page_contract_violations": [],
        "notes_expected": len(notes_manifest.get("notes", [])),
        "notes_found": 0,
        "notes_hash_mismatches": [],
        "missing_parts": [],
        "warnings": [],
        "passed": False,
    }

    for page in deck.get("pages", []):
        manifest_path = Path(page.get("manifest", ""))
        validation_path = Path(page.get("validation", ""))
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        if not validation_path.is_absolute():
            validation_path = root / validation_path
        if not manifest_path.exists():
            report["page_manifests_missing"].append(str(manifest_path))
        else:
            try:
                raw_manifest = read_manifest(manifest_path)
                manifest, violations = normalize_for_validation(raw_manifest)
                violations.extend(page_contract_violations(manifest))
                violations.extend(quality_contract_violations(raw_manifest))
                if violations:
                    report["page_contract_violations"].append(
                        {"manifest": str(manifest_path), "violations": violations}
                    )
            except Exception as exc:
                report["page_contract_violations"].append(
                    {"manifest": str(manifest_path), "violations": [{"reason": str(exc)}]}
                )
        if not validation_path.exists():
            report["page_validation_missing"].append(str(validation_path))
        else:
            try:
                page_report = read_manifest(validation_path)
                if page_report.get("passed") is False:
                    report["failed_page_validations"].append(str(validation_path))
            except Exception as exc:
                report["failed_page_validations"].append(f"{validation_path}: {exc}")

    try:
        with zipfile.ZipFile(args.pptx) as z:
            names = z.namelist()
            report["slides"] = len([n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)])
            for part in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"):
                if part not in names:
                    report["missing_parts"].append(part)
            notes_texts = collect_notes_texts(z, names)
            report["notes_found"] = len(notes_texts)
            for entry in notes_manifest.get("notes", []):
                page_index = int(entry.get("page_index", 0))
                expected_hash = entry.get("text_sha256", sha256_text(entry.get("text", "")))
                actual = notes_texts.get(page_index)
                if actual is None:
                    report["notes_hash_mismatches"].append({"page_index": page_index, "reason": "missing notes slide"})
                elif sha256_text(actual) != expected_hash:
                    report["notes_hash_mismatches"].append({"page_index": page_index, "reason": "text hash mismatch"})
    except Exception as exc:
        report["warnings"].append(f"Unable to read pptx: {exc}")

    report["passed"] = (
        report["slides"] == expected_pages
        and not report["page_manifests_missing"]
        and not report["page_validation_missing"]
        and not report["failed_page_validations"]
        and not report["page_contract_violations"]
        and not report["missing_parts"]
        and not report["notes_hash_mismatches"]
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["passed"] else 1)


def rel_source_part(rels_name):
    if not rels_name.endswith(".rels"):
        return posixpath.dirname(rels_name)
    directory = posixpath.dirname(rels_name)
    if directory.endswith("/_rels"):
        directory = posixpath.dirname(directory)
    source = posixpath.basename(rels_name)[:-5]
    return posixpath.normpath(posixpath.join(directory, source))


def resolve_target(rels_name, target):
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    source = rel_source_part(rels_name)
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def relationship_targets(z, rels_name, names):
    if rels_name not in names:
        return []
    root = ET.fromstring(z.read(rels_name))
    targets = []
    for rel in root.findall("rel:Relationship", NS):
        mode = rel.attrib.get("TargetMode")
        target = rel.attrib.get("Target")
        resolved = resolve_target(rels_name, target)
        targets.append(
            {
                "id": rel.attrib.get("Id"),
                "type": rel.attrib.get("Type", ""),
                "target": target,
                "resolved": resolved,
                "external": mode == "External",
            }
        )
    return targets


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx")
    parser.add_argument("--manifest")
    parser.add_argument("--deck-manifest")
    parser.add_argument("--required-text", action="append", default=[])
    parser.add_argument("--report")
    args = parser.parse_args()

    if args.deck_manifest:
        validate_deck(args)

    raw_manifest = read_manifest(args.manifest)
    manifest, authoring_violations = normalize_for_validation(raw_manifest)
    manifest_base = Path(args.manifest).resolve().parent if args.manifest else Path.cwd()
    required = list(args.required_text)
    required.extend(manifest.get("required_text", []))
    required.extend(manifest.get("text_inventory", []))

    report = {
        "pptx": str(Path(args.pptx).resolve()),
        "zip_ok": False,
        "slides": 0,
        "images": 0,
        "editable_text_shapes": 0,
        "shape_count": 0,
        "all_text": "",
        "required_text": required,
        "missing_required_text": [],
        "missing_parts": [],
        "missing_relationship_targets": [],
        "missing_asset_provenance": [],
        "missing_manifest_images": [],
        "missing_provenance_sources": [],
        "invalid_asset_provenance": [],
        "media_hash_mismatches": [],
        "asset_provenance_checked": 0,
        "manifest_image_count": len(manifest.get("images", [])),
        "media_manifest_mismatch": False,
        "relationship_targets_checked": 0,
        "warnings": [],
        "page_contract_violations": [],
    }

    try:
        with zipfile.ZipFile(args.pptx) as z:
            bad = z.testzip()
            report["zip_ok"] = bad is None
            if bad:
                report["warnings"].append(f"Bad zip member: {bad}")
            names = z.namelist()
            required_parts = [
                "[Content_Types].xml",
                "_rels/.rels",
                "ppt/presentation.xml",
                "ppt/_rels/presentation.xml.rels",
            ]
            for part in required_parts:
                if part not in names:
                    report["missing_parts"].append(part)
            slide_names = sorted(n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n))
            report["slides"] = len(slide_names)
            report["images"] = len([n for n in names if n.startswith("ppt/media/")])
            report["media_manifest_mismatch"] = report["images"] != report["manifest_image_count"]
            for index, image in enumerate(manifest.get("images", []), start=1):
                image_path = image.get("path")
                if not image_path:
                    continue
                ext = Path(image_path).suffix.lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                media_name = f"ppt/media/image{index}{ext}"
                source_path = Path(image_path)
                if not source_path.is_absolute():
                    source_path = manifest_base / source_path
                if media_name not in names:
                    report["media_hash_mismatches"].append(
                        {"path": image_path, "media": media_name, "reason": "missing media part"}
                    )
                    continue
                if source_path.exists():
                    manifest_hash = file_sha256(source_path)
                    media_hash = hashlib.sha256(z.read(media_name)).hexdigest()
                    if manifest_hash != media_hash:
                        report["media_hash_mismatches"].append(
                            {"path": image_path, "media": media_name, "reason": "hash mismatch"}
                        )
                else:
                    report["missing_manifest_images"].append(str(image_path))
            for slide_name in slide_names:
                rels_name = f"{posixpath.dirname(slide_name)}/_rels/{posixpath.basename(slide_name)}.rels"
                if rels_name not in names:
                    report["missing_parts"].append(rels_name)
            rel_files = [name for name in names if name.endswith(".rels")]
            for rels_name in rel_files:
                for target in relationship_targets(z, rels_name, names):
                    if target["external"] or not target["resolved"]:
                        continue
                    report["relationship_targets_checked"] += 1
                    if target["resolved"] not in names:
                        report["missing_relationship_targets"].append(
                            {
                                "rels": rels_name,
                                "id": target["id"],
                                "target": target["target"],
                                "resolved": target["resolved"],
                            }
                        )
            texts = []
            for slide_name in slide_names:
                xml = z.read(slide_name)
                root = ET.fromstring(xml)
                shapes = root.findall(".//p:sp", NS)
                report["shape_count"] += len(shapes)
                report["editable_text_shapes"] += sum(1 for shape in shapes if shape.findall(".//a:t", NS))
                texts.append(collect_text(xml))
            report["all_text"] = "\n".join(texts)
    except Exception as exc:
        report["warnings"].append(f"Unable to read pptx: {exc}")

    for text in required:
        if text and text not in report["all_text"]:
            report["missing_required_text"].append(text)

    provenance = {}
    for entry in manifest.get("asset_provenance", []):
        path = entry.get("path")
        if path:
            provenance[Path(path).as_posix()] = entry

    for image in manifest.get("images", []):
        image_path = image.get("path")
        if not image_path:
            continue
        key = Path(image_path).as_posix()
        entry = provenance.get(key)
        if not entry:
            report["missing_asset_provenance"].append(key)
            continue
        report["asset_provenance_checked"] += 1
        source_type = entry.get("source_type")
        provenance_note = entry.get("provenance_note") or entry.get("qa_note")
        if source_type not in ALLOWED_SOURCE_TYPES:
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "source_type", "value": source_type}
            )
        if not provenance_note:
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "provenance_note", "value": provenance_note}
            )
        if source_type == "user-approved-rasterization" and not entry.get("approval_note"):
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "approval_note", "value": entry.get("approval_note")}
            )
        if source_type in {"user-approved-rasterization", "source-derived-rasterization"} and not (
            entry.get("source_region_px") or entry.get("source_bbox_px")
        ):
            report["invalid_asset_provenance"].append(
                {
                    "path": key,
                    "field": "source_region_px/source_bbox_px",
                    "value": entry.get("source_region_px") or entry.get("source_bbox_px"),
                }
            )
        if source_type == "source-derived-rasterization":
            region_size = source_region_size(entry)
            if region_size and (region_size[0] <= 0 or region_size[1] <= 0):
                report["invalid_asset_provenance"].append(
                    {"path": key, "field": "source_region_px/source_bbox_px", "value": entry.get("source_region_px") or entry.get("source_bbox_px")}
                )
        source = entry.get("source")
        if not source:
            report["missing_provenance_sources"].append({"path": key, "source": source})
            continue
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = manifest_base / source_path
        if not source_path.exists():
            report["missing_provenance_sources"].append({"path": key, "source": str(source)})
        if source_type == "source-derived-rasterization" and entry.get("require_edge_safe_alpha") is True:
            asset_file = Path(key)
            if not asset_file.is_absolute():
                asset_file = manifest_base / asset_file
            for problem in alpha_edge_violations(asset_file):
                report["invalid_asset_provenance"].append({"path": key, **problem})

    report["page_contract_violations"] = (
        authoring_violations + page_contract_violations(manifest) + quality_contract_violations(raw_manifest)
    )

    report["passed"] = (
        report["zip_ok"]
        and report["slides"] >= 1
        and not report["media_manifest_mismatch"]
        and not report["missing_parts"]
        and not report["missing_relationship_targets"]
        and not report["media_hash_mismatches"]
        and not report["missing_required_text"]
        and not report["missing_asset_provenance"]
        and not report["missing_manifest_images"]
        and not report["missing_provenance_sources"]
        and not report["invalid_asset_provenance"]
        and not report["page_contract_violations"]
        and (report["editable_text_shapes"] > 0 or not required)
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
