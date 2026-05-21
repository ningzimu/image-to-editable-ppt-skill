---
name: image-to-editable-ppt
description: Use when the user gives one or more slide images, an image-based PPT/PPTX, or a PDF and asks for an editable PowerPoint/PPTX, slide reconstruction, image-only presentation conversion, per-page editable rebuilds, or preservation of PPT speaker notes.
---
# Image to Editable PPT

## Purpose

Convert slide images, PDFs, image-based PPTX files, and locally normalizable PPT files into editable `.pptx` output. The workflow is: normalize inputs -> assign pages -> rebuild each page -> assemble the deck -> validate and repair.

This skill owns the full job folder, page delegation, editable text reconstruction, generated visual assets, PPTX assembly, speaker-note preservation, validation, and targeted repair. Use the built-in `image_gen` tool for clean visual layers and style-bearing non-text assets; use this skill's scripts for deterministic normalization, packaging, splitting, preview QA, and validation.

## Role Scope

This `SKILL.md` is written for both the parent agent and page subagents. Read the role labels before acting.

- Parent agent: executes Step 1, Step 2, Step 5, Step 6, Step 7, and Step 8. The parent owns job-level manifests, page dispatch, whole-deck preview review, final deck assembly, speaker notes, root validation, and final reporting.
- Page subagent: executes only Step 3 and Step 4 for its assigned `pages/page_NNN/` folder. It should actively inspect, repair, and retry inside that folder until the page is ready whenever possible. A page subagent must not assemble the deck, edit job-level files, edit other page folders, or rewrite speaker notes.
- Shared rules: all agents must follow the Output Contract, Job Folder Contract, page readiness gate, and FAQ constraints that apply to their role.

If you are a page subagent and this file mentions parent-only work, treat that content as context, not permission to perform it.

## Output Contract

- One image -> one-slide editable `.pptx`.
- Multiple images -> one slide per image; do not promise relative image order.
- PDF -> one output slide per PDF page, preserving page order.
- PPT/PPTX -> one output slide per source slide, preserving slide order.
- PPT/PPTX speaker notes -> copied unchanged to matching output slides. Do not OCR, summarize, translate, rewrite, or send notes to subagents.
- Final deck filename -> `{origin_name}_edited.pptx`, where `origin_name` is the first input file stem.

## Job Folder Contract

Every run must create a fresh job folder and keep all intermediate and final files inside it:

```text
output/image-to-editable-ppt/<job-id>/        # Fresh per-run job folder; keep all intermediate and final files here.
├── input/                                    # Copied original input files; never mutate user originals in place.
├── deck_manifest.json                       # Job-level manifest: input type, page order, page paths, notes manifest, final output name.
├── deck_preview_contact.png                 # Parent QA image combining all page preview.png files before final PPTX assembly.
├── {origin_name}_edited.pptx                # Final editable PowerPoint deck; origin_name is the first input file stem.
├── validation.json                          # Final deck validation report.
├── notes_manifest.json                      # Extracted PPT/PPTX speaker notes, copied unchanged into matching output slides.
└── pages/                                   # Per-page work area; one page_NNN folder per output slide.
    └── page_001/                            # Page-scoped folder owned by exactly one page subagent.
        ├── source.png                       # Normalized source image for this page.
        ├── run_request.json                 # Optional parent-written task boundary: source path, write scope, requested outputs, user constraints.
        ├── imagegen-jobs.json               # Audit log for built-in image_gen clean-base, asset-sheet, or repair generations.
        ├── assets/                          # Final per-object PNG assets referenced by manifest.json.
        ├── preview.png                      # Rendered reconstructed page preview for parent whole-deck review.
        ├── split_assets_contact.png         # Human QA image with origin and preview side by side.
        ├── manifest.json                    # Page reconstruction manifest consumed by build_pptx_from_manifest.py.
        └── validation.json                  # Page-level validation report from validate_pptx.py --manifest.
```

## Execution Steps

### Step 1. Prepare Runtime And Inputs (Parent)

Step 1.1. Bootstrap the local runtime when dependencies may be missing:

```bash
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py bootstrap
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py doctor
```

Step 1.2. Normalize inputs with `prepare_inputs.py`. If normalization fails, report the input-normalization blocker and ask for a PDF export or per-slide images. Do not silently install additional system renderers.

```bash
python3 {skill_root}/scripts/prepare_inputs.py slide1.png slide2.png
python3 {skill_root}/scripts/prepare_inputs.py deck.pdf
python3 {skill_root}/scripts/prepare_inputs.py image_based_deck.pptx
python3 {skill_root}/scripts/prepare_inputs.py legacy_deck.ppt
```

