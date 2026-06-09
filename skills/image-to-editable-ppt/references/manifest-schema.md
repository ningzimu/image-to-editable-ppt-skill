# Manifest Schema

This document describes the responsibilities, owners, and current field contracts for `editppt` run/page JSON files. All key state is advanced by `editppt` commands; page reconstructors write only page-local files.

## `deck_manifest.json`

Owner: created by `editppt prepare`; `editppt run backend` may update the image backend; `editppt run finalize` reads it and writes completion time.

Purpose:

- Input type.
- Page order.
- Page manifest paths.
- Notes manifest path.
- Final output path.
- Run-level image backend contract.
- Original user request.

Key fields:

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "input_type": "image|images|pdf|pptx",
  "max_concurrent_pages": 6,
  "image_backend": {},
  "pages": [],
  "notes_manifest": "notes_manifest.json",
  "output": "final/origin_edited.pptx"
}
```

`image_backend` is written with defaults by `editppt prepare` and may be overwritten by `editppt run backend` when needed.

## `page_jobs.json`

Owner: created by `editppt prepare`, updated by `editppt run` commands.

Purpose:

- Source of truth for page state.
- Dispatch records.
- Result records.

Structure:

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "max_concurrent_pages": 6,
  "pages": [
    {
      "page_id": "page_001",
      "status": "pending",
      "page_dir": "pages/page_001",
      "page_request": "pages/page_001/page_request.json",
      "source": "pages/page_001/source.png",
      "dispatch": null,
      "result": null
    }
  ]
}
```

`dispatch` is written by `editppt run dispatch`. `result` is written by `editppt run record`. `accepted` is written by `editppt run finalize`.

## `page_request.json`

Owner: `editppt prepare`.

Purpose: task boundary for the page worker.

Includes:

- page id
- page directory
- source image
- slide size
- content box
- max concurrent pages
- allowed write scope
- required outputs
- user constraints
- image backend contract

Must not include:

- page type prediction
- `imagegen_required` prediction
- object-level decisions

If the run uses an image backend, `page_request.json` must contain the same `image_backend`.

`slide` and `content_box` are computed automatically by `editppt prepare`. Inputs close to 16:9 use the standard widescreen canvas; other inputs use a custom canvas converted from the source image pixel dimensions. The agent must copy these two fields into the page `manifest.json` and must not compress, stretch, or recalculate the canvas.

## `page_result.json`

Owner: created by the page worker, validated by `editppt run record`.

Includes:

- manifest path
- imagegen jobs path
- page pptx path
- preview path
- contact sheet path
- validation path
- page-local output hashes, which may be supplemented by `editppt run record`

## `pages/page_NNN/validation.json`

Owner: created by the page worker, read by `editppt run record`.

Purpose: page-level deliverability conclusion.

Must contain at top level:

```json
{
  "passed": true
}
```

`passed` must be a boolean. `editppt run record` only reads top-level `passed` to decide whether the page can enter final assembly. `status: "pass"`, `runtime_validation.passed`, or other nested fields may remain as supplemental information, but they cannot replace top-level `passed`.

## `pages/page_NNN/manifest.json`

Owner: page worker.

Purpose: source of truth for page-level PPTX construction.

Must contain:

- `slide`
- `content_box`
- `source`
- `text_inventory`
- `visual_inventory`
- `background_strategy`
- `quality_checks`
- `text_boxes`
- `shapes`
- `images`
- `asset_provenance`
- page strategy

`slide`, `content_box`, and `source.width_px/source.height_px` must come from `page_request.json`. All `box_px`, `points_px`, and `polygon_px` values use `source.png` pixel coordinates; the runtime maps these coordinates into `content_box` instead of stretching them to the whole slide.

`text_inventory` may be a list of strings or a list of structured objects. In structured objects, the fields used for exact text validation are `text`, `required_text`, `items`, or `texts`; fields such as `id`, `decision`, `description`, and `note` are only records and are not used for exact text matching. Example:

