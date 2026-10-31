"""Rectangular editable table validation and DrawingML emission."""
import math
from copy import deepcopy

STYLE_DEFAULTS = {"font": "PingFang SC", "font_size": 18, "color": "#111111",
                  "align": "left", "valign": "top", "wrap": "none",
                  "fill": "#FFFFFF", "stroke": "#000000", "stroke_width": 1,
                  "margin_left": 0.05, "margin_right": 0.05,
                  "margin_top": 0.05, "margin_bottom": 0.05}


STYLE_FIELDS = set(STYLE_DEFAULTS) | {"bold", "italic", "fit_text"}
CELL_FIELDS = {"text", "row_span", "col_span", "style"}
CELL_GEOMETRY = {"left", "top", "width", "height"}


def validate_style(style, label):
    if not isinstance(style, dict):
        raise ValueError(f"{label} must be an object")
    unsupported = set(style) - STYLE_FIELDS
    if unsupported:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(sorted(unsupported))}")


def positive(value, label, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} must be a finite {'nonnegative' if allow_zero else 'positive'} number")
    return float(value)


def normalize_table(table, manifest, normalize_position, fit_text, align, valign):
    if not isinstance(table, dict):
        raise ValueError("table must be an object")
    table = deepcopy(table)
    if "box" in table:
        if not isinstance(table["box"], list) or len(table["box"]) != 4:
            raise ValueError("table.box must be [x, y, width, height] in inches")
        table.update(zip(("left", "top", "width", "height"), table["box"]))
    table = normalize_position(manifest, table)
    for name in ("left", "top", "width", "height"):
        table[name] = positive(table.get(name), f"table.{name}", name in ("left", "top"))
    cells = table.get("cells")
    if not isinstance(cells, list) or not cells or not isinstance(cells[0], list) or not cells[0]:
        raise ValueError("table.cells must be a nonempty rectangular 2D array")
    rows, cols = len(cells), len(cells[0])
    if any(not isinstance(row, list) or len(row) != cols for row in cells):
        raise ValueError("table.cells must be rectangular")
    for key, count, extent in (("column_widths", cols, table["width"]), ("row_heights", rows, table["height"])):
        values = table.get(key, [1] * count)
        if not isinstance(values, list) or len(values) != count:
            raise ValueError(f"table.{key} must match the grid dimension")
        values = [positive(value, f"table.{key}") for value in values]
        table[key] = [value / sum(values) * extent for value in values]
    style = table.get("style", {})
    validate_style(style, "table.style")
    owners = {}
    output = []
    for r, row in enumerate(cells):
        output.append([])
        for c, raw in enumerate(row):
            if isinstance(raw, str):
                raw = {"text": raw}
            if not isinstance(raw, dict) or not isinstance(raw.get("text", ""), str):
                raise ValueError("table cell must be a string or object with string text")
            if (r, c) in owners:
                if {k: v for k, v in raw.items() if k != "_owner"} not in ({}, {"text": ""}):
                    raise ValueError("covered table cells must be empty, without style or spans")
                output[r].append({"_owner": owners[r, c]})
                continue
            # Normalized cells expose effective style and geometry for both renderers.
            # Recalculate those fields rather than trusting supplied internal values.
            allowed = CELL_FIELDS
            if CELL_GEOMETRY <= raw.keys() and STYLE_DEFAULTS.keys() <= raw.keys() and "style" in raw:
                allowed = allowed | STYLE_FIELDS | CELL_GEOMETRY
            unsupported = set(raw) - allowed
            if unsupported:
                raise ValueError(f"table cell contains unsupported fields: {', '.join(sorted(unsupported))}")
            rs, cs = raw.get("row_span", 1), raw.get("col_span", 1)
            if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in (rs, cs)):
                raise ValueError("table row_span/col_span must be positive integers")
            if r + rs > rows or c + cs > cols:
                raise ValueError("table span exceeds grid bounds")
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    if (rr, cc) in owners:
                        raise ValueError("table spans overlap")
                    owners[rr, cc] = (r, c)
            validate_style(raw.get("style", {}), "cell.style")
            cell = {**STYLE_DEFAULTS, **style, **raw.get("style", {}), "text": raw.get("text", ""), "row_span": rs, "col_span": cs}
            align(cell["align"])
            valign(cell["valign"])
            if cell["wrap"] not in ("none", "square"):
                raise ValueError("cell wrap must be none or square")
            positive(cell["font_size"], "cell font_size")
            positive(cell["stroke_width"], "cell stroke_width", True)
            for side in ("left", "right", "top", "bottom"):
                positive(cell[f"margin_{side}"], f"cell margin_{side}", True)
            cell.update(left=table["left"] + sum(table["column_widths"][:c]),
                        top=table["top"] + sum(table["row_heights"][:r]),
                        width=sum(table["column_widths"][c:c + cs]), height=sum(table["row_heights"][r:r + rs]))
            inner = cell_text_box(cell)
            if inner["width"] <= 0 or inner["height"] <= 0:
                raise ValueError("table cell margins leave no text area")
            fitted = fit_text(inner, manifest)
            cell["font_size"] = fitted.get("font_size", cell["font_size"])
            cell["style"] = {**style, **raw.get("style", {}), "font_size": cell["font_size"]}
            output[r].append(cell)
    table["cells"] = output
    return table


def cell_text_box(cell):
    return {**cell, "left": cell["left"] + cell["margin_left"], "top": cell["top"] + cell["margin_top"],
            "width": cell["width"] - cell["margin_left"] - cell["margin_right"],
            "height": cell["height"] - cell["margin_top"] - cell["margin_bottom"]}


def table_xml(idx, table, emu, text_xml, fill_xml, line_xml, valign):
    rows = []
    for r, row in enumerate(table["cells"]):
        parts = []
        for c, cell in enumerate(row):
            owner_r, owner_c = cell.get("_owner", (r, c))
            origin = table["cells"][owner_r][owner_c]
            attrs = []
            if r == owner_r and origin["row_span"] > 1:
                attrs.append(f'rowSpan="{origin["row_span"]}"')
            if c == owner_c and origin["col_span"] > 1:
                attrs.append(f'gridSpan="{origin["col_span"]}"')
            if c != owner_c:
                attrs.append('hMerge="1"')
            if r != owner_r:
                attrs.append('vMerge="1"')
            body = text_xml(0, {**origin, "text": ""} if "_owner" in cell else cell).split("<p:txBody>", 1)[1].split("</p:txBody>", 1)[0]
            lines = "".join(line_xml(origin["stroke"] if origin["stroke_width"] else "none", origin["stroke_width"]).replace("a:ln", f"a:ln{side}") for side in ("L", "R", "T", "B"))
            margins = " ".join(f'mar{side}="{emu(origin[key])}"' for side, key in (("L", "margin_left"), ("R", "margin_right"), ("T", "margin_top"), ("B", "margin_bottom")))
            parts.append(f'<a:tc {" ".join(attrs)}><a:txBody>{body}</a:txBody><a:tcPr {margins} anchor="{valign(origin["valign"])[0]}">{lines}{fill_xml(origin["fill"])}</a:tcPr></a:tc>')
        rows.append(f'<a:tr h="{emu(table["row_heights"][r])}">{"".join(parts)}</a:tr>')
    grid = "".join(f'<a:gridCol w="{emu(width)}"/>' for width in table["column_widths"])
    return f'''<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{idx}" name="Table {idx}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{emu(table['left'])}" y="{emu(table['top'])}"/><a:ext cx="{emu(table['width'])}" cy="{emu(table['height'])}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr/><a:tblGrid>{grid}</a:tblGrid>{''.join(rows)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'''
