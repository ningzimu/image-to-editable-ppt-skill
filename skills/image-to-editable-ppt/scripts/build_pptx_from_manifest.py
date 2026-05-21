#!/usr/bin/env python3
import argparse
import html
import json
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path


EMU_PER_INCH = 914400
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def emu(value):
    return int(round(float(value) * EMU_PER_INCH))


def hex_color(value, default="000000"):
    if not value:
        return default
    return str(value).strip().lstrip("#").upper()


def content_type_for(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".svg":
        return "image/svg+xml"
    raise ValueError(f"Unsupported image type: {path}")


def image_ext(path):
    suffix = Path(path).suffix.lower()
    return ".jpg" if suffix == ".jpeg" else suffix


def xml_text(value):
    return html.escape(str(value), quote=True)


def source_size_px(manifest):
    source = manifest.get("source", {})
    width = source.get("width_px")
    height = source.get("height_px")
    if width and height:
        return float(width), float(height)
    return None


def px_to_inches(manifest, x, y, width, height):
    slide = manifest.get("slide", {})
    source_size = source_size_px(manifest)
    if not source_size:
        raise ValueError("Manifest uses pixel coordinates but lacks source.width_px/source.height_px")
    source_width, source_height = source_size
    slide_width = float(slide.get("width", 13.333))
    slide_height = float(slide.get("height", 7.5))
    return {
        "left": float(x) / source_width * slide_width,
        "top": float(y) / source_height * slide_height,
        "width": float(width) / source_width * slide_width,
        "height": float(height) / source_height * slide_height,
    }


def normalize_position_item(manifest, item):
    item = dict(item)
    if "box_px" in item:
        x, y, width, height = item["box_px"]
        item.update(px_to_inches(manifest, x, y, width, height))
    if "points_px" in item:
        x1, y1, x2, y2 = item["points_px"]
        left = min(float(x1), float(x2))
        top = min(float(y1), float(y2))
        width = abs(float(x2) - float(x1))
        height = abs(float(y2) - float(y1))
        item.update(px_to_inches(manifest, left, top, width, height))
        start = px_to_inches(manifest, x1, y1, 0, 0)
        end = px_to_inches(manifest, x2, y2, 0, 0)
        item["points"] = [start["left"], start["top"], end["left"], end["top"]]
        if float(x2) < float(x1):
            item["flip_h"] = True
        if float(y2) < float(y1):
            item["flip_v"] = True
    if item.get("source_corner_radius_px") is not None and "radius" not in item:
        radius = float(item.get("source_corner_radius_px") or 0)
        item["radius"] = px_to_inches(manifest, 0, 0, radius, radius)["width"]
    return item


def normalize_manifest(manifest):
    """Return a manifest copy with pixel authoring fields resolved to inches."""
    normalized = deepcopy(manifest)
    for key in ("text_boxes", "images", "shapes"):
        normalized[key] = [normalize_position_item(normalized, item) for item in normalized.get(key, [])]
    return normalized


def preview_color(value):
    if not value or value == "none":
        return value
    value = str(value).strip()
    if value.startswith("#"):
        return value
    if len(value) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in value):
        return f"#{value}"
    return value


def shape_fill(fill):
    if not fill or fill == "none":
        return '<a:noFill/>'
    return f'<a:solidFill><a:srgbClr val="{hex_color(fill)}"/></a:solidFill>'


def shape_line_xml(stroke, width, dash=None):
    if not stroke or stroke == "none":
        return '<a:ln><a:noFill/></a:ln>'
    dash_xml = f'<a:prstDash val="{xml_text(dash)}"/>' if dash else ""
    return (
        f'<a:ln w="{int(float(width or 1) * 12700)}">'
        f'<a:solidFill><a:srgbClr val="{hex_color(stroke)}"/></a:solidFill>'
        f"{dash_xml}"
        "</a:ln>"
    )


def slide_background_xml(slide):
    background = slide.get("background")
    if not background:
        return ""
    return (
        "<p:bg><p:bgPr>"
        f'<a:solidFill><a:srgbClr val="{hex_color(background, "FFFFFF")}"/></a:solidFill>'
        "<a:effectLst/></p:bgPr></p:bg>"
    )