Step 1.3. Confirm these files exist before reconstruction begins:

- `deck_manifest.json`
- `notes_manifest.json`
- `pages/page_NNN/source.png` for every expected page

Step 1.4. Treat `deck_manifest.json` as the source of truth for page count, page order, note manifest path, and final output name.

### Step 2. Assign Page Reconstruction (Parent)

Step 2.1. For a single image, the parent agent may rebuild the only page directly.

Step 2.2. For multiple images, PDF, PPT, and PPTX jobs, dispatch exactly one subagent per output page. This is mandatory. If subagents are unavailable, stop before page reconstruction and report the dispatch blocker. Continue without subagents only if the user explicitly approves a single-agent run.

Step 2.3. The parent owns only job-level files:

- `deck_manifest.json`
- `notes_manifest.json`
- final `{origin_name}_edited.pptx`
- root `validation.json`
- page ordering and note preservation

Step 2.4. The parent may write `run_request.json`, but only as a task-boundary file. It may include source path, allowed write scope, requested outputs, and user constraints. It must not pre-fill or prescribe `page_type`, `imagegen_required`, `skip_imagegen_allowed`, or `imagegen_skip_reason`; those are page-analysis decisions owned by the page subagent and recorded in `manifest.json`.

Step 2.5. Each subagent may create or edit only files inside its assigned `pages/page_NNN/` folder. Subagents must not edit job-level manifests, other page folders, source input files, speaker notes, or the final deck.

### Step 3. Rebuild Each Page (Page Subagent)

Step 3.1. Inspect `source.png` and create the page inventory before generating anything. The page subagent owns these decisions and records them in `manifest.json`:

- classify the page type
- list every readable text string in `text_inventory`
- list required non-text visual objects
- identify complex backgrounds, large photos, charts, screenshots, icons, badges, decorative marks, shadows, tapes, textured notes, hand-drawn marks, sketchy arrows, and reusable illustration parts
- decide which objects can be native PPT geometry
- decide which objects require `image_gen`
- record `imagegen_required`, `skip_imagegen_allowed`, and skip evidence

Step 3.2. Build a layer plan before writing slide objects. Use this order:

1. clean background/base layer
2. native PPT geometry layer
3. independent foreground image assets
4. editable text layer

Step 3.3. For a pure flat background, rebuild it as a native fill or simple native shapes. For a complex non-solid background, use `image_gen` to reconstruct a clean bottom background/base. Complex backgrounds include photo backgrounds, texture backgrounds, illustration backgrounds, dense dashboard/report bases, large screenshot-like regions, chart-context backgrounds, and pages where foreground decorations sit on top of a non-flat base.

Step 3.3.1. The clean background/base should preserve the background image, visual field, panels, photo regions, chart context, texture, shadows, spacing, and page atmosphere.

Step 3.3.2. The clean background/base must remove readable text and remove foreground objects that should stay editable or movable, including decorations, icons, foreground photos, chart marks, badges, arrows, tapes, stickers, and callouts.

Step 3.3.3. Reject the clean background/base if it contains text ghosts, pseudo text, duplicated foreground assets, missing layout regions, invented objects, or obvious visual drift.

Step 3.3.4. Place the clean background/base as the lowest layer in `manifest.json` with the lowest `z_index`.

Step 3.4. Decompose foreground visuals into object-level layers. For dashboard, report, chart, diagram, technical-route, and dense infographic pages, never replace the foreground with one combined raster image. Rebuild simple structural elements as native PPT geometry, and use `image_gen` asset sheets only for independent style-bearing or raster objects that need to remain movable:

- large foreground pictures or screenshot-like regions that must stay movable
- icons and pictograms
- chart glyphs, visual marks, decorative data callouts, KPI pictograms, legends-as-icons, and chart embellishments that are not rebuilt as native geometry
- badges, labels, stickers, and callout marks
- hand-drawn marks, tape, textured notes, decorative strokes, shadows, sketchy arrows, underlines, and reusable illustration parts

Step 3.4.1. For charts and reports, rebuild structural cards, tables, chart frames, axes, gridlines, simple bars, simple lines, and plain status blocks as native PPT shapes when practical. Use generated assets only for the visual parts that carry style or illustration detail. Rebuild every chart label, tick label, legend text, value label, and annotation as native PPT text; do not put readable chart text inside generated assets.

