"""Native path geometry and matching raster-only curve sampling."""

import math


DASH_PATTERNS = {
    "solid": (), "dot": (1, 3), "dash": (4, 3), "lgDash": (8, 3),
    "dashDot": (4, 3, 1, 3), "lgDashDot": (8, 3, 1, 3),
    "lgDashDotDot": (8, 3, 1, 3, 1, 3), "sysDash": (3, 1),
    "sysDot": (1, 1), "sysDashDot": (3, 1, 1, 1),
    "sysDashDotDot": (3, 1, 1, 1, 1, 1),
}
POINT_COUNTS = {"moveTo": 1, "lnTo": 1, "quadBezTo": 2, "cubicBezTo": 3, "close": 0}


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_shape(item):
    """Reject unsupported styles and ambiguous or malformed native paths."""
    dash = item.get("dash")
    if dash is not None and (not isinstance(dash, str) or dash not in DASH_PATTERNS):
        raise ValueError("dash must be a supported DrawingML preset")
    for field in ("start_arrow", "end_arrow"):
        if item.get(field) not in (None, "none", "triangle"):
            raise ValueError(f"{field} must be none or triangle")
    has_arrow = any(item.get(field) == "triangle" for field in ("start_arrow", "end_arrow"))
    if has_arrow and (item.get("type") not in ("line", "path") or "polygon_px" in item or "polygon" in item):
        raise ValueError("arrows are supported only on lines and open paths")
    if item.get("type") != "path":
        if "path_px" in item:
            raise ValueError("path_px requires type path")
        return
    for field in ("polygon_px", "polygon", "points_px", "points", "preset", "flip_h", "flip_v"):
        if field in item:
            raise ValueError(f"path cannot also specify {field}")
    box = item.get("box_px")
    if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(_finite(v) for v in box) or box[2] <= 0 or box[3] <= 0:
        raise ValueError("path box_px must contain finite x, y and positive width, height")
    commands = item.get("path_px")
    if not isinstance(commands, list) or len(commands) < 2:
        raise ValueError("path_px requires moveTo followed by at least one drawing segment")
    drawn = False
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            raise ValueError("each path_px command must be an object")
        op = command.get("op")
        if not isinstance(op, str) or op not in POINT_COUNTS:
            raise ValueError("unsupported path_px operation")
        if (index == 0) != (op == "moveTo"):
            raise ValueError("path_px must have exactly one moveTo at the start")
        if op == "close" and index != len(commands) - 1:
            raise ValueError("close is allowed only at the end of path_px")
        points = command.get("points")
        if not isinstance(points, list) or len(points) != POINT_COUNTS[op]:
            raise ValueError(f"{op} requires {POINT_COUNTS[op]} points")
        if any(not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_finite(v) for v in p) for p in points):
            raise ValueError("path points must be finite [x, y] coordinates")
        drawn |= op in ("lnTo", "quadBezTo", "cubicBezTo")
    if not drawn:
        raise ValueError("path_px requires at least one drawing segment")
    closed = commands[-1]["op"] == "close"
    if not closed and item.get("fill") not in (None, "none"):
        raise ValueError("open paths require fill none")
    if closed and has_arrow:
        raise ValueError("closed paths cannot have endpoint arrows")


def custom_path_geometry_xml(item):
    """Encode a whole curve as one editable DrawingML custom geometry."""
    validate_shape(item)
    left, top, width, height = item["box_px"]
    segments = []
    for command in item["path_px"]:
        op = command["op"]
        if op == "close":
            segments.append("<a:close/>")
            continue
        points = "".join(
            f'<a:pt x="{round((x - left) / width * 21600)}" y="{round((y - top) / height * 21600)}"/>'
            for x, y in command["points"]
        )
        segments.append(f"<a:{op}>{points}</a:{op}>")
    fill = "norm" if item["path_px"][-1]["op"] == "close" else "none"
    return (
        '<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>'
        '<a:rect l="l" t="t" r="r" b="b"/>'
        f'<a:pathLst><a:path w="21600" h="21600" fill="{fill}">'
        + "".join(segments) + "</a:path></a:pathLst></a:custGeom>"
    )


def _flatten_curve(controls, output, depth=0):
    # Control-polygon excess also catches collinear curves that double back.
    length = sum(math.dist(a, b) for a, b in zip(controls, controls[1:]))
    start, end = controls[0], controls[-1]
    chord = math.dist(start, end)
    deviation = max((abs((end[0] - start[0]) * (p[1] - start[1]) - (end[1] - start[1]) * (p[0] - start[0])) / chord for p in controls[1:-1]), default=0) if chord else length
    if depth >= 16 or (length - chord <= 0.25 and deviation <= 0.25):
        output.append(end)
        return
    levels = [controls]
    while len(levels[-1]) > 1:
        levels.append([((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(levels[-1], levels[-1][1:])])
    _flatten_curve([level[0] for level in levels], output, depth + 1)
    _flatten_curve([level[-1] for level in reversed(levels)], output, depth + 1)


def preview_path_points(item, scale):
    """Map absolute source pixels through the normalized box and sample curves."""
    validate_shape(item)
    left, top, width, height = item["box_px"]

    def map_point(point):
        return (
            (item.get("left", 0) + (point[0] - left) / width * item.get("width", 1)) * scale,
            (item.get("top", 0) + (point[1] - top) / height * item.get("height", 1)) * scale,
        )

    output = []
    for command in item["path_px"]:
        op = command["op"]
        points = [map_point(point) for point in command["points"]]
        if op in ("moveTo", "lnTo"):
            output.extend(points)
        elif op == "close":
            output.append(output[0])
        else:
            _flatten_curve([output[-1], *points], output)
    return output


def draw_styled_path(draw, points, fill, width, dash=None, start_arrow=None, end_arrow=None):
    """Draw dashes continuously along arc length and arrows along end tangents."""
    if not fill or fill == "none" or len(points) < 2:
        return
    points = [tuple(point) for point in points]
    width = max(1, round(width))
    pattern = [value * width for value in DASH_PATTERNS[dash or "solid"]]
    if not pattern:
        draw.line(points, fill=fill, width=width)
    else:
        index, remaining = 0, pattern[0]
        for start, end in zip(points, points[1:]):
            length = math.dist(start, end)
            if not length:
                continue
            offset = 0.0
            while offset < length:
                step = min(remaining, length - offset)
                if index % 2 == 0:
                    segment = [tuple(a + (b - a) * distance / length for a, b in zip(start, end)) for distance in (offset, offset + step)]
                    draw.line(segment, fill=fill, width=width)
                offset += step
                remaining -= step
                if remaining <= 1e-9:
                    index = (index + 1) % len(pattern)
                    remaining = pattern[index]

    def arrow(tip, candidates):
        neighbor = next((p for p in candidates if p != tip), None)
        if neighbor is None:
            return
        distance = math.dist(tip, neighbor)
        dx, dy = (tip[0] - neighbor[0]) / distance, (tip[1] - neighbor[1]) / distance
        length, half_width = 3 * width, 1.5 * width
        base = (tip[0] - length * dx, tip[1] - length * dy)
        draw.polygon([tip, (base[0] - half_width * dy, base[1] + half_width * dx), (base[0] + half_width * dy, base[1] - half_width * dx)], fill=fill)

    if start_arrow == "triangle":
        arrow(points[0], points[1:])
    if end_arrow == "triangle":
        arrow(points[-1], reversed(points[:-1]))