```json
[
  {"id": "title", "text": "Market Overview", "decision": "native-text"},
  {"id": "metrics", "required_text": ["Annual recurring revenue", "42.8M"]}
]
```

`quality_checks` must include at least:

```json
{
  "font_size_calibrated": true,
  "visual_inventory_matched": true,
  "background_strategy_checked": true,
  "shape_corner_geometry_checked": true
}
```

`background_strategy` must explain at least:

- mode: `native-or-script`, `source-preserving-local-cleanup`, `imagegen-full-clean-base`, or similar.
- source consistency: which composition, perspective, objects, colors, lighting, and details are preserved.
- removed foreground: which foreground objects will be removed and rebuilt.
- comparison note: the background consistency conclusion after comparing preview against source.

`roundRect` shapes must record `source_corner_radius_px`; they may also record `corner_reason`. If the source is a straight-corner rectangle, use `rect`.

Recommended record:

```json
{
  "type": "roundRect",
  "box_px": [64, 169, 472, 187],
  "source_corner_radius_px": 12,
  "corner_category": "small-radius",
  "corner_reason": "source card corners are lightly rounded"
}
```

Allowed `corner_category` values: `straight`, `small-radius`, `large-radius`, `pill`. `straight` should not use `roundRect`.

`source-derived-rasterization` assets must record:

```json
{
  "path": "assets/example.png",
  "source": "source.png",
  "source_type": "source-derived-rasterization",
  "source_region_px": [100, 200, 60, 60],
  "require_edge_safe_alpha": true,
  "provenance_note": "Small isolated non-icon object cropped to preserve source identity."
}
```

`source_region_px` uses `[x, y, width, height]`. If `[left, top, right, bottom]` is used, the field name must be `source_bbox_px`.

`require_edge_safe_alpha` is an optional strict check: set it to `true` only when the asset should be fully inside a transparent canvas. By default, visible pixels touching an edge do not directly fail validation.

This source type is allowed only for small visual objects with no readable text, that are not icons or pictograms, are already naturally isolated, and have no background-structure attachment. It must not be used for icon separation, full pages, whole cards, whole charts, or text regions. Icons, pictograms, symbols, logo-like marks, and semantic badges must use image-backend source-faithful separation.

`latex-rendered-formula` formula assets must record:

```json
{
  "images": [
    {
      "id": "formula_c2_1",
      "path": "assets/formula_c2_1.svg",
      "box_px": [105, 392, 390, 90],
      "alt": "LaTeX rendered formula formula_c2_1",
      "z_index": 220
    }
  ],
  "asset_provenance": [
    {
      "path": "assets/formula_c2_1.svg",
      "source": "assets/formula_c2_1.tex",
      "source_type": "latex-rendered-formula",
      "provenance_note": "Rendered from LaTeX by editppt formula render-latex; visual fidelity is prioritized over formula editability."
    }
  ],
  "formula_inventory": [
    {
      "id": "formula_c2_1",
      "decision": "latex-rendered-image",
      "editable": false,
      "image": "assets/formula_c2_1.svg",
      "tex_source": "assets/formula_c2_1.tex"
    }
  ]
}
```

Formula images must be generated by `editppt formula render-latex`. Do not crop formulas from the source, and do not assemble complex formulas from hand-written native text boxes.

## `pages/page_NNN/imagegen-jobs.json`

Owner: created by `editppt prepare`, updated by `editppt image` commands.

Purpose: record the generation and processing process for clean bases, asset sheets, and selected bitmap assets.

State and provenance record rules are described in the State Principles section of `SKILL.md` and in the asset processing examples in `cli-helper.md`.

## `notes_manifest.json`

Owner: created by `editppt prepare`, read by `editppt run finalize`.

Purpose:

- Original PPT/PPTX speaker notes.
- Notes hashes.
- Page mapping.

Notes are not handed to page workers, translated, summarized, or rewritten.
