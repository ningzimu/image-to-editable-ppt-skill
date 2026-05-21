---
name: image-to-editable-ppt
description: Use when the user gives one or more slide images, an image-based PPT/PPTX, or a PDF and asks for an editable PowerPoint/PPTX, slide reconstruction, image-only presentation conversion, per-page editable rebuilds, or preservation of PPT speaker notes.
---
# Image to Editable PPT

## Overview

Convert image, PDF, and image-based PPT/PPTX inputs into editable PowerPoint output. The workflow is input normalization -> per-page reconstruction -> deck assembly -> validation and repair. A single image produces a one-page PPTX. Multiple images produce a multi-page PPTX with one page per image, but image order is not guaranteed. A PDF produces one output page per PDF page in the same order. A PPT/PPTX produces the same number of output pages in the same order, and any source speaker notes must be copied to the matching output page unchanged.

This skill owns input splitting, job folder setup, subagent page assignment, editable text reconstruction, asset provenance, PPTX assembly, validation, visual QA, note preservation, and targeted repair. It delegates visual generation and visual decomposition to `$imagegen`.

## Priority And Non-Negotiable Dispatch

When this skill is invoked, its workflow and dispatch rules are the highest-priority task-specific instructions for the conversion job. For multi-image, PDF, and PPT/PPTX inputs, using subagents is mandatory, not optional: create exactly one page subagent per output page before page reconstruction begins.

Do not silently replace the required subagent workflow with parent-agent sequential processing. If subagents are unavailable, blocked by the current platform, or disallowed by higher-priority system rules, stop before rebuilding pages and report that subagent dispatch is the blocker. Continue without subagents only if the user explicitly approves a single-agent run after that blocker is stated.

Subagents must return a page with `completion_status: "ready_for_assembly"` or `completion_status: "blocked"` in `manifest.json`. The parent must assemble only pages marked `ready_for_assembly`. A page marked `blocked`, missing this field, or failing `validate_pptx.py --manifest` is not an input to deck assembly.

## Input Modes And Output Contract