Step 3.4.2. Ask `image_gen` for sparse single-sheet layouts on a pure chroma-key background. Choose a key color absent from the assets, for example avoid green for green icons and avoid magenta for magenta/purple assets. Require pure key-colored space between visible assets: at least 260 px for dense pages and at least 220 px for simpler pages. Spacing is more important than asset size; allow assets to shrink so they do not touch.

Step 3.4.3. Each listed asset must be internally complete as one object, with no clipped edges, no touching neighbors, no cross-asset shadows, no repeated fragments, and no surrounding card/text/page region baked in. Do not include readable text in the asset sheet. If a source object contains text, generate only the no-text visual container or mark, then rebuild the text natively.

Step 3.4.4. Remove the chroma key locally, split the assets, inspect extracted PNGs, and keep only assets that are complete, unclipped, and visually usable. Do not accept crowded asset sheets as final inputs to splitting; regenerate the sheet before trying to rescue severe crowding with post-processing.

Step 3.4.5. If one asset is bad, repair only that asset or a small focused sheet. Do not regenerate the whole page unless the base layer itself is wrong.

Step 3.5. Rebuild native PPT geometry after the base layer is decided. Native PPT shapes are appropriate for true primitives such as simple lines, rectangles, circles, table borders, chart axes, and simple bars.

Step 3.5.1. Preserve source geometry semantics. Rectangular panels, tables, cards, chart frames, and report containers stay rectangular unless the source object is visibly rounded.

Step 3.5.2. Do not replace style-bearing visual objects with local drawing code, PowerPoint preset-shape approximations, source crops, or placeholders. Source-image crops are allowed only as diagnostic alignment references unless the user explicitly approves lower editability.

Step 3.6. Separate all readable text from the visual layers and rebuild it as visible native PPT text boxes. Do not ask `image_gen` to render exact text. Hidden, transparent, tiny, off-canvas, or metadata-only text does not count as editable text.

Step 3.6.1. If source text sits on a complex background, remove it from the generated clean background/base first, then place editable text boxes above the cleaned area.

Step 3.6.2. If source text is part of a label, badge, tape, sticker, note, or callout, split the object: generate the no-text visual container as an asset or native shape, then rebuild the text as native PPT text on top.

Step 3.7. Skip `image_gen` only when every non-text visual object is a plain editable primitive such as a line, rectangle, rounded rectangle, circle, simple chart bar, or table border. Record the skip evidence in `manifest.json`.

Step 3.8. Do not mark a page `blocked` at the first failed attempt. First try targeted self-repair inside the assigned page folder: regenerate only the bad background region or asset sheet, resplit assets, adjust coordinates, enlarge text boxes, fix manifest paths, and rerun validation. Use `completion_status: "blocked"` only when the page subagent has hit a hard blocker it cannot solve within its write scope, such as unavailable required tooling, unusable source input, repeatedly failed required `image_gen` output, or missing information needed to reconstruct the page.

Step 3.8.1. When a hard blocker remains, write `completion_status: "blocked"` and a non-empty, specific `blocker_reason` in `manifest.json`. The reason must state what was attempted, what still fails, and what guidance or input is needed next. Do not create a ready page manifest.

Step 3.9. Record source-image pixel coordinates in the page manifest:

- `source.width_px` and `source.height_px`
- `box_px: [x, y, width, height]` for text, images, and filled shapes
- `points_px: [x1, y1, x2, y2]` for straight line shapes
- explicit `z_index`: base/background first, native geometry next, generated assets next, editable text last

Step 3.10. Keep text boxes roomy. Prefer widening/tallening boxes, explicit line breaks, and `valign: "middle"` for labels before shrinking font size.

### Step 4. Validate Each Page (Page Subagent; Parent Reviews)

Step 4.1. Build the page PPTX and run page validation:

```bash
python3 {skill_root}/scripts/build_pptx_from_manifest.py manifest.json --out output.pptx
python3 {skill_root}/scripts/validate_pptx.py output.pptx --manifest manifest.json --report validation.json
```

Step 4.2. Generate page QA with `run_page_experiment.py`. It writes `preview.png` for parent whole-deck review and `split_assets_contact.png` with `origin` and `preview` side by side for page-level comparison.

```bash
python3 {skill_root}/scripts/run_page_experiment.py pages/page_001 --preview-scale 144
```

Step 4.3. If validation or visual QA fails, repair the smallest failing scope before reporting back:

