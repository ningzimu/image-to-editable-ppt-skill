"""Deterministic per-object style audit for a rebuilt page.

`editppt page validate` enforces the structural page contract. This audit is
the complementary style gate: it checks that every positioned object carries
an explicit, source-faithful style declaration — shape geometry, fill, stroke,
font size and color, shadow/glow effects, layering, and position/size — so
that visual fidelity does not depend on silent builder defaults.

The audit writes `style_audit.json` into the page directory and always exits 0
unless `--strict` is given, in which case any error-level finding exits 1.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

from build_pptx_from_manifest import (
    SHAPE_STYLE_ALIASES,
    TEXT_STYLE_ALIASES,
    gradient_stops,
    source_size_px,
)

COLOR_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
CJK_RE = re.compile(r"[一-鿿]")
CANVAS_TOLERANCE = 0.02
FONT_DEVIATION_TOLERANCE = 0.25
MIN_OBJECT_PX = 2.0

KNOWN_PRESETS = {
    "rect", "roundRect", "round1Rect", "round2SameRect", "round2DiagRect",
    "ellipse", "donut", "blockArc", "pie", "diamond", "triangle", "rtTriangle",
    "parallelogram", "trapezoid", "chevron", "pentagon", "hexagon", "heptagon",
    "octagon", "decagon", "dodecagon", "star4", "star5", "star6", "star8",
    "star12", "star16", "star24", "star32", "sun", "moon", "cloud", "heart",
    "lightningBolt", "smileyFace", "plaque", "cube", "can", "teardrop", "arc",
    "rightArrow", "leftArrow", "upArrow", "downArrow", "leftRightArrow",
    "upDownArrow", "quadArrow", "bentArrow", "bentUpArrow", "curvedRightArrow",
    "notchedRightArrow", "homePlate", "leftBracket", "rightBracket",
    "leftBrace", "rightBrace", "bracketPair", "bracePair", "callout1",
    "callout2", "callout3", "wedgeRectCallout", "wedgeRoundRectCallout",
    "wedgeEllipseCallout", "line", "straightConnector1", "bentConnector2",
    "bentConnector3", "curvedConnector2", "flowChartProcess",
    "flowChartDecision", "flowChartTerminator", "flowChartConnector",
}

DEFAULT_Z_INDEX = {"shape": 100.0, "image": 200.0, "text": 300.0}


def is_color(value):
    return isinstance(value, str) and bool(COLOR_RE.match(value.strip()))


def box_of(item):
    box = item.get("box_px")
    if isinstance(box, list) and len(box) == 4:
        return [float(v) for v in box]
    points = item.get("points_px")
    if isinstance(points, list) and len(points) == 4:
        x1, y1, x2, y2 = [float(v) for v in points]
        return [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
    polygon = item.get("polygon_px")
    if isinstance(polygon, list) and polygon:
        xs = [float(p[0]) for p in polygon]
        ys = [float(p[1]) for p in polygon]
        return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
    return None


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy


def contains(outer, inner):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return ix >= ox - 1 and iy >= oy - 1 and ix + iw <= ox + ow + 1 and iy + ih <= oy + oh + 1


def audit_color(findings, obj, field, value, *, allow_none=True):
    if value in (None, ""):
        if allow_none:
            findings.append(error(obj, field, "no explicit color declared; the builder default is not a style decision",
                                  "Set an explicit hex color sampled from the source, or the literal \"none\"."))
        return
    if value == "none":
        return
    if isinstance(value, dict):
        gradient = gradient_stops(value)
        if gradient is None:
            findings.append(error(obj, field, "invalid gradient fill spec",
                                  'Use {"gradient": {"angle": <deg>, "stops": [{"pos": 0-100, "color": "#RRGGBB"}, ...]}} with at least two stops.'))
        else:
            for pos, color in gradient[1]:
                if not COLOR_RE.match(color):
                    findings.append(error(obj, field, f"invalid gradient stop color: {color}",
                                          "Use #RGB or #RRGGBB hex colors sampled from the source."))
        return
    if not is_color(value):
        findings.append(error(obj, field, f"invalid color value: {value!r}",
                              "Use #RGB/#RRGGBB hex sampled from the source, a gradient dict, or the literal \"none\"."))


def error(obj, field, issue, suggestion):
    return {"level": "error", "object": obj, "field": field, "issue": issue, "suggestion": suggestion}


def warning(obj, field, issue, suggestion):
    return {"level": "warning", "object": obj, "field": field, "issue": issue, "suggestion": suggestion}


def info(obj, field, issue, suggestion):
    return {"level": "info", "object": obj, "field": field, "issue": issue, "suggestion": suggestion}


def check_bounds(findings, obj, box, canvas_w, canvas_h, *, is_line=False):
    if box is None:
        findings.append(error(obj, "box_px", "positioned object has no box_px/points_px/polygon_px",
                              "Record source-pixel coordinates for every positioned object."))
        return
    x, y, w, h = box
    tol_x = canvas_w * CANVAS_TOLERANCE
    tol_y = canvas_h * CANVAS_TOLERANCE
    if x < -tol_x or y < -tol_y or x + w > canvas_w + tol_x or y + h > canvas_h + tol_y:
        findings.append(error(obj, "box_px", f"box {box} exceeds the source canvas {canvas_w:.0f}x{canvas_h:.0f}",
                              "Re-measure the object bounds against source.png."))
    if is_line:
        degenerate = w < 1.0 and h < 1.0
    else:
        degenerate = w < MIN_OBJECT_PX or h < MIN_OBJECT_PX
    if degenerate:
        findings.append(warning(obj, "box_px", f"degenerate size {w:.1f}x{h:.1f}px",
                                "Confirm the object is intentional; drop phantom zero-size objects."))


def first_present(item, *fields):
    for field in fields:
        if item.get(field) not in (None, ""):
            return item[field]
    return None


def check_effect_spec(findings, obj, field, spec):
    if not isinstance(spec, dict):
        findings.append(error(obj, field, f"{field} must be an object",
                              f'Use {{"color": "#RRGGBB", "blur_px"/"radius_px": <px>, "alpha": 0-1, ...}}.'))
        return
    if not spec.get("enabled", True):
        return
    if not is_color(str(spec.get("color", ""))):
        findings.append(error(obj, f"{field}.color", f"invalid effect color: {spec.get('color')!r}",
                              "Sample the effect color from the source as #RRGGBB."))
    for key in ("blur_px", "radius_px", "offset_x_px", "offset_y_px"):
        if key in spec and not isinstance(spec[key], (int, float)):
            findings.append(error(obj, f"{field}.{key}", f"{key} must be a number of source pixels", ""))
    alpha = spec.get("alpha")
    if alpha is not None and not (isinstance(alpha, (int, float)) and 0.0 <= float(alpha) <= 1.0):
        findings.append(error(obj, f"{field}.alpha", f"alpha must be between 0 and 1, got {alpha!r}", ""))


def audit_shapes(manifest, findings, canvas):
    canvas_w, canvas_h = canvas
    for index, item in enumerate(manifest.get("shapes", [])):
        obj = f"shapes[{index}]"
        box = box_of(item)
        is_line = item.get("type") == "line" or item.get("preset") == "line" or "points_px" in item
        check_bounds(findings, obj, box, canvas_w, canvas_h, is_line=is_line)
        preset = item.get("preset")
        if preset and preset not in KNOWN_PRESETS:
            findings.append(error(obj, "preset", f"unknown preset geometry: {preset!r}",
                                  "Use a DrawingML preset name, or polygon_px for a custom outline."))
        if not is_line:
            if "fill" not in item:
                findings.append(error(obj, "fill", "shape has no explicit fill",
                                      "Declare the source fill: hex color, gradient dict, or \"none\"."))
            else:
                audit_color(findings, obj, "fill", item.get("fill"))
        stroke = first_present(item, "stroke", "line_color", "border_color")
        if stroke is None and not is_line:
            findings.append(error(obj, "stroke", "shape has no explicit stroke declaration",
                                  "Declare the source border color, or \"none\" when the source has no border."))
        elif stroke not in (None, "none"):
            audit_color(findings, obj, "stroke", stroke, allow_none=False)
            if first_present(item, "stroke_width", "line_width", "border_width") is None:
                findings.append(error(obj, "stroke_width", "stroked shape has no explicit stroke_width",
                                      "Measure the source border width in pixels."))
        for field in ("shadow", "glow"):
            if field in item:
                check_effect_spec(findings, obj, field, item[field])
        if "z_index" not in item:
            findings.append(info(obj, "z_index", "no explicit z_index; falls back to the layer default (100)",
                                 "Set z_index when the object participates in overlapping layers."))


def audit_text_boxes(manifest, findings, canvas, hint_lines):
    canvas_w, canvas_h = canvas
    used_hints = set()
    for index, item in enumerate(manifest.get("text_boxes", [])):
        obj = f"text_boxes[{index}]"
        box = box_of(item)
        check_bounds(findings, obj, box, canvas_w, canvas_h)
        if item.get("font_size") in (None, ""):
            findings.append(error(obj, "font_size", "text box has no explicit font_size",
                                  "Copy the measured value from text_hints.json / the source."))
        color = first_present(item, "color", "font_color", "text_color")
        if color is None:
            findings.append(error(obj, "color", "text box has no explicit color",
                                  "Sample the glyph color from the source."))
        else:
            audit_color(findings, obj, "color", color, allow_none=False)
        if "font" not in item and "font_family" not in item:
            findings.append(info(obj, "font", "no explicit font family; the builder default applies",
                                 "Record the source typeface when it differs from the default."))
        if item.get("font_size_source") not in ("measured", "hints"):
            findings.append(info(obj, "font_size_source", "font size not marked as measured",
                                 'Add "font_size_source": "measured" for hint-calibrated boxes.'))
        if box and hint_lines and item.get("font_size") not in (None, ""):
            best = None
            best_overlap = 0.0
            for hint_index, hint in enumerate(hint_lines):
                hint_box = hint.get("box_px")
                if not hint_box:
                    continue
                overlap = overlaps(box, [float(v) for v in hint_box])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best = (hint_index, hint)
            if best and best_overlap > 0.3 * (box[2] * box[3]):
                hint_index, hint = best
                used_hints.add(hint_index)
                text = " ".join(str(part) for part in _text_lines(item))
                measured = hint.get("font_pt_if_cjk") if CJK_RE.search(text) else hint.get("font_pt_if_latin")
                measured = measured or hint.get("font_pt")
                if measured:
                    requested = float(item["font_size"])
                    deviation = abs(requested - float(measured)) / float(measured)
                    if deviation > FONT_DEVIATION_TOLERANCE:
                        findings.append(warning(
                            obj, "font_size",
                            f"font_size {requested}pt deviates {deviation:.0%} from measured {measured}pt (hint {hint.get('id', hint_index)})",
                            "Use the measured size unless the hint merged several lines or latched onto a graphic."))
        for field in ("shadow", "glow"):
            if field in item:
                check_effect_spec(findings, obj, field, item[field])
        if "z_index" not in item:
            findings.append(info(obj, "z_index", "no explicit z_index; falls back to the layer default (300)",
                                 "Set z_index when the text participates in overlapping layers."))
    return used_hints


def _text_lines(item):
    if item.get("paragraphs"):
        lines = []
        for paragraph in item["paragraphs"]:
            if isinstance(paragraph, str):
                lines.append(paragraph)
            else:
                runs = paragraph.get("runs")
                lines.append("".join(str(run.get("text", "")) for run in runs) if runs else str(paragraph.get("text", "")))
        return lines
    if item.get("runs"):
        return ["".join(str(run.get("text", "")) for run in item["runs"])]
    return str(item.get("text", "")).splitlines()


def audit_images(manifest, page_dir, findings, canvas):
    canvas_w, canvas_h = canvas
    for index, item in enumerate(manifest.get("images", [])):
        obj = f"images[{index}]"
        box = box_of(item)
        check_bounds(findings, obj, box, canvas_w, canvas_h)
        path = item.get("path", "")
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = page_dir / resolved
        if not path or not resolved.exists():
            findings.append(error(obj, "path", f"image file missing: {path!r}",
                                  "Import the asset with editppt image import / process-sheet before building."))
        if not (item.get("id") or item.get("alt")):
            findings.append(info(obj, "alt", "image has no id/alt naming what it depicts",
                                 "Name the asset after the source object it reproduces."))
        if "z_index" not in item:
            findings.append(info(obj, "z_index", "no explicit z_index; falls back to the layer default (200)",
                                 "Set z_index when the asset participates in overlapping layers."))


def audit_layering(manifest, findings):
    coverers = []
    for index, item in enumerate(manifest.get("shapes", [])):
        box = box_of(item)
        fill = item.get("fill")
        opaque = fill not in (None, "", "none")
        if box and opaque:
            coverers.append((f"shapes[{index}]", box, float(item.get("z_index", DEFAULT_Z_INDEX["shape"]))))
    for index, item in enumerate(manifest.get("images", [])):
        box = box_of(item)
        if box:
            coverers.append((f"images[{index}]", box, float(item.get("z_index", DEFAULT_Z_INDEX["image"]))))
    for index, item in enumerate(manifest.get("text_boxes", [])):
        box = box_of(item)
        if not box:
            continue
        text_z = float(item.get("z_index", DEFAULT_Z_INDEX["text"]))
        for name, cover_box, cover_z in coverers:
            if cover_z > text_z and contains(cover_box, box):
                findings.append(warning(
                    f"text_boxes[{index}]", "z_index",
                    f"text is fully covered by higher-z {name} (z={cover_z:g} > {text_z:g})",
                    "Raise the text z_index or lower the covering object; see page-decision-tree.md section 3.6."))


def audit_duplicates(manifest, findings):
    boxes = []
    for index, item in enumerate(manifest.get("text_boxes", [])):
        box = box_of(item)
        text = " ".join(_text_lines(item)).strip()
        if box and text:
            boxes.append((index, box, text))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            index_a, box_a, text_a = boxes[i]
            index_b, box_b, text_b = boxes[j]
            if text_a != text_b:
                continue
            overlap = overlaps(box_a, box_b)
            if overlap > 0.8 * min(box_a[2] * box_a[3], box_b[2] * box_b[3]):
                findings.append(warning(
                    f"text_boxes[{index_b}]", "text",
                    f"duplicate of text_boxes[{index_a}] at a nearly identical position",
                    "Remove the duplicate; the same text must not be drawn twice (decision tree section 3.5)."))


def run_audit(page_dir, manifest_name, hints_name="text_hints.json"):
    page_dir = Path(page_dir)
    manifest = json.loads((page_dir / manifest_name).read_text(encoding="utf-8"))
    source = manifest.get("source", {})
    canvas = (float(source.get("width_px", 0)), float(source.get("height_px", 0)))
    if not canvas[0] or not canvas[1]:
        raise SystemExit("style-audit: manifest lacks source.width_px/source.height_px")
    hints_path = page_dir / hints_name
    hint_lines = []
    if hints_path.exists():
        hint_lines = json.loads(hints_path.read_text(encoding="utf-8")).get("lines", [])
    findings = []
    audit_shapes(manifest, findings, canvas)
    audit_text_boxes(manifest, findings, canvas, hint_lines)
    audit_images(manifest, page_dir, findings, canvas)
    audit_layering(manifest, findings)
    audit_duplicates(manifest, findings)
    summary = {
        "errors": sum(1 for f in findings if f["level"] == "error"),
        "warnings": sum(1 for f in findings if f["level"] == "warning"),
        "info": sum(1 for f in findings if f["level"] == "info"),
    }
    return {
        "schema_version": 1,
        "manifest": manifest_name,
        "canvas_px": {"width": canvas[0], "height": canvas[1]},
        "summary": summary,
        "findings": findings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit per-object style completeness against the strict fidelity contract.")
    parser.add_argument("page_dir", help="Page directory containing manifest.json")
    parser.add_argument("--manifest", default="manifest.json", help="Manifest file relative to the page directory")
    parser.add_argument("--report", default="style_audit.json", help="Report output relative to the page directory")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any error-level finding exists")
    args = parser.parse_args(argv)
    page_dir = Path(args.page_dir).expanduser().resolve()
    report = run_audit(page_dir, args.manifest)
    report_path = page_dir / args.report
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(f"style-audit: errors={summary['errors']} warnings={summary['warnings']} info={summary['info']} -> {report_path}")
    for finding in report["findings"]:
        if finding["level"] == "error":
            print(f"  ERROR {finding['object']} {finding['field']}: {finding['issue']}", file=sys.stderr)
    return 1 if args.strict and summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