def text_box_xml(idx, item):
    left = emu(item.get("left", 0))
    top = emu(item.get("top", 0))
    width = emu(item.get("width", 1))
    height = emu(item.get("height", 0.4))
    rotation = item.get("rotation")
    rotation_attr = f' rot="{int(float(rotation) * 60000)}"' if rotation not in (None, "") else ""
    font_size = int(float(item.get("font_size", 18)) * 100)
    font = xml_text(item.get("font", "PingFang SC"))
    align = item.get("align", "left")
    anchor = item.get("valign", "top")
    wrap = item.get("wrap", "none")
    autofit = item.get("autofit", "none")
    autofit_xml = "<a:spAutoFit/>" if autofit == "shape" else "<a:noAutofit/>"
    paragraphs = item.get("paragraphs")
    runs = item.get("runs")

    def run_xml(run):
        run_font_size = int(float(run.get("font_size", item.get("font_size", 18))) * 100)
        run_font = xml_text(run.get("font", item.get("font", "PingFang SC")))
        run_color = hex_color(run.get("color", item.get("color", "#111111")))
        run_bold = ' b="1"' if run.get("bold", item.get("bold")) else ""
        run_italic = ' i="1"' if run.get("italic", item.get("italic")) else ""
        run_text = xml_text(run.get("text", ""))
        return (
            f'<a:r><a:rPr lang="zh-CN" sz="{run_font_size}"{run_bold}{run_italic}>'
            f'<a:solidFill><a:srgbClr val="{run_color}"/></a:solidFill>'
            f'<a:latin typeface="{run_font}"/><a:ea typeface="{run_font}"/><a:cs typeface="{run_font}"/>'
            f'</a:rPr><a:t>{run_text}</a:t></a:r>'
        )

    def paragraph_xml(paragraph):
        if isinstance(paragraph, str):
            paragraph_runs = [{"text": paragraph}]
        else:
            paragraph_runs = paragraph.get("runs", [{"text": paragraph.get("text", "")}])
        return (
            f'<a:p><a:pPr algn="{align}"/>'
            + "".join(run_xml(run) for run in paragraph_runs)
            + f'<a:endParaRPr lang="zh-CN" sz="{font_size}"/></a:p>'
        )

    if paragraphs:
        text_body = "".join(paragraph_xml(paragraph) for paragraph in paragraphs)
    elif runs:
        text_body = paragraph_xml({"runs": runs})
    else:
        text_body = "".join(paragraph_xml(part) for part in str(item.get("text", "")).split("\n"))
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{idx}" name="TextBox {idx}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm{rotation_attr}><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
        <p:txBody>
          <a:bodyPr wrap="{xml_text(wrap)}" anchor="{anchor}" lIns="0" tIns="0" rIns="0" bIns="0">{autofit_xml}</a:bodyPr><a:lstStyle/>
          {text_body}
        </p:txBody>
      </p:sp>"""


def image_xml(idx, rel_id, item):
    left = emu(item.get("left", 0))
    top = emu(item.get("top", 0))
    width = emu(item.get("width", 1))
    height = emu(item.get("height", 1))
    name = xml_text(item.get("alt") or Path(item.get("path", "")).stem or f"Image {idx}")
    return f"""
      <p:pic>
        <p:nvPicPr><p:cNvPr id="{idx}" name="{name}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr><a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      </p:pic>"""