- bad or missing asset -> regenerate a focused `image_gen` asset sheet, resplit, and replace only that asset
- text issue -> update `text_inventory`, text box content, size, wrapping, or alignment
- clipped/cramped text -> enlarge `box_px`, add line breaks, or use `valign` before reducing font size
- broken image relationship -> fix the manifest path or regenerate the missing asset
- baked-in text overlap -> regenerate the clean no-text background/base
- layout drift -> adjust source-coordinate placement and rerun `split_assets_contact.png`

Step 4.4. Repeat Step 4.1 through Step 4.3 until the page is ready or a hard blocker remains. A page is ready only when all are true:

- `manifest.json` has `completion_status: "ready_for_assembly"`
- `validate_pptx.py --manifest` passes
- `preview.png` exists and is visually acceptable
- `split_assets_contact.png` exists and is visually acceptable
- all readable source strings are represented as visible editable PPT text unless explicitly documented otherwise
- required non-text visual objects are represented as native shapes or generated assets with provenance

Step 4.5. If a hard blocker remains after targeted self-repair, the page subagent reports `completion_status: "blocked"` and a specific `blocker_reason` in `manifest.json`. The parent must not assemble it; the parent re-dispatches that page with the blocker reason, validation output, `split_assets_contact.png` when present, and concrete repair instructions.

### Step 5. Review Whole-Deck Preview (Parent Only)

Step 5.1. Before final PPTX assembly, combine every page's `preview.png` into one deck-level QA sheet:

```bash
python3 {skill_root}/scripts/make_deck_preview_contact.py \
  output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

Step 5.2. Inspect `deck_preview_contact.png` as the whole-deck visual gate. Check page order, missing pages, repeated pages, obvious layout drift, crude assets, broken backgrounds, text overlap, clipped text, and inconsistent reconstruction quality across pages.

Step 5.3. If any page looks poor, do not assemble the deck. Repair those pages first. For independent page problems, the parent may dispatch multiple page subagents in parallel, each scoped only to its own `pages/page_NNN/` folder and given the concrete visual issue, validation output, current `preview.png`, and current `split_assets_contact.png`.

Step 5.4. After repairs, rerun page validation and regenerate the affected page `preview.png` and `split_assets_contact.png`, then regenerate `deck_preview_contact.png`. Repeat until the whole-deck preview has no known page-quality problems.

### Step 6. Assemble The Deck (Parent Only)

Step 6.1. Assemble only after every expected page in `deck_manifest.json` is ready and the whole-deck preview gate passes. Do not skip, drop, renumber, or replace blocked/missing/invalid pages to make assembly pass.

```bash
python3 {skill_root}/scripts/build_pptx_from_manifest.py \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

Step 6.2. The output path comes from `deck_manifest.output` and must be `{origin_name}_edited.pptx`.

Step 6.3. For PPT/PPTX input, copy notes from `notes_manifest.json` to matching slides unchanged.

### Step 7. Validate And Repair The Deck (Parent)

Step 7.1. Run deck validation:

```bash
python3 {skill_root}/scripts/validate_pptx.py \
  output/image-to-editable-ppt/<job-id>/{origin_name}_edited.pptx \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --report output/image-to-editable-ppt/<job-id>/validation.json
```

Step 7.2. Inspect the assembled output, `deck_preview_contact.png`, and each affected page's `preview.png` and `split_assets_contact.png`. Structural validation is not enough.

Step 7.3. Repair the smallest failing scope:

- text issue -> update `text_inventory` or text boxes
- clipped/cramped text -> enlarge box, add line break, use `valign`, then reduce font only if needed
- missing or low-fidelity asset -> rerun targeted `image_gen`, then resplit/recrop only affected assets
- broken image relationship -> fix manifest path or regenerate the asset file
- baked-in text overlap -> replace source background with a clean no-text generated background
- layout drift -> adjust manifest coordinates and regenerate `split_assets_contact.png`

Step 7.4. Repeat Step 4, Step 5, or Step 7 until page validation, whole-deck preview review, and deck validation pass. Do not report completion while any expected page is blocked, missing, visually poor, missing `preview.png`, or absent from `deck_preview_contact.png`.

### Step 8. Report Completion (Parent)

Report only after the final deck is assembled and validation passes. Include:

- final PPTX path
- `deck_preview_contact.png` path
- root `validation.json` path
- any known fidelity limits or user-approved rasterization

## Commands

Crop one generated asset-sheet region into a reusable image and append provenance. This helper is for generated asset sheets only; do not use it to crop non-text assets from `source.png`:

