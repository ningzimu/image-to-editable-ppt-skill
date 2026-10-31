# Manifest Schema

This document describes the responsibilities, owners, and current field contracts for `editppt` run/page JSON files. All key state is advanced by `editppt` commands; page reconstructors write only page-local files.

## Contents

- `deck_manifest.json`
- `page_jobs.json`
- `page_request.json`
- `page_result.json`
- `pages/page_NNN/validation.json`
- `pages/page_NNN/manifest.json` (including Native tables)
- `pages/page_NNN/imagegen-jobs.json`
- Asset sheet regions and split reports
- `notes_manifest.json`

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
  "image_backend": {
    "backend_id": "builtin-imagegen",
    "tool_name": "image_gen.imagegen",
    "required_parameters": {
      "generate": ["prompt"],
      "edit": ["prompt", "referenced_image_paths"]
    },
    "input_context_policy": "generate with prompt; before editing, view_image each input, then use prompt plus absolute local referenced_image_paths",
    "save_path_policy": "use only an explicit valid local result/output_hint path, then editppt image import; never scan for a newest file",
    "fallback_command": "editppt image generate/edit",
    "fallback_order": ["codex-oauth", "openai-compatible-api"],
    "fallback_policy": {
      "on": [
        "tool-unavailable",
        "tool-error",
        "input-unreadable",
        "no-valid-local-output"
      ],
      "missing_optional_parameters": false
    }
  },
  "pages": [],
  "notes_manifest": "notes_manifest.json",
  "output": "final/origin_edited.pptx"
}
```

`image_backend` is written by `editppt prepare` and may be overwritten by `editppt run backend` when needed. Parent-level backend selection policy lives in `SKILL.md` subsection "Image Backend Selection".

For `backend_id: "builtin-imagegen"`, these fields are required and have fixed meanings:

- `tool_name`: `image_gen.imagegen`, an agent tool rather than a Python or shell API.
- `required_parameters`: the complete required argument sets. Generation needs `prompt`; editing needs `prompt` plus absolute local paths in `referenced_image_paths`.
- `input_context_policy`: requires `view_image` on every edit input before the built-in call; generation has no image input.
- `save_path_policy`: permits only an explicit valid local result path, including `output_hint`, followed by `editppt image import`; newest-file directory scanning is forbidden.
- `fallback_command`: the CLI surface used only after the fallback policy matches.
- `fallback_order`: the CLI's internal order, Codex OAuth before a configured OpenAI-compatible API.
- `fallback_policy.on`: the only events that permit leaving the built-in tool: it is unavailable/not callable, its call errors, an edit input is unreadable, or it returns no valid local image.
- `fallback_policy.missing_optional_parameters`: always `false`; absent optional controls never authorize fallback.

Other backend metadata may describe model labels, runtime homes, or handoff text, but it does not change this order. Parent-level tool selection and user-interaction policy live in `SKILL.md` subsection "Image Backend Selection"; page reconstructors execute the copied contract above.

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

`dispatch` is written by `editppt run dispatch`. It includes `execution_mode`: `"worker"` for normal page-worker dispatch and `"local"` for the parent agent's single-page local claim; older dispatch records without this field are treated as `"worker"`. A page with status `dispatched` is an active execution lease until explicit completion, failure, cancellation, or lost-worker verification; elapsed time alone does not make it lost. `result` is written by `editppt run record`. `accepted` is written by `editppt run finalize`.

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

If the run uses an image backend, `page_request.json` must contain the same `image_backend` object without weakening or reordering its `fallback_policy` or `fallback_order`.

`slide` and `content_box` are computed automatically by `editppt prepare`. Inputs close to 16:9 use the standard widescreen canvas; other inputs use a custom canvas converted from the source image pixel dimensions. The agent must copy these two fields into the page `manifest.json` and must not compress, stretch, or recalculate the canvas.

## `page_result.json`

Owner: created by the page reconstructor, validated by `editppt run record`.

Includes:

- manifest path
- imagegen jobs path
- page pptx path
- preview path
- contact sheet path
- validation path
- page-local output hashes, which may be supplemented by `editppt run record`

`editppt run record` stores output `hashes` and `asset_hashes` under the page entry’s `result` in `page_jobs.json`. Asset keys are run-relative paths from `manifest.images`, and values are SHA-256 digests. Finalization rejects missing or changed recorded files before building. Legacy records without `asset_hashes` retain output-hash checks but cannot verify image freshness.

Minimal required shape (paths are relative to the page directory):

```json
{
  "page_manifest": "manifest.json",
  "imagegen_jobs": "imagegen-jobs.json",
  "page_pptx": "page.pptx",
  "preview": "preview.png",
  "contact_sheet": "split_assets_contact.png",
  "validation": "validation.json",
  "page_result": "page_result.json"
}
```

The `manifest` artifact is the authoritative page source for final assembly. `editppt run finalize` rebuilds the final deck from recorded page manifests in page order. The `page_pptx` artifact remains a page-level deliverability artifact and is validated by `editppt run record`, but it is not the final assembly input.

## `pages/page_NNN/validation.json`

Owner: created by the page reconstructor, read by `editppt run record`.

Purpose: page-level deliverability conclusion.

`line_geometry_violations` records mismatches between declared paths/stroke styles and the actual PPTX objects. A non-empty list fails page validation; final deck validation reports these mismatches under `page_contract_violations`.

Native table validation report fields:

- `native_tables`: number of native table objects in the PPTX.
- `editable_table_cells`: number of table cells containing native DrawingML text (`a:t`). These cells satisfy editable-text checks, including on table-only pages.
- `table_structure_violations`: differences between manifest tables and the built PPTX. A non-empty list fails validation; final deck validation also rechecks native table structure.

Must contain at top level:

```json
{
  "passed": true
}
```

`passed` must be a boolean. `editppt run record` only reads top-level `passed` to decide whether the page can enter final assembly. `status: "pass"`, `runtime_validation.passed`, or other nested fields may remain as supplemental information, but they cannot replace top-level `passed`.

## `pages/page_NNN/manifest.json`

Owner: page reconstructor.

Purpose: source of truth for page-level PPTX construction.

The manifest is not a summary of a separately authored `page.pptx`. It is the build contract for both page-level validation and final deck assembly. A page may not pass validation if the page PPTX can only be reproduced by custom page-local code while the manifest lacks object positions.

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

`slide`, `content_box`, and `source.width_px/source.height_px` must come from `page_request.json`. All `box_px`, `points_px`, `polygon_px`, and `path_px` point values use `source.png` pixel coordinates; the runtime maps these coordinates into `content_box` instead of stretching them to the whole slide. Coordinate layouts:

- `box_px: [x, y, width, height]`
- `points_px: [x1, y1, x2, y2]`

Positioned build object requirements:

- Every `text_boxes[]` item must have `box_px`. Text in `text_inventory` does not create a positioned text box.
- Every `images[]` item must have `box_px`.
- Every `tables[]` item must have `box_px` with positive width and height.
- Every non-line `shapes[]` item must have `box_px`.
- Every line shape must have `points_px`.

`text_inventory` and `visual_inventory` are only inventories; they do not substitute for positioned `text_boxes`, `images`, `shapes`, and `tables`. The manifest must be sufficient to rebuild the page without reading any custom page script.

Missing coordinates are page-contract violations. The runtime must reject them during `editppt run record` and deck validation because otherwise missing values fall back to default positions such as the top-left corner.

**Native tables**

`tables` is optional and defaults to `[]`, preserving existing manifests. Each item builds one native DrawingML `a:tbl` object. Object-source decisions live in `page-decision-tree.md` section 3.3, "Structural Primitives and Layout Objects."

- `id` optionally names the table; `z_index` defaults to `250`.
- `box_px: [x, y, width, height]` positions the entire table in source pixels, using the same content-area mapping as other objects.
- `cells` is a non-empty rectangular two-dimensional array. Each slot is a string or an object with `text`, optional `row_span` / `col_span`, and optional `style`. Spans are positive integers and default to `1`.
- `column_widths` and `row_heights` are optional lists of positive relative weights, with exactly one weight per column or row. They scale to the table box; omitted lists assign equal sizes.
- A merged rectangle is declared only in its top-left cell. All covered slots must be `""`, `{}`, or `{"text": ""}`. Overlapping merges, out-of-grid spans, and content or style in covered slots are rejected.
- `style` on the table supplies cell defaults; `cells[r][c].style` overrides individual fields. Supported fields are `font`, `font_size`, `color`, `bold`, `italic`, `align`, `valign`, `wrap`, `fit_text`, `fill`, `stroke`, `stroke_width`, and `margin_left`, `margin_right`, `margin_top`, `margin_bottom`.
- Defaults: `font: "PingFang SC"`, `font_size: 18` points, `color: "#111111"`, `align: "left"`, `valign: "top"`, `wrap: "none"`, `fill: "#FFFFFF"`, `stroke: "#000000"`, `stroke_width: 1` point, and each margin `0.05` inches. Font fitting is enabled by default. Alignment values follow "Text alignment" below.
- Cell strings, including newline-separated text, participate in text coverage validation.

Example with a merged header and two data columns:

```json
{
  "tables": [{
    "id": "results",
    "box_px": [80, 120, 640, 180],
    "column_widths": [2, 1],
    "row_heights": [1, 1],
    "style": {"font_size": 16, "valign": "middle"},
    "cells": [
      [{"text": "Results", "col_span": 2, "style": {"bold": true, "fill": "#E8EEF5"}}, ""],
      ["Completed", "24"]
    ]
  }]
}
```

**Native paths and stroke styles**

The object-source and granularity rules live in `page-decision-tree.md` section 3.3, "Structural Primitives and Layout Objects."

- `shapes[].type: "path"` requires `box_px` with positive width and height and a non-empty `path_px` command list. It cannot also specify `points_px`, `polygon_px`, `preset`, `flip_h`, or `flip_v`; express its direction in the path coordinates. All point pairs are absolute `source.png` pixel coordinates, not coordinates relative to the box; the runtime maps them into the declared box and slide content area.
- Each command has `op` and `points`. Supported commands are `moveTo` (one `[x, y]` pair), `lnTo` (one endpoint), `quadBezTo` (one control point followed by the endpoint), `cubicBezTo` (two control points followed by the endpoint), and `close` (empty `points`).
- The first command is the only `moveTo`; at least one drawing command follows. Optional `close` may occur only once, at the end. All coordinates must be finite numbers. An open path has `fill: "none"`.
- `dash` defaults to `solid` and accepts `solid`, `dot`, `dash`, `lgDash`, `dashDot`, `lgDashDot`, `lgDashDotDot`, `sysDash`, `sysDot`, `sysDashDot`, or `sysDashDotDot`.
- `start_arrow` and `end_arrow` default to `none` and accept only `none` or `triangle`. Arrowheads are supported only on `line` shapes and open paths.
- Optional `semantic_line_id` is a non-empty string identifying one logical line. It must be unique across the page's shapes; repeating it on multiple shapes is a contract violation, including when those shapes are grouped. Omission does not waive the section 3.3 review.

Example of one open dashed curve with an endpoint arrow:

```json
{
  "type": "path",
  "box_px": [100, 80, 300, 140],
  "semantic_line_id": "trend-projection",
  "path_px": [
    {"op": "moveTo", "points": [[100, 220]]},
    {"op": "cubicBezTo", "points": [[180, 80], [280, 180], [400, 100]]}
  ],
  "fill": "none",
  "stroke": "00AACC",
  "stroke_width": 2,
  "dash": "dash",
  "end_arrow": "triangle"
}
```

Text-size fitting:

- `text_boxes[].font_size` is treated as the requested font size. The deterministic builder may clamp it downward during normalization when the requested size is too large for the resolved source-pixel box.
- Keep default fitting enabled for first drafts. Set `fit_text: false` only when the page author has manually calibrated the box and font size.
- `text_boxes[].box_px` should describe the source text bounds plus modest padding. Do not use an unrelated card, chart, or table cell group as the text box, because the fitter infers size from the supplied box. Badge-centered text is the explicit shared-box exception in `page-decision-tree.md` section 3.6.
- Optional tuning fields are `min_font_size`, `max_font_size`, `text_fit_safety`, and `line_height`.

Text alignment:

- `text_boxes[].align` accepts `left`, `center`, or `right` (default `left`). The equivalent DrawingML tokens `l`, `ctr`, and `r` are also accepted.
- `text_boxes[].valign` accepts `top`, `middle`, or `bottom` (default `top`); `center` is an alias for `middle`. The equivalent DrawingML tokens `t`, `ctr`, and `b` are also accepted.
- The deterministic builder translates these manifest values to valid DrawingML enum tokens. Unsupported values are page-contract violations instead of silently falling back to an application default.

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

- `mode`: `native-or-script`, `source-preserving-local-cleanup`, `imagegen-full-clean-base`, or similar.
- `source_consistency_contract`: which composition, perspective, object positions, colors, lighting, and key details are preserved.
- `removed_foreground`: which foreground objects were removed from the background and rebuilt later.
- `comparison_note`: the background consistency conclusion after comparing the preview against the source.

`asset_provenance` requirements — every path referenced in `images[]` must have a matching entry:

- `path`: the image path as referenced in `images[]`.
- `source`: the file the asset was produced from (for separated assets and clean bases this is typically `source.png` or the recorded asset sheet; for formulas the `.tex` file). The referenced file must exist.
- `source_type`: exactly one of `asset-sheet-separated`, `imagegen`, `latex-rendered-formula`, `user-provided`, `user-approved-rasterization`. No other value passes validation.
- `provenance_note`: a non-empty explanation of how the asset was produced.

New `visual_inventory` entries should declare `role` (`foreground`, `background`, `structure`, or `formula`) and may supply `object_type` (such as `icon` or `photo`). For `role: foreground`, supply `path` matching an image and its `asset_provenance`, plus `source_type` matching that provenance (`asset-sheet-separated` or `imagegen`). Descriptions and provenance notes explain the work; they are not keyword-based proof of the source method. Legacy entries remain supported; prefer these fields for unambiguous classification.

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

Formula source decisions and failure handling are defined in `page-decision-tree.md` section 3.2.

## `pages/page_NNN/imagegen-jobs.json`

Owner: created by `editppt prepare`, updated by `editppt image import` and `editppt image process-sheet` (`generate`/`edit` do not write it — importing the selected output is what records the job).

Purpose: record the generation and processing process for clean bases, asset sheets, and selected bitmap assets.

Each imported job records at least the selected output and the backend that actually produced it:

```json
{
  "schema_version": 1,
  "jobs": [
    {
      "job_id": "icon-sheet",
      "role": "asset_sheet",
      "status": "recorded",
      "source_image": "/absolute/path/from/tool-output.png",
      "output": "assets/icon-sheet.png",
      "output_sha256": "...",
      "backend": "builtin-imagegen",
      "fallback_reason": null
    }
  ]
}
```

`backend` is the actual producer: `builtin-imagegen`, `codex-oauth`, or `openai-compatible-api`; `unknown` is reserved for legacy page directories that have no `image_backend` contract. `editppt image import` requires an explicit producer, rejects files that are not readable images, and checks `backend`/`fallback_reason` against the page contract. `fallback_reason` is `null` when the preferred backend succeeded or the run selected a CLI contract directly; when a built-in contract enters its CLI fallback, it records the matching event from `image_backend.fallback_policy.on`.

State and provenance record rules are described in the State Principles section of `SKILL.md` and in the asset processing examples in `cli-helper.md`.

## Asset sheet regions and split reports

`asset-regions.json` is authored by the page reconstructor after inspecting the generated sheet. It contains `regions`, a nonempty array of `{ "name": "icon-a", "box": [x, y, width, height] }`. Names are unique safe filenames (PNG extension optional); coordinates are integer pixels of the **generated sheet**, not `source.png`. Boxes must have positive size, be inside the image, and not overlap. Each region must contain foreground surrounded by transparent margins; collectively regions cover all nonzero Alpha except the faint-residue allowance below. Empty grid slots are omitted.

The split report records `source`, `assets`, and each asset's `path`, `source`, `box`, `padded_box`, `area`, `merged_count`, and `size`; region mode also records `region_box`. Report boxes are `[left, top, right, bottom]` in generated-sheet pixels, unlike the region input's width/height form. `area` in region mode counts all nonzero Alpha pixels. Crops preserve the original RGBA pixels and retain disconnected fragments; padding is clipped to the owning region.

If all uncovered pixels together total at most 4 pixels with maximum Alpha 8 (on the 0–255 scale), region splitting accepts them as faint residue and emits `warnings: [{"code": "ignored_faint_residue", "pixel_count": 1, "max_alpha": 1, "box": [x1, y1, x2, y2]}]`. Any foreground touching a region boundary still fails, including a faint connected stroke; larger or more opaque uncovered content also fails. This never thresholds pixels inside a region. The unchanged source sheet retains residue for inspection.

## `notes_manifest.json`

Owner: created by `editppt prepare`, read by `editppt run finalize`.

Purpose:

- Original PPT/PPTX speaker notes.
- Notes hashes.
- Page mapping.

Notes are not handed to page workers, translated, summarized, or rewritten.