def shape_xml(idx, item):
    kind = item.get("type", "rect")
    left = emu(item.get("left", 0))
    top = emu(item.get("top", 0))
    width = emu(item.get("width", 1))
    height = emu(item.get("height", 1))
    stroke_width = item.get("stroke_width", 1)
    flip_h = ' flipH="1"' if item.get("flip_h") else ""
    flip_v = ' flipV="1"' if item.get("flip_v") else ""
    fill = shape_fill(item.get("fill"))
    line = shape_line_xml(item.get("stroke", "#000000"), stroke_width, item.get("dash"))
    preset = item.get("preset")
    if not preset:
        preset = "line" if kind == "line" else "ellipse" if kind == "ellipse" else "roundRect" if kind == "roundRect" else "rect"
    geometry = preset_geometry_xml(preset, item)
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{idx}" name="{xml_text(kind.title())} {idx}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm{flip_h}{flip_v}><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>{geometry}{fill}{line}</p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
      </p:sp>"""


def round_rect_adjustment(item):
    box_px = item.get("box_px")
    if item.get("source_corner_radius_px") is not None and box_px and len(box_px) == 4:
        radius = float(item.get("source_corner_radius_px") or 0)
        min_dim = max(1.0, min(float(box_px[2]), float(box_px[3])))
    elif item.get("radius") is not None:
        radius = float(item.get("radius") or 0)
        min_dim = max(0.01, min(float(item.get("width", 1)), float(item.get("height", 1))))
    else:
        return None
    return max(0, min(50000, int(round(radius / min_dim * 100000))))


def preset_geometry_xml(preset, item):
    if preset != "roundRect":
        return f'<a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>'
    adjustment = round_rect_adjustment(item)
    if adjustment is None:
        return '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>'
    return (
        '<a:prstGeom prst="roundRect"><a:avLst>'
        f'<a:gd name="adj" fmla="val {adjustment}"/>'
        '</a:avLst></a:prstGeom>'
    )


def slide_xml(manifest):
    slide = manifest.get("slide", {})
    next_id = 2
    parts = []
    layered = []
    for index, item in enumerate(manifest.get("shapes", [])):
        layered.append((float(item.get("z_index", 100)), index, "shape", item, None))
    for rel_index, item in enumerate(manifest.get("images", []), start=1):
        layered.append((float(item.get("z_index", 200)), rel_index, "image", item, f"rId{rel_index + 1}"))
    for index, item in enumerate(manifest.get("text_boxes", [])):
        layered.append((float(item.get("z_index", 300)), index, "text", item, None))

    for _z_index, _order, kind, item, rel_id in sorted(layered, key=lambda entry: (entry[0], entry[1])):
        if kind == "shape":
            parts.append(shape_xml(next_id, item))
        elif kind == "image":
            parts.append(image_xml(next_id, rel_id, item))
        else:
            parts.append(text_box_xml(next_id, item))
        next_id += 1
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    {slide_background_xml(slide)}
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {''.join(parts)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def rels_xml(manifest, media_start=1, notes_index=None):
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>']
    for i, item in enumerate(manifest.get("images", []), start=1):
        target = f"../media/image{media_start + i - 1}{image_ext(item['path'])}"
        rels.append(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>')
    if notes_index is not None:
        rels.append(
            f'<Relationship Id="rId{len(rels) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{notes_index}.xml"/>'
        )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>"


def notes_slide_xml(text):
    paras = "".join(
        f'<a:p><a:r><a:rPr lang="zh-CN" sz="1200"/><a:t>{xml_text(line)}</a:t></a:r><a:endParaRPr lang="zh-CN" sz="1200"/></a:p>'
        for line in str(text).splitlines()
    ) or '<a:p><a:endParaRPr lang="zh-CN" sz="1200"/></a:p>'
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder"/><p:cNvSpPr txBox="1"/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="685800" y="914400"/><a:ext cx="5486400" cy="6858000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:notes>"""


def notes_rels_xml(slide_index):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="../notesMasters/notesMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide{slide_index}.xml"/>
</Relationships>"""


def notes_master_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
</p:notesMaster>"""


