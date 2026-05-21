# Image to Editable PPT Workflow

## Table of Contents

- [Use Cases](#use-cases)
- [Input Normalization](#input-normalization)
- [Script Entrypoints](#script-entrypoints)
- [Recommended Output Folder](#recommended-output-folder)
- [Run Manifests And Provenance](#run-manifests-and-provenance)
- [Multi-Page Delegation And Assembly](#multi-page-delegation-and-assembly)
- [Page Reconstruction Loop](#page-reconstruction-loop)
- [Whole-Deck Preview Gate](#whole-deck-preview-gate)
- [Photo Background With Editable Text](#photo-background-with-editable-text)
- [Hand-Drawn Manual Pages](#hand-drawn-manual-pages)
- [Generated Asset-Sheet Decomposition](#generated-asset-sheet-decomposition)
- [Manifest Schema](#manifest-schema)
- [Validation Criteria](#validation-criteria)
- [Repair Workflow](#repair-workflow)
- [Common Repairs](#common-repairs)

## Use Cases

- "把这张 PPT 截图转成可编辑 PPT"
- "把这些图片转成一个多页可编辑 PPT"
- "把这个 PDF 转成页码对应的可编辑 PPT"
- "把这个图片版 PPT/PPTX 转成可编辑 PPT，并保留页面备注"
- "复刻这页图，文字要能改"
- "把视频关键帧/海报图片做成可编辑幻灯片"
- "拆元素，再用图片素材和可编辑文字重建"

## Input Normalization

Normalize every task before page reconstruction:

- One image becomes one page source image.
- Multiple images become one page source image per input image; do not promise their relative order.
- PDF pages are rendered to page source images; page N must map to output slide N.
- Image-based `.pptx` pages are extracted when each slide contains exactly one full-slide embedded picture; source slide N must map to output slide N.
- `.ppt` files are passed through the available local normalization path. If normalization fails, ask the user for a PDF export or per-slide images instead of silently installing additional system renderers.
- PPT/PPTX speaker notes are extracted into `notes_manifest.json` and copied by the parent agent during final deck assembly. Do not rewrite notes.

Use:

```bash
python3 {skill_root}/scripts/prepare_inputs.py input.png
python3 {skill_root}/scripts/prepare_inputs.py one.png two.png three.png
python3 {skill_root}/scripts/prepare_inputs.py deck.pdf
python3 {skill_root}/scripts/prepare_inputs.py image_based_deck.pptx
python3 {skill_root}/scripts/prepare_inputs.py legacy_deck.ppt
```

## Script Entrypoints

Every script in `skills/image-to-editable-ppt/scripts/` has a workflow role. Do not keep unused one-off helpers in this folder.

### `image_to_editable_ppt_runtime.py`

Bootstrap and check the local skill runtime. Use before dependency-based scripts when the environment is new or uncertain:

```bash
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py bootstrap
python3 {skill_root}/scripts/image_to_editable_ppt_runtime.py doctor
```

### `prepare_inputs.py`

Create the job folder, copy inputs, normalize pages into `pages/page_NNN/source.png`, extract speaker notes when present, and write `deck_manifest.json` plus `notes_manifest.json`:

```bash
python3 {skill_root}/scripts/prepare_inputs.py input.png
python3 {skill_root}/scripts/prepare_inputs.py deck.pdf
python3 {skill_root}/scripts/prepare_inputs.py image_based_deck.pptx
```

### `build_pptx_from_manifest.py`

Build either one page PPTX from a page manifest or the final deck from `deck_manifest.json`. The deck path enforces page readiness, page previews, page contact sheets, and `deck_preview_contact.png` before assembly:

```bash
python3 {skill_root}/scripts/build_pptx_from_manifest.py \
  pages/page_001/manifest.json \
  --out pages/page_001/page.pptx \
  --preview pages/page_001/preview.png

python3 {skill_root}/scripts/build_pptx_from_manifest.py \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

### `validate_pptx.py`

Validate a page PPTX against `manifest.json`, or validate the final deck against `deck_manifest.json`. Deck validation also checks page readiness artifacts and speaker-note hashes:

```bash
python3 {skill_root}/scripts/validate_pptx.py \
  pages/page_001/page.pptx \
  --manifest pages/page_001/manifest.json \
  --report pages/page_001/validation.json

python3 {skill_root}/scripts/validate_pptx.py \
  output/image-to-editable-ppt/<job-id>/{origin_name}_edited.pptx \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --report output/image-to-editable-ppt/<job-id>/validation.json
```

### `run_page_experiment.py`

Run the repeatable page loop after `manifest.json` exists. It can copy a generated asset sheet, remove chroma key, split assets, build the page PPTX, validate it, write `preview.png`, and write `split_assets_contact.png`:

```bash
python3 {skill_root}/scripts/run_page_experiment.py pages/page_001 --preview-scale 144
```

### `make_deck_preview_contact.py`

Combine every page's `preview.png` into root `deck_preview_contact.png` for parent whole-deck review before final assembly:

```bash
python3 {skill_root}/scripts/make_deck_preview_contact.py \
  output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

### `split_alpha_components.py`

Split a transparent generated asset sheet into component PNG assets after chroma-key removal:

```bash
python3 {skill_root}/scripts/split_alpha_components.py \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --names icon_doc.png,icon_book.png,icon_chart.png \
  --sort x \
  --square
```

### `crop_image_asset.py`

Crop one region from a generated transparent asset sheet and append `asset_provenance` to the page manifest. Use this only for generated asset sheets, not for cropping non-text assets from `source.png`:

```bash
python3 {skill_root}/scripts/crop_image_asset.py \
  --input imagegen_asset_sheet_alpha.png \
  --out assets/icon_trigger.png \
  --box 120,80,260,220 \
  --manifest manifest.json \
  --source-type imagegen \
  --provenance-note "Icon cropped from the selected imagegen asset sheet and visually inspected."
```

## Recommended Output Folder

Use one fresh folder per job. All intermediate files and final outputs stay inside this folder:

```text
output/image-to-editable-ppt/<job-name>/      # Fresh per-run job folder; keep all intermediate and final files here.
├── input/                                    # Copied original input files; never mutate user originals in place.
├── deck_manifest.json                       # Job-level manifest: input type, page order, page paths, notes manifest, final output name.
├── deck_preview_contact.png                 # Parent QA image combining all page preview.png files before final PPTX assembly.
├── {origin_name}_edited.pptx                # Final editable PowerPoint deck; origin_name is the first input file stem.
├── validation.json                          # Final deck validation report.
├── notes_manifest.json                      # Extracted PPT/PPTX speaker notes, copied unchanged into matching output slides.
└── pages/                                   # Per-page work area; one page_NNN folder per output slide.
    ├── page_001/                            # Page-scoped folder owned by exactly one page subagent.
    │   ├── source.png                       # Normalized source image for this page.
    │   ├── run_request.json                 # Optional parent-written task boundary: source path, write scope, requested outputs, user constraints.
    │   ├── imagegen-jobs.json               # Audit log for built-in image_gen clean-base, asset-sheet, or repair generations.
    │   ├── asset_manifest.json              # Optional expanded asset audit; manifest.json is the validator source of truth.
    │   ├── clean_layout_base.png            # Optional generated no-text base layer for complex pages.
    │   ├── imagegen_asset_sheet_chroma.png  # Optional generated asset sheet on a solid chroma-key background.
    │   ├── imagegen_asset_sheet_alpha.png   # Optional transparent asset sheet after chroma-key removal.
    │   ├── assets/                          # Final per-object PNG assets referenced by manifest.json.
    │   ├── preview.png                      # Rendered reconstructed page preview for parent whole-deck review.
    │   ├── split_assets_contact.png         # Human QA image with origin and preview side by side.
    │   ├── split_assets.json                # Optional splitter output mapping asset filenames to crop boxes/components.
    │   ├── manifest.json                    # Page reconstruction manifest consumed by build_pptx_from_manifest.py.
    │   └── validation.json                  # Page-level validation report from validate_pptx.py --manifest.
    └── page_002/                            # Next page folder with the same contract.
        └── ...                              # Additional page-scoped files following page_001 conventions.
```

## Run Manifests And Provenance

Use lightweight JSON files to keep the run auditable:

- `run_request.json`: optional parent-written task boundary file with the source image path, output folder, slide size, allowed write scope, requested outputs, and user constraints. It must not prescribe `page_type`, `imagegen_required`, `skip_imagegen_allowed`, or `imagegen_skip_reason`; the page subagent decides those after inspecting the source image and records them in `manifest.json`.
- `imagegen-jobs.json`: recommended audit file for each built-in `image_gen` clean base, asset-sheet, or repair job, prompt file or prompt text, source images attached, selected generated output path, and status. The filename stays `imagegen-jobs.json` for compatibility.
- `asset_manifest.json`: optional expanded asset audit. The validator-enforced provenance lives in `manifest.json` under `asset_provenance`.
- `pages/page_NNN/manifest.json`: the page construction manifest consumed by `build_pptx_from_manifest.py`.
- `deck_manifest.json`: the job-level manifest with input type, page count, page order, per-page manifest paths, notes manifest path, and `{origin_name}_edited.pptx` output name.
- `notes_manifest.json`: source PPT/PPTX notes text and hashes by page. Notes are copied unchanged into the final deck.
- `pages/page_NNN/preview.png`: rendered reconstructed page preview for parent whole-deck visual review.
- `pages/page_NNN/split_assets_contact.png`: page-level origin/preview comparison.
- `deck_preview_contact.png`: parent-created whole-deck preview sheet assembled from every page `preview.png`.
- `pages/page_NNN/validation.json`: page validation output.
- root `validation.json`: deck validation output.

Do not record a visual asset as final unless the underlying source exists and has been visually inspected. For editable-first visual decomposition, the source should be a built-in `image_gen` clean base or generated asset sheet, not a crop from the original source slide. Every `images[*].path` in `manifest.json` must have an `asset_provenance` entry with the same `path`, valid `source_type`, existing `source`, and manifest-recorded provenance note.

Compatibility names such as `imagegen-jobs.json`, `imagegen_required`, and `source_type: "imagegen"` refer to generated visual assets from the built-in `image_gen` tool. They do not require a separate image-generation skill to be loaded by a subagent.

Every page manifest must include `completion_status`. Use `ready_for_assembly` only when the page passes validation and is acceptable for the final deck. Do not mark a page `blocked` at the first failed attempt. The page subagent should first try targeted self-repair inside its own page folder: regenerate the bad background region or asset sheet, resplit assets, adjust coordinates, enlarge text boxes, fix manifest paths, and rerun validation. Use `blocked` only when a hard blocker remains within that write scope. The `blocker_reason` must state what was attempted, what still fails, and what guidance or input is needed next. A blocked page is an audit artifact, not a deck input.

## Multi-Page Delegation And Assembly

For multi-image, PDF, and PPT/PPTX inputs, the parent agent creates one page job per source page and dispatches one Codex subagent per page when subagents are available. Each subagent owns only its assigned `pages/page_NNN/` directory. The parent may provide source path, allowed write scope, requested outputs, and user constraints, but it must not pre-classify the page or decide whether `image_gen` is required. The subagent must return the page manifest, assets, `preview.png`, `split_assets_contact.png`, and validation report.

The parent agent alone owns:

- `deck_manifest.json`
- `notes_manifest.json`
- final `{origin_name}_edited.pptx`
- root `deck_preview_contact.png`
- root `validation.json`
- page ordering and notes preservation
- final quality check and delivery

Before assembling the final deck, create and inspect the whole-deck preview sheet:

```bash
python3 {skill_root}/scripts/make_deck_preview_contact.py \
  output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

Assemble the final deck only after every page is ready, every page has acceptable `preview.png`, and `deck_preview_contact.png` has no known page-quality problems:

```bash
python3 {skill_root}/scripts/build_pptx_from_manifest.py \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

Validate the deck:

```bash
python3 {skill_root}/scripts/validate_pptx.py \
  output/image-to-editable-ppt/<job-id>/{origin_name}_edited.pptx \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --report output/image-to-editable-ppt/<job-id>/validation.json
```

Deck validation also checks the page assembly contract. It rejects pages that use full-slide `source.png` or another user-provided full-slide raster as the background while also overlaying editable text boxes, because that creates baked-text overlap.

## Page Reconstruction Loop

Every page follows the same loop:

1. Classify the page: structural dashboard/report, photo background with overlay text, dense infographic, hand-drawn/manual page, or plain primitive layout.
2. Inventory readable text and non-text visual objects. Treat OCR as a draft only; inspect the source image and correct the inventory before rebuilding.
3. Decide layer ownership:
   - Native PPT text boxes for readable text.
   - Native PPT shapes for true primitives: straight lines, rectangles, circles, chart bars, table borders, simple status pills, and axis/grid lines.
   - Built-in `image_gen` assets for icons, pictograms, hand-drawn marks, tape, texture, shadows, illustrated decorations, and other style-bearing objects.
   - Built-in `image_gen` clean no-text backgrounds for photo or hand-drawn pages where the background itself is not practical native geometry.
4. Preserve source shape semantics. Rectangular panels, tables, chart frames, and report containers stay `rect`; use `roundRect` only for source objects that visibly have rounded corners.
5. Build the manifest in source-image pixel coordinates. Set `source.width_px` and `source.height_px`, then place text, images, and shapes with `box_px: [x, y, width, height]`; use `points_px: [x1, y1, x2, y2]` only for straight line shapes. Keep explicit `z_index`: background/base `0`, structural shapes `10-20`, generated assets `30`, editable text `40+`.
6. Give editable text boxes layout slack. Start from the source text position, then make the box wider/taller than the visible glyphs so renderer font metrics do not clip or wrap text unexpectedly. For text inside buttons, badges, pills, and callouts, use `valign: "middle"` and a taller box rather than tiny y-coordinate tweaks.
7. Run `build_pptx_from_manifest.py`, run `validate_pptx.py`, then inspect `preview.png` and `split_assets_contact.png`, which must show `origin` and `preview` side by side. Fix the smallest failing scope and repeat.

Use `scripts/run_page_experiment.py` when a page manifest already exists and you need a repeatable local loop for chroma cleanup, asset splitting, PPTX build, validation, and origin/preview QA:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/run_page_experiment.py" pages/page_001 \
  --preview-scale 144
```

If the page uses a new generated asset sheet:

```bash
python3 "$SKILL_DIR/scripts/run_page_experiment.py" pages/page_001 \
  --asset-sheet-source /path/to/generated_sheet.png \
  --chroma imagegen_icon_sheet_magenta.png \
  --asset-names icon_a.png,icon_b.png,icon_c.png \
  --split-sort x \
  --square-assets \
  --force-chroma
```

Do not use this script as a substitute for visual judgment. It automates the loop; the agent still must inspect `preview.png` and `split_assets_contact.png`.

## Whole-Deck Preview Gate

The parent agent must review the whole deck visually before final PPTX assembly. This prevents a technically valid set of pages from becoming a poor deck because one page is missing, duplicated, out of order, visually weak, or inconsistent with the rest.

After all expected pages report `completion_status: "ready_for_assembly"` and pass page validation, run:

```bash
python3 {skill_root}/scripts/make_deck_preview_contact.py \
  output/image-to-editable-ppt/<job-id>/deck_manifest.json
```

Inspect `deck_preview_contact.png` before assembly. Check page order, missing pages, repeated pages, obvious layout drift, crude generated assets, broken backgrounds, text overlap, clipped text, and inconsistent reconstruction quality across pages.

If any page looks poor, do not assemble the deck. Repair those pages first. For independent page problems, the parent may dispatch multiple page subagents in parallel, each scoped to its own `pages/page_NNN/` folder and given the concrete visual issue, validation output, current `preview.png`, and current `split_assets_contact.png`.

After repairs, rerun the affected page validation, regenerate that page's `preview.png` and `split_assets_contact.png`, then regenerate `deck_preview_contact.png`. Repeat until the whole-deck preview has no known page-quality problems.

## Photo Background With Editable Text

Use this branch when the slide is one complex photo/texture background with a small number of overlay text blocks. Examples include nature covers, city photos, product photos, abstract backgrounds, and full-bleed posters where the only editable content is typography.

Do this:

1. Save the original as `source.png`.
2. Use built-in `image_gen` image editing to remove all overlaid text and generate a no-text background.
3. Inspect the clean background before building the PPT. Reject backgrounds with old text ghosting, blur patches, dark boxes, generated replacement text, logos, or new unrelated objects.
4. Place the clean background as one full-slide image.
5. Recreate every readable string as visible native PPT text boxes.
6. Record provenance for the background as `source_type: "imagegen"` with a manifest provenance note explaining that it is an edited no-text background derived from the user-provided slide.

Do not use local PIL/OpenCV blur, threshold masks, dark overlays, or clone-like patches as the final background cleanup for complex photos. These methods often leave readable ghosts or obvious texture damage. They are acceptable only for locating text boxes, generating masks, or diagnosing where `image_gen` should repair.

Suggested `image_gen` edit prompt:

```text
Edit the provided slide image to remove all overlaid text while preserving the original photograph/background. Remove every visible title, subtitle, caption, logo-like text, and text shadow. Reconstruct the natural background texture in those areas with no visible ghosting, no blur patches, no dark boxes, no replacement text, no logos, and no new objects. Keep the same 16:9 composition, colors, contrast, lighting, and photographic style. Output only the clean no-text background image.
```

For this branch, strict object-level decomposition is not required for the photo content. The editable objects are the text boxes. The background is a single visual asset unless the user explicitly needs separate editable photo regions.

## Hand-Drawn Manual Pages

Use this branch when the source is a hand-drawn instruction page, sketched workflow, manual, whiteboard-like diagram, or note-style infographic.

Do this:

1. Use built-in `image_gen` image editing to create a clean no-readable-text visual layer that preserves the paper texture, hand-drawn frames, arrows, tapes, icons, checkbox outlines, warning marks, and other non-text visual structure.
2. Rebuild all readable text as native PPT text. The visual base must not contain readable baked-in text under editable text.
3. If icons or arrows should be independently movable, generate them as separate sparse asset sheets instead of leaving them only in the clean base.
4. Use a handwriting-like font only when it improves resemblance and remains readable; otherwise prefer stable native Chinese fonts over distorted text.
5. Reject clean bases with pseudo text, ghost text, lost sketch lines, or newly invented decorations.

This branch is not a permission to flatten the source page. The hand-drawn visual layer may be raster; the readable content must still be native editable text.

## Dense Infographic Layered Generation Workflow

Use this branch for technical route maps, dense infographics, dashboard-like slides, architecture diagrams, and pages with many panels, arrows, icons, chart glyphs, and labels. The goal is cleaner than direct source slicing and more editable than a single generated background.

Default layer model:

1. `clean_layout_base.png`: one built-in `image_gen` visual base with all readable text removed. For pages with icons that should be independently movable, also ask `image_gen` to remove those standalone icons from the base and leave clean blank spaces.
2. `imagegen_asset_sheet_*`: one or more sparse chroma-key sheets containing standalone icons, arrows, checks, magnifiers, badges, pictograms, reusable chart glyphs, and diagram parts.
3. `assets/*.png`: transparent split assets from the sheets.
4. Native PPT text boxes: every readable source string, manually verified. Do not use OCR output as the unquestioned truth source.
5. Optional simple native geometry: plain lines, rectangles, circles, or structural shapes that are genuinely better as editable PowerPoint shapes.

Suggested clean-base `image_gen` prompt:

```text
Using the provided slide image as visual reference, create a clean layout-only visual base with the same canvas ratio and composition. Preserve the title bar, backgrounds, panels, cards, photo areas, chart/diagram context, bands, borders, shadows, and spacing. Remove all readable text, letters, numbers, formulas, Chinese characters, English words, labels, captions, and checklist text. Also remove standalone reusable icons that will be overlaid separately: icons, arrows, check marks, magnifiers, badges, pictograms, and other label-like glyphs. Leave clean blank spaces where removed text or icons used to be, matching the surrounding background fills. No gibberish text, no pseudo text, no fake labels, no watermark.
```

Suggested icon-sheet `image_gen` prompt:

```text
Using the provided slide image as visual reference, create a sparse asset sheet containing only reusable non-text visual objects: icons, arrows, check marks, magnifiers, badges, pictograms, chart glyphs, and reusable diagram parts. Use a perfectly flat solid #00ff00 chroma-key background. Keep at least 260 px of pure #00ff00 space between every visible object. No touching objects, no cross-object shadows, generous padding, and each icon internally complete as one object. Shrink assets if needed to preserve spacing. No readable text, labels, letters, numbers, pseudo text, full cards, photos, panels, or large diagram backgrounds.
```

Inspect the clean base before assembly. Reject it if it still contains readable text, obvious text ghosts, duplicated standalone icons that should be separate, generated pseudo labels, or large layout drift. Inspect extracted assets before assembly. If objects are missing or merged, regenerate a smaller sheet with fewer assets rather than forcing a bad split.

Use the source image for alignment and object inventory, but not as the default visual asset source. Cropping source regions is only allowed in explicit visual-99 mode or for diagnostic comparisons.

Do not repair text overlap by moving editable text over the original raster. The original raster already contains the text. The only acceptable repair is a clean no-text visual base.

## Generated Asset-Sheet Decomposition

Use the built-in `image_gen` tool as the required default decomposition path for non-text visual assets and base visual elements. For dense pages, the reliable pattern is: whole slide reference -> clean no-text/no-standalone-icon layout base -> sparse chroma-key asset sheets -> local alpha cleanup -> deterministic split -> PPT images + editable text boxes. For simpler pages, the shorter asset-sheet-only pattern is acceptable. Do not replace this default path with direct crops from `source.png` or locally drawn approximations.

Near-original fidelity does not loosen the editable reconstruction contract. Source-region crop assets improve visual fidelity and position accuracy, but reduce object-level editability; if they would be required for the page to look correct, block and explain the tradeoff instead of marking the page ready for assembly.

Skip `image_gen` only when the source page is truly plain and the non-text layer contains only structural geometry that must remain editable, such as straight lines, rectangles, round rectangles, or circles. Prefer `image_gen` when in doubt, especially for hand-drawn icons, pictograms, tapes, shadows, textured notes, decorative strokes, sketchy arrows, underlines, badges, and other style-bearing or reusable visual parts.

Ask for an asset sheet:

```text
Using the provided slide image as visual reference, create ONE sparse asset sheet on a perfectly flat solid #ff00ff chroma-key background.
Keep every asset separated by at least 260 px of pure #ff00ff empty space for dense pages, or at least 220 px for simpler pages. Spacing is more important than asset size; shrink assets if needed.
No asset may touch, overlap, visually connect to, cast shadow onto, or have antialiased edges blending into another asset.
Each listed asset must be internally complete and connected as one visual object. Do not split one icon into disconnected parts.
Include the major standalone non-text visual assets: icons, arrows, underlines, tapes, textured paper pieces, decorations, chart glyphs, pictograms, badges, and other reusable visual parts. For dense infographic pages, keep large cards, panels, and photo/chart context in the clean layout base unless the user needs them independently movable.
Omit all long readable text; text will be recreated as editable PPT text boxes.
Do not add new objects. Every asset must be fully visible, unclipped, and surrounded by generous #ff00ff padding.
```

Then remove chroma key with the system imagegen helper when available. Locate it from the active Codex home instead of assuming a portable install path:

```bash
IMAGEGEN_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/scripts/remove_chroma_key.py"
python3 "$IMAGEGEN_HELPER" \
  --input imagegen_asset_sheet_chroma.png \
  --out imagegen_asset_sheet_alpha.png \
  --auto-key border \
  --soft-matte \
  --transparent-threshold 12 \
  --opaque-threshold 220
```

Choose the key color from the asset colors. Do not use `#00ff00` for green icons, green charts, or green badges; use `#ff00ff` or another absent color. Do not enable `--despill` by default because it can wash out same-hue icons. Add `--despill` only after inspecting that it improves edges without damaging colors.

Split the transparent sheet into individual PNG assets. The default splitter uses alpha thresholding, small morphology close, 8-neighbor connected components, and conservative nearby-fragment merging:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/split_alpha_components.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --sort x \
  --square \
  --manifest split_assets.json
```

Inspect extracted assets before rebuilding the PPT. Treat clipped circular icons, missing strokes, accidental fragments, merged components, wrong names/order, and page-fragment crops as repair items. If the assets are wrong, rerun `image_gen` with more padding or fewer objects per sheet, or resplit with different thresholds before touching the PPT manifest.

If a sparse sheet still splits one icon into fragments, retry once with `--merge-gap 24`. If unrelated assets merge, lower `--merge-gap` or set it to `0`. If the asset sheet is crowded, regenerate it instead of tuning the splitter.

Use `--names` when the output order is known:

```bash
python3 "$SKILL_DIR/scripts/split_alpha_components.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --names info_doc_icon.png,info_book_icon.png,bottom_light_icon.png,bottom_chart_icon.png,bottom_target_icon.png \
  --sort x \
  --square
```

For complex sheets where objects touch, crop the transparent generated sheet into individual PNG assets with deterministic boxes. Prefer stable asset names such as `folder_skill.png`, `icon_trigger.png`, `note_a.png`, `underline_orange.png`.

Use the bundled crop helper for deterministic crop boxes and provenance updates:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/crop_image_asset.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out assets/folder_skill.png \
  --box 320,180,620,420 \
  --manifest manifest.json \
  --source-type imagegen \
  --provenance-note "Folder asset cropped from selected imagegen asset sheet and visually inspected."
```

## Manifest Schema

Page manifests use source-image pixel coordinates. Set `source.width_px` and `source.height_px` from `source.png`, then use `box_px: [x, y, width, height]` for every positioned text box, image, and shape. Use `points_px: [x1, y1, x2, y2]` for straight line shapes. The builder converts these pixel coordinates to the PowerPoint slide size from `slide.width` and `slide.height`.

Put every readable source string in `text_inventory`; validation treats it like required text.

Objects may include `z_index` to control visual stacking. Lower values render first. Use this for layered rebuilds: cleaned full-slide background at `0`, native cards/lines at `20`, generated icon assets at `30`, and editable text at `40` or higher.

Text boxes may include `rotation` in degrees for editable axis labels or vertical labels. Line shapes may include `dash` with a DrawingML preset such as `dash`, `sysDot`, or `lgDash` for editable chart grids and timelines.

Text box geometry should be forgiving. Do not draw `box_px` exactly around the visible glyph bounds from the source image. A good manifest text box usually has extra horizontal and vertical slack, especially for Chinese text, bold headings, and renderer-sensitive fonts. If text appears clipped or cramped in `preview.png` or `split_assets_contact.png`, prefer these repairs in order: enlarge `box_px`, add an explicit line break matching the source layout, set `valign: "middle"` for container labels, then adjust `font_size`. Do not hide clipping by using tiny text or by accepting accidental wrapping that changes the source hierarchy.

```json
{
  "slide": {
    "width": 13.333,
    "height": 7.5,
    "background": "#fffaf0"
  },
  "source": {
    "width_px": 1920,
    "height_px": 1080
  },
  "images": [
    {
      "id": "folder_skill",
      "visual_object_id": "folder_skill",
      "asset_kind": "generated_component",
      "path": "assets/folder_skill.png",
      "box_px": [979, 346, 317, 230],
      "z_index": 30,
      "alt": "Skill folder"
    }
  ],
  "text_boxes": [
    {
      "id": "title",
      "text": "如何设计一个好的 Skill",
      "box_px": [79, 50, 1080, 101],
      "font_size": 34,
      "font": "PingFang SC",
      "bold": true,
      "color": "#111111",
      "align": "left",
      "valign": "middle",
      "rotation": 0,
      "z_index": 40
    }
  ],
  "shapes": [
    {
      "type": "line",
      "points_px": [86, 194, 777, 194],
      "stroke": "#e66b00",
      "stroke_width": 3,
      "dash": "dash",
      "z_index": 20
    },
    {
      "type": "rect",
      "box_px": [72, 259, 461, 130],
      "fill": "#fff2bf",
      "stroke": "#111111",
      "stroke_width": 1,
      "z_index": 20
    }
  ],
  "required_text": [
    "如何设计一个好的 Skill"
  ],
  "text_inventory": [
    "如何设计一个好的 Skill"
  ],
  "rasterized_or_omitted_text": [
    {
      "text": "decorative non-editable label",
      "reason": "Approved as part of a raster icon"
    }
  ],
  "asset_provenance": [
    {
      "path": "assets/folder_skill.png",
      "source_object_id": "folder_skill",
      "source": "imagegen_asset_sheet_alpha.png",
      "source_type": "imagegen",
      "provenance_note": "Folder asset visually inspected and cropped from selected imagegen sheet"
    }
  ]
}
```

For a photo-background page, the image entry can be a full-slide no-text background:

```json
{
  "images": [
    {
      "id": "clean_photo_background",
      "visual_object_id": "clean_photo_background",
      "asset_kind": "cleaned_background",
      "path": "assets/background_clean.png",
      "box_px": [0, 0, 1920, 1080],
      "z_index": 0,
      "alt": "Clean no-text photo background"
    }
  ],
  "asset_provenance": [
    {
      "path": "assets/background_clean.png",
      "source": "source.png",
      "source_type": "imagegen",
      "source_object_id": "clean_photo_background",
      "provenance_note": "No-text background generated by image editing from the user-provided slide; all readable text is rebuilt as native PPT text.",
      "contains_readable_text": false
    }
  ]
}
```

## Validation Criteria

Run validation every time:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/validate_pptx.py" {origin_name}_edited.pptx \
  --manifest manifest.json \
  --required-text "如何设计一个好的 Skill" \
  --report validation.json
```

Passing means:

- `zip_ok` is true.
- Required package parts and relationship targets exist.
- PPTX media count matches `manifest.images`, and embedded media bytes match the manifest image files.
- `slides` is at least 1.
- `missing_required_text` is empty, including all `text_inventory` entries.
- `editable_text_shapes` is greater than 0 when readable text exists.
- `images` is greater than 0 when visual assets were extracted.
- All final raster assets have a validator-checked `asset_provenance` entry with valid `source_type`, existing `source`, and manifest-recorded provenance note.
- Readable text that is claimed editable is visible native PPT text in the PPTX itself. Hidden, transparent, 1 pt, off-canvas, or metadata-only text boxes do not count, even if the manifest claims a larger font size.
- Text in `preview.png` and `split_assets_contact.png` is not visibly clipped, cramped against its container, or accidentally wrapped. Structural validation can pass while text placement is still unacceptable; treat preview-visible typography problems as repair items.
- Required non-text visual objects are independently present as named `images` or `shapes` with exact `visual_object_id` or `id` matches to the required-object truth. Do not rely on broad aliases or labels. In strict editable reconstruction, raster objects count when they come from built-in `image_gen` clean bases or generated asset sheets as appropriate: clean bases count for layout/background fidelity, while required independently movable icons/arrows/checks/glyphs must come from separate asset images or native shapes. A tile, grid crop, renamed crop, or large source region that contains several unrelated objects does not count as an extracted visual object.
- For photo-background pages, the clean background is allowed as one full-slide image when `contains_readable_text` is false and all visible text is represented as native PPT text.

For research or strict QA, keep an independent required-object truth file and run the evaluator with `--required-objects`. The truth should list every icon, arrow, note, tape, checkbox, underline, chart glyph, badge, and illustration that must be independently movable/editable.

Use page `preview.png` for parent whole-deck review, and `split_assets_contact.png` for page-level source comparison. The page contact sheet must place the source `origin` and rebuilt `preview` side by side. Do not use macOS Quick Look thumbnails as an acceptance signal because they can distort PPT text layout and produce false line-break failures.

## Repair Workflow

Repair only the smallest failing scope:

1. Run validation and inspect `validation.json`.
2. Inspect `preview.png`, `split_assets_contact.png`, or a real renderer screenshot.
3. Classify the failure:
   - text inventory or OCR miss
   - missing or visibly degraded asset
   - missing or invalid asset provenance
   - bad crop or chroma-key cleanup
   - bad coordinate or size
   - clipped, cramped, or accidentally wrapped text box
   - broken PPTX part or relationship
   - contact-sheet-only font/rendering issue
4. Fix the narrowest artifact: `manifest.json`, one crop from the generated asset sheet, one `image_gen` repair job, or the deterministic script.
5. Rebuild, regenerate `preview.png` and `split_assets_contact.png`, and rerun validation.

Never hide a failure by deleting a `text_inventory` item, removing an asset from the expected layout, or accepting a placeholder as final. If the user explicitly accepts a lower-fidelity result, record the limitation in the final response and in the run notes.

## Common Repairs

- Missing words: add text boxes to the manifest rather than regenerating visual assets.
- Clipped or cramped text: increase box width/height first, then add explicit line breaks or `valign: "middle"` for container labels; reduce font size only after the box has enough slack.
- Accidental wrapping: widen the text box or split the text into source-matching explicit lines. Do not accept new line breaks that change the original visual hierarchy.
- Chinese glyph boxes in `preview.png` or `split_assets_contact.png`: switch preview font to a macOS CJK font such as `/System/Library/Fonts/PingFang.ttc`, `/System/Library/Fonts/STHeiti Medium.ttc`, or another installed Chinese font.
- Low fidelity clean base: rerun `image_gen` with a narrower clean-base prompt, explicitly naming leftover text/icons or drift to remove, then keep the existing text/assets when possible.
- Low fidelity assets: rerun `image_gen` with a narrower asset sheet prompt, increase padding, request fewer objects per pass, then resplit only the affected assets.
- Overlapping objects: assign fixed dimensions and positions in the manifest; do not rely on automatic layout for reconstructed slides.