```bash
python3 {skill_root}/scripts/crop_image_asset.py \
  --input imagegen_asset_sheet_alpha.png \
  --out assets/icon_trigger.png \
  --box 120,80,260,220 \
  --manifest manifest.json \
  --source-type imagegen \
  --provenance-note "Icon cropped from the selected imagegen asset sheet and visually inspected."
```

Split a transparent asset sheet into component PNG assets after chroma-key removal:

```bash
python3 {skill_root}/scripts/split_alpha_components.py \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --names icon_doc.png,icon_book.png,icon_bulb.png,icon_chart.png,icon_target.png \
  --sort x \
  --square
```

When processing a new asset sheet, pass the selected generated image explicitly:

```bash
python3 {skill_root}/scripts/run_page_experiment.py pages/page_001 \
  --asset-sheet-source /path/to/generated_sheet.png \
  --chroma imagegen_icon_sheet_magenta.png \
  --asset-names icon_a.png,icon_b.png,icon_c.png \
  --split-sort x \
  --square-assets \
  --force-chroma
```

Combine per-page `preview.png` files into the parent whole-deck QA sheet:

```bash
python3 {skill_root}/scripts/make_deck_preview_contact.py \
  output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

## FAQ

### Q1. Subagents are unavailable. Can the parent rebuild all pages?

For multi-image, PDF, PPT, and PPTX jobs, no. Stop before page reconstruction and report subagent dispatch as the blocker. Continue as a parent-only rebuild only after explicit user approval.

### Q2. A subagent returned `completion_status: "blocked"`. What happens next?

First check that the subagent attempted targeted self-repair and wrote a specific `blocker_reason` in `manifest.json`. Then the parent reads that reason, checks `validation.json` and `split_assets_contact.png` when present, and re-dispatches the same page with targeted repair instructions. Blocked pages are repair tasks, not slides to omit.

### Q3. Can the parent decide page type or whether `image_gen` is required?

No. The parent may write task boundaries in `run_request.json`, but page classification and `imagegen_required` decisions belong to the page subagent and must be recorded in `manifest.json`.

### Q4. Can a page use the original `source.png` as a full-slide background with editable text on top?

No. That duplicates baked-in source text under editable text and is a failed editable reconstruction. Use a clean no-text generated background when a raster background is needed.

### Q5. When can `image_gen` be skipped?

Only when all non-text visual objects are plain editable primitives. If the source contains icons, pictograms, decorative marks, sketchy arrows, stickers, textured notes, tapes, shadows, or other style-bearing objects, use `image_gen` or block with a reason.

### Q6. What if generated assets look crude or wrong in `split_assets_contact.png`?

The page subagent should repair it directly before reporting back: generate a focused repair asset sheet for the affected object(s), replace only the bad assets, rerun page validation, and regenerate `split_assets_contact.png`. Report `blocked` only if targeted repair still cannot produce usable assets.

### Q7. How should clipped or cramped text be fixed?

First enlarge `box_px`. Then add source-matching explicit line breaks or use `valign: "middle"` for labels. Reduce font size only after the text box has enough slack.

### Q8. What if a PPT/PPTX has speaker notes?

The parent preserves notes via `notes_manifest.json` and copies them unchanged to matching output slides during assembly. Subagents must not rewrite or analyze speaker notes.

### Q9. Which visual QA files should exist?

Each page should have `preview.png` for parent whole-deck review and `split_assets_contact.png` for origin/preview comparison. The job folder should have `deck_preview_contact.png` before final assembly. Do not create `diff.png` or `diff.json` as required outputs.

## Acceptance Criteria

- Final output is `{origin_name}_edited.pptx`.
- Output slide count matches expected source page/slide count.
- PPT/PPTX speaker notes, when present, are preserved on matching slides with identical text.
- Every page manifest has `completion_status: "ready_for_assembly"`.
- No page marked `blocked`, missing `completion_status`, missing validation, or failing validation is assembled.
- Every readable source string is listed in `text_inventory` and appears as visible editable PPT text unless explicitly documented otherwise.
- Every required non-text visual object is independently represented as a native shape or generated asset with provenance.
- `preview.png` exists for each page.
- `split_assets_contact.png` exists for each page and shows `origin` and `preview` side by side.
- `deck_preview_contact.png` exists and has been inspected before final deck assembly.
- Root `validation.json` passes.
- Final response names the PPTX path, validation report path, and any known fidelity limits.

For detailed prompt patterns, manifest schema, and validation criteria, read `references/workflow.md`.