def notes_master_rels_xml():
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def content_types_xml(manifests, notes_indices=None):
    notes_indices = notes_indices or []
    defaults = {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "xml": "application/xml",
    }
    for manifest in manifests:
        for item in manifest.get("images", []):
            ext = image_ext(item["path"]).lstrip(".")
            defaults[ext] = content_type_for(item["path"])
    default_xml = "".join(f'<Default Extension="{ext}" ContentType="{ctype}"/>' for ext, ctype in defaults.items())
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, len(manifests) + 1):
        overrides.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    if notes_indices:
        overrides.append('<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>')
        for i in notes_indices:
            overrides.append(f'<Override PartName="/ppt/notesSlides/notesSlide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{default_xml}{"".join(overrides)}</Types>'


def presentation_xml(slide_count, width, height):
    slide_ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, slide_count + 1))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{width}" cy="{height}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def presentation_rels_xml(slide_count):
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(1, slide_count + 1):
        rels.append(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{"".join(rels)}</Relationships>'


def write_common_parts(z, slide_count, width, height, notes_count):
    z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>""")
    z.writestr("docProps/core.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Image to editable PPT</dc:title></cp:coreProperties>""")
    z.writestr("docProps/app.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Codex</Application><PresentationFormat>Widescreen</PresentationFormat><Slides>{slide_count}</Slides></Properties>""")
    z.writestr("ppt/presentation.xml", presentation_xml(slide_count, width, height))
    z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(slide_count))
    z.writestr("ppt/slideMasters/slideMaster1.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>""")
    z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>""")
    z.writestr("ppt/slideLayouts/slideLayout1.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>""")
    z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>""")
    z.writestr("ppt/theme/theme1.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="ImageToEditablePPT"><a:themeElements><a:clrScheme name="Office"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F1F1F"/></a:dk2><a:lt2><a:srgbClr val="F8F8F8"/></a:lt2><a:accent1><a:srgbClr val="0F766E"/></a:accent1><a:accent2><a:srgbClr val="E66B00"/></a:accent2><a:accent3><a:srgbClr val="F6D365"/></a:accent3><a:accent4><a:srgbClr val="57C4B8"/></a:accent4><a:accent5><a:srgbClr val="666666"/></a:accent5><a:accent6><a:srgbClr val="111111"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="PingFang"><a:majorFont><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/><a:cs typeface="PingFang SC"/></a:majorFont><a:minorFont><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/><a:cs typeface="PingFang SC"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>""")
    if notes_count:
        z.writestr("ppt/notesMasters/notesMaster1.xml", notes_master_xml())
        z.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels", notes_master_rels_xml())


def write_pptx(manifest, out_path, manifest_path):
    write_deck([{"manifest": manifest, "manifest_path": Path(manifest_path)}], out_path, [])


def write_deck(page_entries, out_path, notes_entries):
    if not page_entries:
        raise ValueError("Deck has no pages")
    first_slide = page_entries[0]["manifest"].get("slide", {})
    width = emu(first_slide.get("width", 13.333))
    height = emu(first_slide.get("height", 7.5))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    notes_by_page = {int(entry.get("page_index", 0)): entry for entry in notes_entries if entry.get("text")}
    notes_indices = sorted(notes_by_page)
    normalized_entries = [
        {**entry, "manifest": normalize_manifest(entry["manifest"])}
        for entry in page_entries
    ]
    manifests = [entry["manifest"] for entry in normalized_entries]
    media_index = 1
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml(manifests, notes_indices))
        write_common_parts(z, len(page_entries), width, height, len(notes_by_page))
        for slide_index, entry in enumerate(normalized_entries, start=1):
            manifest = entry["manifest"]
            notes_index = slide_index if slide_index in notes_by_page else None
            z.writestr(f"ppt/slides/slide{slide_index}.xml", slide_xml(manifest))
            z.writestr(f"ppt/slides/_rels/slide{slide_index}.xml.rels", rels_xml(manifest, media_index, notes_index))
            base = Path(entry["manifest_path"]).resolve().parent
            for item in manifest.get("images", []):
                src = Path(item["path"])
                if not src.is_absolute():
                    src = base / src
                z.write(src, f"ppt/media/image{media_index}{image_ext(src)}")
                media_index += 1
            if notes_index is not None:
                note = notes_by_page[slide_index]
                notes_xml = note.get("notes_xml")
                if notes_xml and Path(notes_xml).exists():
                    z.writestr(f"ppt/notesSlides/notesSlide{notes_index}.xml", Path(notes_xml).read_bytes())
                else:
                    z.writestr(f"ppt/notesSlides/notesSlide{notes_index}.xml", notes_slide_xml(note.get("text", "")))
                z.writestr(f"ppt/notesSlides/_rels/notesSlide{notes_index}.xml.rels", notes_rels_xml(slide_index))