- One image (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tif`, `.tiff`) -> one-page `.pptx`.
- Multiple images -> multi-page `.pptx`; every image becomes a page, but do not promise relative order.
- PDF -> multi-page `.pptx`; PDF page N must become output slide N.
- PPT/PPTX -> multi-page `.pptx`; source slide N must become output slide N.
- PPT/PPTX speaker notes -> output speaker notes on the matching page, unchanged. Do not OCR, summarize, translate, rewrite, or send notes to subagents.

## Runtime And Dependencies

Use this skill's local runtime for dependency-based scripts. Let `{skill_root}` mean the directory containing this `SKILL.md`.

```bash
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py bootstrap
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py doctor
```

The runtime creates `{skill_root}/.venv` and installs `{skill_root}/requirements.txt`. The `.venv` and `.env` files are local state and must not be committed. PDF rendering uses PyMuPDF. PPT/PPTX rendering requires LibreOffice/`soffice` as a system dependency; if it is missing, stop and report the blocker.

## Job Folder Contract

Every run must create a fresh job folder and keep all intermediate and final files inside it:

```text
output/image-to-editable-ppt/<job-id>/
├── input/
├── deck_manifest.json
├── rebuilt.pptx
├── validation.json
├── notes_manifest.json
└── pages/
    └── page_001/
        ├── source.png
        ├── run_request.json
        ├── imagegen-jobs.json
        ├── assets/
        ├── split_assets_contact.png
        ├── manifest.json
        ├── preview.png
        ├── diff.png
        ├── diff.json
        ├── validation.json
        └── qa_notes.md
```

Use `scripts/prepare_inputs.py` to normalize inputs and create `deck_manifest.json`:

```bash
python3 {skill_root}/scripts/prepare_inputs.py input1.png input2.png
python3 {skill_root}/scripts/prepare_inputs.py deck.pdf
python3 {skill_root}/scripts/prepare_inputs.py image_based_deck.pptx
```

## Generation Delegation

Use `$imagegen` as the default source for clean visual layers, then use deterministic local scripts only for alpha cleanup, splitting, placement, packaging, and validation. For dense infographic, technical-route, dashboard, architecture, or diagram-heavy slides, prefer a layered imagegen workflow instead of one full-slide background: generate a clean layout/base layer with all readable text removed and standalone reusable icons removed; generate one or more sparse chroma-key asset sheets for icons, arrows, checks, magnifiers, badges, pictograms, chart glyphs, and reusable diagram parts; remove the key locally; split the transparent sheets; then rebuild the slide with the clean base image, independent PNG assets, editable PPT text, and simple editable geometry.

Asset sheets must be sparse. Require at least 260 px of pure chroma-key space between visible assets for dense slides, at least 220 px for simpler slides, allow assets to shrink to preserve spacing, and require each listed icon/object to be internally complete as one visual object. Do not accept crowded sheets as final inputs to splitting; regenerate the sheet before trying to rescue severe crowding with post-processing.

For complex infographic pages, do not rely on OCR as the truth source. Build or verify a `text_inventory` from visual inspection, user-provided text, or manual correction, then recreate readable text as native PowerPoint text. `$imagegen` is for clean non-text visual assets, not for exact text rendering.

Before generating an asset sheet or repair asset, load and follow the installed image generation skill:

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

Do not call the Image API directly for the normal path. Let `$imagegen` choose its built-in-first path. If `$imagegen` cannot produce the required clean visual layer or required assets, block the page instead of inventing a substitute.

Use this skill's scripts only for deterministic work: removing/splitting `$imagegen` asset-sheet images, cropping `$imagegen` asset-sheet regions when generated components touch, mapping generated assets to source coordinates, building manifests, assembling PPTX files, producing local previews, contact sheets, and validating package structure, provenance, and editable text. Do not crop non-text visual assets directly from the original source image as the default decomposition path. Source-image crops are allowed only as diagnostic/alignment references. Do not locally draw, synthesize, trace, or replace complex visual assets with Python/Pillow, SVG, canvas, HTML/CSS, source crops, or hand-made placeholders as a substitute for `$imagegen`.

Photo-background exception: when the page is primarily one complex photo or texture background with only overlay text, do not decompose the photo into objects and do not use local blur/darken/inpaint as the final cleanup. Use `$imagegen` image editing to produce a clean no-text background image, then rebuild all readable text as visible native PPT text boxes. Treat the edited no-text background as one background asset with provenance; it is acceptable because the editable layer is the text overlay, not individual trees/buildings/waves in the photo.

Near-original fidelity does not loosen the editable reconstruction contract. If near-original visual fidelity requires a non-editable raster region, block and explain the tradeoff instead of silently rasterizing it. Never present full-slide raster, tiled full-page raster mosaics, hidden/tiny text overlays, or grid crops as object-level editable reconstruction.

Hard boundary: do not mark visual decomposition complete by inventing assets, cropping assets from the original source image, editing manifests to hide missing assets, or recording temporary placeholder art as final. If the task requires generated separation, repair, or redraw and `$imagegen` is unavailable, stop and explain the blocker instead of fabricating the visual layer.

Hard boundary: never use the full source slide image (`source.png`) as a full-slide background and then overlay editable text boxes as a normal editable reconstruction. That creates duplicate baked-in text underneath editable text. It is a failed page, not a documented limitation. The validator rejects this pattern.

Before skipping `$imagegen`, make an explicit page-level gate decision in `run_request.json`, `manifest.json`, or `qa_notes.md`:

```json
{
  "page_type": "dense_dashboard",
  "imagegen_required": true,
  "skip_imagegen_allowed": false,
  "imagegen_skip_reason": null
}
```

Skip `$imagegen` only after positively confirming that every non-text visual object is a plain editable primitive, such as straight lines, rectangles, round rectangles, circles, or structural chart bars. This is a reverse-proof gate: if any standalone icon, pictogram, badge, sticker, tape, paper texture, shadowed illustration, decorative mark, sketchy arrow/underline, hand-drawn mark, or other style-bearing reusable visual object is present, `$imagegen` is required even if the rest of the page is simple geometry. Dashboard, dense infographic, technical-route, and architecture pages default to `imagegen_required: true`; set `skip_imagegen_allowed: true` only when the QA notes list concrete evidence that no style-bearing visual objects exist. Do not use local drawing code or native PowerPoint preset shapes to approximate required `$imagegen` assets.

## Visible Progress Plan

For every normal run, keep a visible checklist with one active step at a time:

1. Preparing inputs and job folder.
2. Assigning page reconstruction.
3. Rebuilding editable pages.
4. Assembling the PPTX deck.
5. Checking and repairing.

What each step means:

- `Preparing inputs and job folder.` Copy inputs to `input/`, normalize each page to `pages/page_NNN/source.png`, create `deck_manifest.json`, and extract PPT/PPTX notes into `notes_manifest.json`.
- `Assigning page reconstruction.` For multi-image, PDF, and PPT/PPTX inputs, dispatch one subagent per page. This is mandatory. If subagent dispatch cannot happen, stop and report the blocker instead of rebuilding pages in the parent agent. Single-image jobs may stay in the parent agent.
- `Rebuilding editable pages.` Each page job creates its own manifest, assets, preview, diff, validation, and QA notes inside its `pages/page_NNN/` folder.
- `Assembling the PPTX deck.` The parent agent reads `deck_manifest.json`, ordered page manifests, and notes manifest; then writes `rebuilt.pptx`.
- `Checking and repairing.` Run page and deck validation, inspect previews or renderer screenshots, compare against sources, treat visibly poor placeholder-like icons or style-bearing assets as blockers, repair the smallest failing scope, and report final paths.

Only mark a step complete when the real file, image, manifest, validation report, or decision exists. For a repair-only request, start from the first relevant step instead of restarting the whole workflow.

## Workflow

1. Normalize inputs with `prepare_inputs.py`. Stop if PPT/PPTX input needs LibreOffice and `soffice` is unavailable.
2. For multi-image, PDF, and PPT/PPTX jobs, dispatch one Codex subagent per page. The parent owns `deck_manifest.json`, `notes_manifest.json`, final assembly, and final validation. Do not proceed to page reconstruction in the parent agent when subagent dispatch is unavailable; stop and ask for explicit single-agent approval.
3. For each page, make a reconstruction plan before generating anything: classify the page type, list every readable text string, list required non-text visual objects, decide which objects are native PPT geometry and which require `$imagegen`, and record `imagegen_required` / `skip_imagegen_allowed`.
4. Preserve source geometry semantics. Rectangular panels, tables, chart frames, and report containers stay `rect`; use `roundRect` only when the source object is visibly rounded, such as pills, badges, buttons, and rounded callouts. Do not add rounded corners, shadows, or decorative styles just because they look modern.
5. Choose the visual strategy for that page. For complex photo-background pages with only overlay text, use `$imagegen` image editing to create a no-text background. For hand-drawn/manual pages, use `$imagegen` to create a no-readable-text visual layer that preserves hand-drawn frames, arrows, icons, tape, and texture, then rebuild text natively. For dashboard/report pages, rebuild structural cards, tables, charts, axes, gridlines, and simple status badges as native PPT shapes/text, while standalone icons and style-bearing marks come from `$imagegen` asset sheets. Do not satisfy this step by cropping visual objects from `source.png`, or by approximating style-bearing icons/pictograms with local drawing code or PowerPoint preset shapes.
6. Generate and process `$imagegen` assets. Choose a chroma-key color that is absent from the assets (`#00ff00` is bad for green icons; use `#ff00ff` instead). Remove the key locally, split assets, and inspect `split_assets_contact.png`. Do not enable despill by default; use it only when the contact sheet proves it does not damage icon colors.
7. Record provenance for the clean base and for each `$imagegen` asset, then create `pages/page_NNN/manifest.json` using source-image pixel coordinates: set `source.width_px` and `source.height_px`, place objects with `box_px: [x, y, width, height]`, and use `points_px: [x1, y1, x2, y2]` for straight line shapes. Keep explicit `z_index` layers: base/background first, native geometry next, generated icons/assets next, editable text last. Include complete `text_inventory`, required visual object coverage, and `completion_status`.
8. Size editable text boxes generously. Use source text geometry as the alignment reference, but make the `box_px` wider/taller than the visible glyphs so PowerPoint, WPS, and the manifest preview can use slightly different font metrics without clipping. For text inside buttons, badges, and callouts, set `valign: "middle"` and give the box enough horizontal slack before reducing font size.
9. Build, validate, and visually compare each page. Run `build_pptx_from_manifest.py` with `--preview`, run `validate_pptx.py`, and produce a source/preview/diff comparison. Structural validation is not enough; inspect the preview. Repair only the smallest failing scope: a coordinate, text box, shape type, split asset, or targeted `$imagegen` repair.
10. Assemble the final PPTX from `deck_manifest.json` with `build_pptx_from_manifest.py --deck-manifest deck_manifest.json --out rebuilt.pptx` only after every page manifest has `completion_status: "ready_for_assembly"`, page validation passes, and page preview QA is acceptable. For PPT/PPTX input, copy notes from `notes_manifest.json` to the matching slide.
11. Run deck validation with `validate_pptx.py rebuilt.pptx --deck-manifest deck_manifest.json --report validation.json`, then inspect the assembled output or previews before reporting completion.
12. If page or deck validation shows missing words, missing assets, clipped text, cramped text, accidental wrapping, broken relationships, notes mismatch, missing page outputs, obvious layout drift, wrong shape semantics, or preview-visible poor icons/assets, repair only the smallest failing scope and rebuild. Do not report completion while the preview contains crude placeholder shapes, wrong icon metaphors, broken pictograms, illegible generated marks, or visually downgraded assets that should be regenerated through `$imagegen`.

For detailed prompt patterns, manifest schema, and validation criteria, read `references/workflow.md`.

## Editing Policy

- Prefer visible editable text boxes for all readable text, including labels inside diagrams whenever practical. Hidden, transparent, 1 pt, off-canvas, or metadata-only text boxes do not satisfy text editability.
- Keep editable text boxes roomy, not tight to glyph bounds. Preserve source alignment and apparent hierarchy, but first enlarge the box or add explicit line breaks before shrinking font size. For container text inside pills, buttons, badges, and callouts, prefer `valign: "middle"` and a taller box over manual y-coordinate nudging.
- Preserve source shape semantics. Do not convert rectangular panels, tables, cards, or chart frames into rounded rectangles unless the source visibly has rounded corners.
- Use raster images only for non-text visual assets: clean layout bases, illustrations, icons, handwritten decorations, texture, tape, shadows, folders, cards, backgrounds, chart/diagram glyphs, and decorative marks.
- For photo-background slides, use one edited no-text background image plus visible editable text boxes. Do not leave baked-in text in the background, and do not accept local blur/darken patches with visible ghosting as final.
- Keep source images, generated asset sheets, split assets, `split_assets_contact.png`, manifest, PPTX, preview, `original_vs_rebuilt_diff.png`, `diff.json`, and validation report in a single output folder.

## Subagent Use

For a single image, subagents are optional. The parent agent may do the whole one-page job.

For multiple images, PDF, and PPT/PPTX inputs, use one subagent per page. This is a hard requirement of this skill. The parent agent assigns each subagent exactly one `pages/page_NNN/` folder and source image. A subagent may create or edit only files inside its assigned page folder. It must return the page manifest path, preview/diff paths, validation path, QA notes, and any known limits.

If the current runtime cannot spawn subagents, do not mark `Assigning page reconstruction.` complete and do not continue as a parent-only rebuild. Report the blocker clearly and wait for the user to either enable subagents or explicitly authorize a single-agent run.

Subagents must not edit `deck_manifest.json`, `notes_manifest.json`, other page folders, source input files, or the final `rebuilt.pptx`. Speaker notes are handled only by the parent agent and must not be sent to subagents for rewriting or analysis.

Subagent prompt must include this exact gate: "If you cannot produce the required clean no-text visual layer and required `$imagegen` assets, set `completion_status` to `blocked`, write the blocker in `qa_notes.md`, and do not create a ready page manifest." Do not weaken this gate in the parent prompt.

## Repair Workflow

Repair the smallest failing scope:

- Missing or incorrect text: update `text_inventory`, add or fix editable text boxes, and rerun validation.
- Clipped, cramped, or accidentally wrapped text: first increase box width/height and use explicit line breaks or `valign: "middle"` where appropriate; reduce font size only after the box has enough slack.
- Low-fidelity asset: rerun `$imagegen` for that asset or a narrower asset sheet, then resplit or recrop only the affected asset.
- Preview-visible placeholder icon or crude native-shape approximation: classify it as a missing `$imagegen` asset, generate a focused sparse asset sheet for only the affected icon(s), replace the approximation, rerun preview/diff/validation, and record the repair in `qa_notes.md`.
- Broken image relationship: fix the asset path in the manifest or regenerate the missing asset file.
- Incorrect background: fix `slide.background` or use an explicit full-slide shape when the background needs layered texture.
- Text overlaps baked-in source text: do not move the text boxes around as a repair. Replace the source background with a clean no-text `$imagegen` background.
- Layout drift: adjust manifest coordinates and regenerate preview/diff before touching the visual assets.

Do not regenerate the whole slide when a text box, one asset, or one coordinate change is enough.

## Commands

Prepare inputs and create a job folder:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/prepare_inputs.py" slide1.png slide2.png
python3 "$SKILL_DIR/scripts/prepare_inputs.py" deck.pdf
python3 "$SKILL_DIR/scripts/prepare_inputs.py" image_based_deck.pptx
```

Assemble a multi-page deck after page manifests are ready:

```bash
python3 "$SKILL_DIR/scripts/build_pptx_from_manifest.py" \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --out output/image-to-editable-ppt/<job-id>/rebuilt.pptx
```

Validate a multi-page deck:

```bash
python3 "$SKILL_DIR/scripts/validate_pptx.py" \
  output/image-to-editable-ppt/<job-id>/rebuilt.pptx \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --report output/image-to-editable-ppt/<job-id>/validation.json
```

Crop one `$imagegen` asset-sheet region into a reusable image and append provenance. This helper is for generated asset sheets only; do not use it to crop non-text assets from `source.png`:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/crop_image_asset.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out assets/icon_trigger.png \
  --box 120,80,260,220 \
  --manifest manifest.json \
  --source-type imagegen \
  --qa-note "Icon cropped from the selected imagegen asset sheet and visually inspected."
```

Split a transparent asset sheet into component PNG assets after chroma-key removal:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/split_alpha_components.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --names icon_doc.png,icon_book.png,icon_bulb.png,icon_chart.png,icon_target.png \
  --sort x \
  --square
```

The splitter defaults are tuned for generated sparse asset sheets: `--connectivity 8`, `--close-radius 3`, and `--merge-gap 18`. If assets are intentionally close together, lower `--merge-gap` or set it to `0`; if broken strokes remain split, retry once with `--merge-gap 24` before manual crop boxes.

Build from a manifest:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/build_pptx_from_manifest.py" manifest.json --out output.pptx
```

Validate the result:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/validate_pptx.py" output.pptx --manifest manifest.json --required-text "标题" --report validation.json
```

Generate a local preview from the manifest when real PowerPoint/WPS rendering is unavailable:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/build_pptx_from_manifest.py" manifest.json --out output.pptx --preview preview.png
```

Render a simple image diff between the source and preview or renderer screenshot:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/render_diff.py" \
  --expected source.png \
  --actual preview.png \
  --out diff.png \
  --comparison original_vs_rebuilt_diff.png \
  --report diff.json
```

Run the repeatable page experiment loop after a page manifest exists. This can copy a generated asset sheet, remove chroma key, split assets, build the PPTX, validate, and write source/preview QA artifacts:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/run_page_experiment.py" pages/page_001 \
  --preview-scale 144 \
  --qa-pair original_vs_rebuilt.png \
  --pixel-diff
```

When processing a new asset sheet, pass the selected generated image explicitly. Use `--despill` only when the contact sheet proves it does not damage colors:

```bash
python3 "$SKILL_DIR/scripts/run_page_experiment.py" pages/page_001 \
  --asset-sheet-source /path/to/generated_sheet.png \
  --chroma imagegen_icon_sheet_magenta.png \
  --asset-names icon_a.png,icon_b.png,icon_c.png \
  --split-sort x \
  --square-assets \
  --force-chroma
```

## Rules

- Use `$imagegen` clean visual layers as the primary and default decomposition path for non-text visual content. For dense infographic pages, this means a clean layout/base layer plus sparse asset sheets, not one all-purpose generated background.
- Treat the `imagegen_required` gate as mandatory page metadata. For dashboard, dense infographic, technical-route, and architecture pages, default it to `true`; if the final manifest has `images: []`, the page must document `skip_imagegen_allowed: true` plus concrete evidence that all non-text visuals are only plain primitives.
- Prompt asset sheets as sparse single-sheet layouts by default: at least 260 px of pure chroma-key spacing for dense pages and at least 220 px for simpler pages, spacing more important than asset size, no touching or cross-asset shadows, and each icon internally complete as one object.
- Choose chroma-key colors by asset content. Avoid green keys for green assets and avoid magenta keys for magenta/purple assets. Do not enable despill by default; inspect the contact sheet before using it.
- Prefer `$imagegen` when deciding whether a visual element is a shape or an asset. Keep only simple structural geometry editable; split style-bearing or reusable visual elements into PNG assets.
- Do not use the "simple primitives" exception for slides with hand-drawn small icons, tape, textured notes, decorative strokes, shadows, or pictograms. Recreate readable text as editable PPT text, but split those non-text visuals with `$imagegen`.
- Do not crop non-text visual assets directly from the original source image in editable-first mode. Full-page raster mosaics are not object-level editable PPT.
- Do not use regular grid crops, tile mosaics, or large source regions that contain multiple unrelated objects as a substitute for element extraction. A crop that includes a surrounding card, neighboring text, or several icons is a page fragment, not an extracted asset.
- Keep source images attached/visible for `$imagegen` whenever the chosen path supports references.
- Do not rely on `$imagegen` for exact editable text; recreate readable text as editable PPT text boxes.
- Do not satisfy editable text coverage with hidden/tiny overlay text. The visible text in the reconstructed slide must come from native PPT text boxes when the text is claimed editable.
- Do not rely on generated images for exact slide geometry; write manifest placement in source-image pixel coordinates with `source.width_px`, `source.height_px`, `box_px`, and `points_px`, then let deterministic scripts convert to the slide size. Use the source image only as an alignment reference unless the user explicitly accepts visual-99 source rasterization.
- Do not use local drawing code or native PowerPoint preset shapes to fake complex visual assets that should have come from `$imagegen`.
- Do not use local blur, dark rectangles, clone-like patches, or threshold masks as the final way to remove text from a complex photo background. They are acceptable only as diagnostic masks or prompt aids before `$imagegen` background repair.
- Do not use macOS Quick Look thumbnails as the visual acceptance renderer; they can distort PPT text layout. Prefer this skill's manifest preview, PowerPoint/WPS screenshots, or an explicitly trusted renderer.
- Do not accept a PPTX solely because deterministic validation passes; visually inspect the generated preview or a trusted renderer screenshot.
- Do not accept a PPTX whose native geometry changes the source semantics, such as turning rectangular tables/cards into rounded rectangles or replacing source line styles with unrelated decorative choices.
- Treat the visual preview as an active repair trigger, not a passive artifact. If icons, pictograms, badges, or decorative marks look crude, mismatched, placeholder-like, malformed, or obviously worse than the source, stop and repair those assets with `$imagegen` before final reporting.
- Do not skip the asset contact sheet when multiple assets are extracted; it catches clipped icons, wrong component order, and accidental fragments before PPT assembly.
- Treat contact-sheet crowding, cross-asset merges, clipped edges, and repeated fragments as blockers. Regenerate the asset sheet when spacing is the cause; use deterministic crop boxes only when one or two assets still need repair.
- Treat unapproved full-slide rasterization or tiled full-page source-raster mosaics as blockers for editable reconstruction, even when visual diff scores are excellent.
- Treat missing independent required visual objects as blockers. If the source has hand-drawn icons, arrows, notes, tapes, charts, badges, checkboxes, underlines, pictograms, KPI icons, management-insight icons, decorative illustrations, or other style-bearing visual objects, the final manifest must contain corresponding named `$imagegen` assets. Clean base images, page tiles, and native-shape approximations do not count for independently movable object coverage.
- Treat missing `text_inventory` entries, missing relationship targets, broken media files, and unreadable Chinese preview text as blockers.
- Treat visual drift, missing icons, missing labels, rasterized text that was meant to be editable, and clipped content as repair items.

## Acceptance Criteria

- PPTX opens as a valid zip package.
- Output is always `.pptx`.
- Single image output has one slide.
- Multiple image output has one slide per image, with no promise about relative source-image order.
- PDF output slide N corresponds to PDF page N.
- PPT/PPTX output slide N corresponds to source slide N.
- PPT/PPTX speaker notes, when present, are preserved on the matching output slide with identical text.
- Every readable source string is listed in `text_inventory`, and every item is present as editable text unless intentionally documented as rasterized or omitted.
- Every readable source string is visible as editable native text.
- Every page manifest records the source image size in `source.width_px` and `source.height_px`, and positioned text, image, and shape objects use `box_px` or `points_px`.
- Every required non-text visual object is independently represented. Plain primitives may be native shapes; standalone style-bearing objects must be named `$imagegen` image assets.
- Every page records `imagegen_required`, `skip_imagegen_allowed`, and any `imagegen_skip_reason` or skip evidence. Dashboard, dense infographic, technical-route, and architecture pages with `images: []` pass only when the skip evidence proves there are no standalone icons, pictograms, badges, stickers, decorative marks, or other style-bearing reusable objects.
- If `imagegen_required` is true, every standalone style-bearing visual object has a named `$imagegen` asset with provenance.
- Validation report includes slide count, image count, editable shape count, required-text results, missing package parts, missing relationship targets, media hash mismatches, and warnings.
- Every final raster asset has a validator-checked provenance entry with a valid `source_type`, existing `source`, and `qa_note`; user-approved rasterization also needs `approval_note` and source region coordinates.
- A local manifest preview is produced. A real PowerPoint/WPS renderer screenshot is also produced when a renderer is available.
- Preview-visible crude placeholder icons, wrong icon metaphors, malformed pictograms, or native-shape approximations of style-bearing assets are blockers and must be repaired with targeted `$imagegen` asset generation before completion.
- A split-assets contact sheet is produced when visual assets are decomposed, clean base images are inspected for leftover readable text or duplicated standalone icons, and a human-readable source/preview/diff comparison is produced for visual QA.
- For photo-background slides, a clean no-text background image is produced and inspected; old text ghosting, blur blocks, dark boxes, or generated replacement text are blockers.
- Any known visual-fidelity limits are documented rather than hidden.
- Final response names the PPTX path, validation report path, and any known fidelity limits.