def page_entries_from_deck_manifest(deck_manifest_path):
    deck_path = Path(deck_manifest_path).resolve()
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    root = Path(deck.get("job_dir", deck_path.parent)).resolve()
    entries = []
    for page in deck.get("pages", []):
        manifest_path = Path(page.get("manifest", ""))
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries.append({"manifest": manifest, "manifest_path": manifest_path})
    notes_path = deck.get("notes_manifest")
    notes_entries = []
    if notes_path:
        notes_file = Path(notes_path)
        if not notes_file.is_absolute():
            notes_file = root / notes_file
        if notes_file.exists():
            notes_entries = json.loads(notes_file.read_text(encoding="utf-8")).get("notes", [])
            for note in notes_entries:
                notes_xml = note.get("notes_xml")
                if notes_xml:
                    notes_xml_path = Path(notes_xml)
                    if not notes_xml_path.is_absolute():
                        notes_xml_path = root / notes_xml_path
                    note["notes_xml"] = str(notes_xml_path)
    return entries, notes_entries


def output_path_from_deck_manifest(deck_manifest_path):
    deck_path = Path(deck_manifest_path).resolve()
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    root = Path(deck.get("job_dir", deck_path.parent)).resolve()
    output = Path(deck.get("output", "deck_edited.pptx"))
    if not output.is_absolute():
        output = root / output
    return output


def render_preview(manifest, manifest_path, out_path):
    from PIL import Image, ImageColor, ImageDraw, ImageFont

    manifest = normalize_manifest(manifest)
    slide = manifest.get("slide", {})
    width_in = float(slide.get("width", 13.333))
    height_in = float(slide.get("height", 7.5))
    scale = int(manifest.get("preview_scale", 120))
    canvas = Image.new("RGB", (int(width_in * scale), int(height_in * scale)), ImageColor.getrgb(slide.get("background", "#ffffff")))
    base = Path(manifest_path).resolve().parent
    draw = ImageDraw.Draw(canvas)

    def open_preview_image(src):
        if src.suffix.lower() != ".svg":
            return Image.open(src).convert("RGBA")
        convert = "/opt/homebrew/bin/magick"
        if not Path(convert).exists():
            convert = "/opt/homebrew/bin/convert"
        if not Path(convert).exists():
            print(f"Warning: cannot preview SVG without ImageMagick: {src}", file=sys.stderr)
            return None
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            subprocess.run([convert, str(src), handle.name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return Image.open(handle.name).convert("RGBA")

    def render_shape(item):
        box = [item.get("left", 0) * scale, item.get("top", 0) * scale, (item.get("left", 0) + item.get("width", 1)) * scale, (item.get("top", 0) + item.get("height", 1)) * scale]
        fill = preview_color(item.get("fill"))
        outline = preview_color(item.get("stroke", "#000000"))
        width = max(1, int(float(item.get("stroke_width", 1))))
        if item.get("type") == "line":
            if "points" in item:
                points = [value * scale for value in item["points"]]
                draw.line(points, fill=outline, width=width)
                return
            if item.get("dash"):
                draw_dashed_line(draw, box, outline, width)
            else:
                draw.line(box, fill=outline, width=width)
        elif item.get("type") == "ellipse":
            draw.ellipse(box, fill=None if fill in (None, "none") else fill, outline=None if outline == "none" else outline, width=width)
        elif item.get("type") == "roundRect" or item.get("preset") == "roundRect":
            radius = int(float(item.get("radius", 0.12)) * scale)
            draw.rounded_rectangle(box, radius=radius, fill=None if fill in (None, "none") else fill, outline=None if outline == "none" else outline, width=width)
        else:
            draw.rectangle(box, fill=None if fill in (None, "none") else fill, outline=None if outline == "none" else outline, width=width)

    def render_image(item):
        src = Path(item["path"])
        if not src.is_absolute():
            src = base / src
        img = open_preview_image(src)
        if img is None:
            return
        img = img.resize((max(1, int(item.get("width", 1) * scale)), max(1, int(item.get("height", 1) * scale))))
        canvas.paste(img, (int(item.get("left", 0) * scale), int(item.get("top", 0) * scale)), img)

    def render_text(item):
        preview_font_scale = float(item.get("preview_font_scale", manifest.get("preview_font_scale", 1.0)))
        size = max(1, int(float(item.get("font_size", 18)) * scale / 72 * preview_font_scale))
        font_path = choose_preview_font(item.get("preview_font"))
        try:
            font = ImageFont.truetype(font_path, size=size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        if item.get("paragraphs"):
            lines = []
            for paragraph in item["paragraphs"]:
                if isinstance(paragraph, str):
                    lines.append(paragraph)
                else:
                    lines.append("".join(str(run.get("text", "")) for run in paragraph.get("runs", [])))
            preview_text = "\n".join(lines)
        elif item.get("runs"):
            preview_text = "".join(str(run.get("text", "")) for run in item["runs"])
        else:
            preview_text = item.get("text", "")
        fill = preview_color(item.get("color", "#111111"))
        align = item.get("align", "left") if item.get("align", "left") in ("left", "center", "right") else "left"
        x = int(item.get("left", 0) * scale)
        y = int(item.get("top", 0) * scale)
        rotation = float(item.get("rotation", 0) or 0)
        if rotation:
            layer_w = max(1, int(item.get("width", 1) * scale))
            layer_h = max(1, int(item.get("height", 0.4) * scale))
            layer = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
            layer_draw = ImageDraw.Draw(layer)
            layer_draw.multiline_text((0, 0), preview_text, fill=fill, font=font, spacing=4, align=align)
            rotated = layer.rotate(-rotation, expand=True)
            canvas.paste(rotated, (x, y), rotated)
            return
        draw.multiline_text((x, y), preview_text, fill=fill, font=font, spacing=4, align=align)

    layered = []
    for index, item in enumerate(manifest.get("shapes", [])):
        layered.append((float(item.get("z_index", 100)), index, render_shape, item))
    for index, item in enumerate(manifest.get("images", [])):
        layered.append((float(item.get("z_index", 200)), index, render_image, item))
    for index, item in enumerate(manifest.get("text_boxes", [])):
        layered.append((float(item.get("z_index", 300)), index, render_text, item))
    for _z_index, _order, renderer, item in sorted(layered, key=lambda entry: (entry[0], entry[1])):
        renderer(item)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def choose_preview_font(preferred):
    candidates = [
        preferred,
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def draw_dashed_line(draw, box, fill, width):
    x1, y1, x2, y2 = box
    dash = 8
    gap = 6
    if abs(y2 - y1) <= abs(x2 - x1):
        step = dash + gap
        x = min(x1, x2)
        end = max(x1, x2)
        y = y1
        while x < end:
            draw.line((x, y, min(x + dash, end), y), fill=fill, width=width)
            x += step
    else:
        step = dash + gap
        y = min(y1, y2)
        end = max(y1, y2)
        x = x1
        while y < end:
            draw.line((x, y, x, min(y + dash, end)), fill=fill, width=width)
            y += step


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--deck-manifest")
    parser.add_argument("--out")
    parser.add_argument("--preview")
    args = parser.parse_args()
    if args.deck_manifest:
        entries, notes_entries = page_entries_from_deck_manifest(args.deck_manifest)
        out = Path(args.out) if args.out else output_path_from_deck_manifest(args.deck_manifest)
        write_deck(entries, out, notes_entries)
        print(f"Wrote {out}")
        return
    if not args.manifest:
        parser.error("manifest is required unless --deck-manifest is used")
    if not args.out:
        parser.error("--out is required unless --deck-manifest provides an output")
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    write_pptx(manifest, args.out, args.manifest)
    if args.preview:
        render_preview(manifest, args.manifest, args.preview)
    print(f"Wrote {args.out}")
    if args.preview:
        print(f"Wrote {args.preview}")


if __name__ == "__main__":
    main()
