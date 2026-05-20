# Image to Editable PPT Workflow

## Table of Contents

- [Use Cases](#use-cases)
- [Input Normalization](#input-normalization)
- [Recommended Output Folder](#recommended-output-folder)
- [Run Manifests And Provenance](#run-manifests-and-provenance)
- [Multi-Page Delegation And Assembly](#multi-page-delegation-and-assembly)
- [Page Reconstruction Loop](#page-reconstruction-loop)
- [Photo Background With Editable Text](#photo-background-with-editable-text)
- [Hand-Drawn Manual Pages](#hand-drawn-manual-pages)
- [Imagegen Asset-Sheet Decomposition](#imagegen-asset-sheet-decomposition)
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
- PDF pages are rendered to page source images with PyMuPDF; page N must map to output slide N.
- PPT/PPTX pages are rendered with LibreOffice/`soffice`; source slide N must map to output slide N.
- PPT/PPTX speaker notes are extracted into `notes_manifest.json` and copied by the parent agent during final deck assembly. Do not rewrite notes.

Use:

```bash
python3 {skill_root}/scripts/prepare_inputs.py input.png
python3 {skill_root}/scripts/prepare_inputs.py one.png two.png three.png
python3 {skill_root}/scripts/prepare_inputs.py deck.pdf
python3 {skill_root}/scripts/prepare_inputs.py image_based_deck.pptx
```

## Recommended Output Folder

Use one fresh folder per job. All intermediate files and final outputs stay inside this folder:

```text
output/image-to-editable-ppt/<job-name>/
├── input/
├── deck_manifest.json
├── rebuilt.pptx
├── validation.json
├── notes_manifest.json
└── pages/
    ├── page_001/
    │   ├── source.png
    │   ├── run_request.json
    │   ├── imagegen-jobs.json
    │   ├── asset_manifest.json
    │   ├── clean_layout_base.png
    │   ├── imagegen_asset_sheet_chroma.png
    │   ├── imagegen_asset_sheet_alpha.png
    │   ├── assets/
    │   ├── split_assets_contact.png
    │   ├── split_assets.json
    │   ├── manifest.json
    │   ├── preview.png
    │   ├── original_vs_rebuilt_diff.png
    │   ├── diff.png
    │   ├── diff.json
    │   ├── validation.json
    │   └── qa_notes.md
    └── page_002/
        └── ...
```

## Run Manifests And Provenance

Use lightweight JSON files to keep the run auditable:

- `run_request.json`: recommended audit file with the source image path, output folder, requested fidelity/editability tradeoff, slide size, and any user constraints.
- `imagegen-jobs.json`: recommended audit file for each `$imagegen` clean base, asset-sheet, or repair job, prompt file or prompt text, source images attached, selected generated output path, and status.
- `asset_manifest.json`: optional expanded asset audit. The validator-enforced provenance lives in `manifest.json` under `asset_provenance`.
- `pages/page_NNN/manifest.json`: the page construction manifest consumed by `build_pptx_from_manifest.py`.
- `deck_manifest.json`: the job-level manifest with input type, page count, page order, per-page manifest paths, and notes manifest path.
- `notes_manifest.json`: source PPT/PPTX notes text and hashes by page. Notes are copied unchanged into the final deck.
- `pages/page_NNN/validation.json`: page validation output.
- root `validation.json`: deck validation output.

Do not record a visual asset as final unless the underlying source exists and has been visually inspected. For editable-first visual decomposition, the source should be a `$imagegen` clean base or `$imagegen` asset sheet, not a crop from the original source slide. Every `images[*].path` in `manifest.json` must have an `asset_provenance` entry with the same `path`, valid `source_type`, existing `source`, and `qa_note`.

Every page manifest must include `completion_status`. Use `ready_for_assembly` only when the page passes validation and is acceptable for the final deck. Use `blocked` when a required clean visual layer or `$imagegen` asset is unavailable. A blocked page is an audit artifact, not a deck input.

## Multi-Page Delegation And Assembly

For multi-image, PDF, and PPT/PPTX inputs, the parent agent creates one page job per source page and dispatches one Codex subagent per page when subagents are available. Each subagent owns only its assigned `pages/page_NNN/` directory. It must return the page manifest, assets, preview, diff, validation report, and `qa_notes.md`.

The parent agent alone owns:

- `deck_manifest.json`
- `notes_manifest.json`
- final `rebuilt.pptx`
- root `validation.json`
- page ordering and notes preservation
- final quality check and delivery

Assemble the final deck only after required page manifests exist:

```bash
python3 {skill_root}/scripts/build_pptx_from_manifest.py \
  --deck-manifest output/image-to-editable-ppt/<job-id>/deck_manifest.json \
  --out output/image-to-editable-ppt/<job-id>/rebuilt.pptx
```

Validate the deck:

```bash
python3 {skill_root}/scripts/validate_pptx.py \
  output/image-to-editable-ppt/<job-id>/rebuilt.pptx \
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
   - `$imagegen` assets for icons, pictograms, hand-drawn marks, tape, texture, shadows, illustrated decorations, and other style-bearing objects.
   - `$imagegen` clean no-text backgrounds for photo or hand-drawn pages where the background itself is not practical native geometry.
4. Preserve source shape semantics. Rectangular panels, tables, chart frames, and report containers stay `rect`; use `roundRect` only for source objects that visibly have rounded corners.
5. Build the manifest with explicit `z_index`: background/base `0`, structural shapes `10-20`, generated assets `30`, editable text `40+`.
6. Run `build_pptx_from_manifest.py` with `--preview`, run `validate_pptx.py`, then inspect source/preview/diff. Fix the smallest failing scope and repeat.

Use `scripts/run_page_experiment.py` when a page manifest already exists and you need a repeatable local loop for chroma cleanup, asset splitting, PPTX build, validation, and source/preview QA:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/run_page_experiment.py" pages/page_001 \
  --preview-scale 144 \
  --qa-pair original_vs_rebuilt.png \
  --pixel-diff
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

Do not use this script as a substitute for visual judgment. It automates the loop; the agent still must inspect the contact sheet and preview.

## Photo Background With Editable Text

Use this branch when the slide is one complex photo/texture background with a small number of overlay text blocks. Examples include nature covers, city photos, product photos, abstract backgrounds, and full-bleed posters where the only editable content is typography.

Do this:

1. Save the original as `source.png`.
2. Use `$imagegen` image editing to remove all overlaid text and generate a no-text background.
3. Inspect the clean background before building the PPT. Reject backgrounds with old text ghosting, blur patches, dark boxes, generated replacement text, logos, or new unrelated objects.
4. Place the clean background as one full-slide image.
5. Recreate every readable string as visible native PPT text boxes.
6. Record provenance for the background as `source_type: "imagegen"` with a `qa_note` explaining that it is an edited no-text background derived from the user-provided slide.

Do not use local PIL/OpenCV blur, threshold masks, dark overlays, or clone-like patches as the final background cleanup for complex photos. These methods often leave readable ghosts or obvious texture damage. They are acceptable only for locating text boxes, generating masks, or diagnosing where `$imagegen` should repair.

Suggested `$imagegen` edit prompt:

```text
Edit the provided slide image to remove all overlaid text while preserving the original photograph/background. Remove every visible title, subtitle, caption, logo-like text, and text shadow. Reconstruct the natural background texture in those areas with no visible ghosting, no blur patches, no dark boxes, no replacement text, no logos, and no new objects. Keep the same 16:9 composition, colors, contrast, lighting, and photographic style. Output only the clean no-text background image.
```

For this branch, strict object-level decomposition is not required for the photo content. The editable objects are the text boxes. The background is a single visual asset unless the user explicitly needs separate editable photo regions.

## Hand-Drawn Manual Pages

Use this branch when the source is a hand-drawn instruction page, sketched workflow, manual, whiteboard-like diagram, or note-style infographic.

Do this:

1. Use `$imagegen` image editing to create a clean no-readable-text visual layer that preserves the paper texture, hand-drawn frames, arrows, tapes, icons, checkbox outlines, warning marks, and other non-text visual structure.
2. Rebuild all readable text as native PPT text. The visual base must not contain readable baked-in text under editable text.
3. If icons or arrows should be independently movable, generate them as separate sparse asset sheets instead of leaving them only in the clean base.
4. Use a handwriting-like font only when it improves resemblance and remains readable; otherwise prefer stable native Chinese fonts over distorted text.
5. Reject clean bases with pseudo text, ghost text, lost sketch lines, or newly invented decorations.

This branch is not a permission to flatten the source page. The hand-drawn visual layer may be raster; the readable content must still be native editable text.

## Dense Infographic Layered Imagegen Workflow

Use this branch for technical route maps, dense infographics, dashboard-like slides, architecture diagrams, and pages with many panels, arrows, icons, chart glyphs, and labels. The goal is cleaner than direct source slicing and more editable than a single generated background.

Default layer model:

1. `clean_layout_base.png`: one `$imagegen` visual base with all readable text removed. For pages with icons that should be independently movable, also ask `$imagegen` to remove those standalone icons from the base and leave clean blank spaces.
2. `imagegen_asset_sheet_*`: one or more sparse chroma-key sheets containing standalone icons, arrows, checks, magnifiers, badges, pictograms, reusable chart glyphs, and diagram parts.
3. `assets/*.png`: transparent split assets from the sheets.
4. Native PPT text boxes: every readable source string, manually verified. Do not use OCR output as the unquestioned truth source.
5. Optional simple native geometry: plain lines, rectangles, circles, or structural shapes that are genuinely better as editable PowerPoint shapes.

Suggested clean-base `$imagegen` prompt:

```text
Using the provided slide image as visual reference, create a clean layout-only visual base with the same canvas ratio and composition. Preserve the title bar, backgrounds, panels, cards, photo areas, chart/diagram context, bands, borders, shadows, and spacing. Remove all readable text, letters, numbers, formulas, Chinese characters, English words, labels, captions, and checklist text. Also remove standalone reusable icons that will be overlaid separately: icons, arrows, check marks, magnifiers, badges, pictograms, and other label-like glyphs. Leave clean blank spaces where removed text or icons used to be, matching the surrounding background fills. No gibberish text, no pseudo text, no fake labels, no watermark.
```

Suggested icon-sheet `$imagegen` prompt:

```text
Using the provided slide image as visual reference, create a sparse asset sheet containing only reusable non-text visual objects: icons, arrows, check marks, magnifiers, badges, pictograms, chart glyphs, and reusable diagram parts. Use a perfectly flat solid #00ff00 chroma-key background. Keep at least 260 px of pure #00ff00 space between every visible object. No touching objects, no cross-object shadows, generous padding, and each icon internally complete as one object. Shrink assets if needed to preserve spacing. No readable text, labels, letters, numbers, pseudo text, full cards, photos, panels, or large diagram backgrounds.
```

Inspect the clean base before assembly. Reject it if it still contains readable text, obvious text ghosts, duplicated standalone icons that should be separate, generated pseudo labels, or large layout drift. Inspect every split-assets contact sheet before assembly. If objects are missing or merged, regenerate a smaller sheet with fewer assets rather than forcing a bad split.

Use the source image for alignment and object inventory, but not as the default visual asset source. Cropping source regions is only allowed in explicit visual-99 mode or for diagnostic comparisons.

Do not repair text overlap by moving editable text over the original raster. The original raster already contains the text. The only acceptable repair is a clean no-text visual base.

## Imagegen Asset-Sheet Decomposition

Use `$imagegen` as the required default decomposition path for non-text visual assets and base visual elements. For dense pages, the reliable pattern is: whole slide reference -> clean no-text/no-standalone-icon layout base -> sparse chroma-key asset sheets -> local alpha cleanup -> deterministic split -> PPT images + editable text boxes. For simpler pages, the shorter asset-sheet-only pattern is acceptable. Do not replace this default path with direct crops from `source.png` or locally drawn approximations.

Near-original fidelity does not loosen the editable reconstruction contract. Source-region crop assets improve visual fidelity and position accuracy, but reduce object-level editability; if they would be required for the page to look correct, block and explain the tradeoff instead of marking the page ready for assembly.

Skip `$imagegen` only when the source page is truly plain and the non-text layer contains only structural geometry that must remain editable, such as straight lines, rectangles, round rectangles, or circles. Prefer `$imagegen` when in doubt, especially for hand-drawn icons, pictograms, tapes, shadows, textured notes, decorative strokes, sketchy arrows, underlines, badges, and other style-bearing or reusable visual parts.

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

Split the transparent sheet into individual PNG assets. The default splitter uses alpha thresholding, small morphology close, 8-neighbor connected components, and conservative nearby-fragment merging. Always create a contact sheet for visual QA unless there is only one extracted asset:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/split_alpha_components.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out-dir assets \
  --sort x \
  --square \
  --contact-sheet split_assets_contact.png \
  --manifest split_assets.json
```

Inspect `split_assets_contact.png` before rebuilding the PPT. Treat clipped circular icons, missing strokes, accidental fragments, merged components, wrong names/order, and page-fragment crops as repair items. If the contact sheet is wrong, rerun `$imagegen` with more padding or fewer objects per sheet, or resplit with different thresholds before touching the PPT manifest.

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

For complex sheets where objects touch, crop the transparent `$imagegen` sheet into individual PNG assets with deterministic boxes. Prefer stable asset names such as `folder_skill.png`, `icon_trigger.png`, `note_a.png`, `underline_orange.png`.

Use the bundled crop helper for deterministic crop boxes and provenance updates:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/crop_image_asset.py" \
  --input imagegen_asset_sheet_alpha.png \
  --out assets/folder_skill.png \
  --box 320,180,620,420 \
  --manifest manifest.json \
  --source-type imagegen \
  --qa-note "Folder asset cropped from selected imagegen asset sheet and visually inspected."
```

## Manifest Schema

Coordinates use inches. The default widescreen page is 13.333 x 7.5 inches. Put every readable source string in `text_inventory`; validation treats it like required text.

Objects may include `z_index` to control visual stacking. Lower values render first. Use this for layered rebuilds: cleaned full-slide background at `0`, native cards/lines at `20`, generated icon assets at `30`, and editable text at `40` or higher.

Text boxes may include `rotation` in degrees for editable axis labels or vertical labels. Line shapes may include `dash` with a DrawingML preset such as `dash`, `sysDot`, or `lgDash` for editable chart grids and timelines.

```json
{
  "slide": {
    "width": 13.333,
    "height": 7.5,
    "background": "#fffaf0"
  },
  "images": [
    {
      "id": "folder_skill",
      "visual_object_id": "folder_skill",
      "asset_kind": "generated_component",
      "path": "assets/folder_skill.png",
      "left": 6.8,
      "top": 2.4,
      "width": 2.2,
      "height": 1.6,
      "z_index": 30,
      "alt": "Skill folder"
    }
  ],
  "text_boxes": [
    {
      "id": "title",
      "text": "如何设计一个好的 Skill",
      "left": 0.55,
      "top": 0.35,
      "width": 7.5,
      "height": 0.7,
      "font_size": 34,
      "font": "PingFang SC",
      "bold": true,
      "color": "#111111",
      "align": "left",
      "rotation": 0,
      "z_index": 40
    }
  ],
  "shapes": [
    {
      "type": "line",
      "left": 0.6,
      "top": 1.35,
      "width": 4.8,
      "height": 0,
      "stroke": "#e66b00",
      "stroke_width": 3,
      "dash": "dash",
      "z_index": 20
    },
    {
      "type": "rect",
      "left": 0.5,
      "top": 1.8,
      "width": 3.2,
      "height": 0.9,
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
      "qa_note": "Folder asset visually inspected and cropped from selected imagegen sheet"
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
      "left": 0,
      "top": 0,
      "width": 13.333,
      "height": 7.5,
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
      "qa_note": "No-text background generated by image editing from the user-provided slide; all readable text is rebuilt as native PPT text.",
      "contains_readable_text": false
    }
  ]
}
```

## Validation Criteria

Run validation every time:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/validate_pptx.py" rebuilt.pptx \
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
- All final raster assets have a validator-checked `asset_provenance` entry with valid `source_type`, existing `source`, and `qa_note`.
- Readable text that is claimed editable is visible native PPT text in the PPTX itself. Hidden, transparent, 1 pt, off-canvas, or metadata-only text boxes do not count, even if the manifest claims a larger font size.
- Required non-text visual objects are independently present as named `images` or `shapes` with exact `visual_object_id` or `id` matches to the required-object truth. Do not rely on broad aliases or labels. In strict editable reconstruction, raster objects count when they come from `$imagegen` clean bases or generated asset sheets as appropriate: clean bases count for layout/background fidelity, while required independently movable icons/arrows/checks/glyphs must come from separate asset images or native shapes. A tile, grid crop, renamed crop, or large source region that contains several unrelated objects does not count as an extracted visual object.
- For photo-background pages, the clean background is allowed as one full-slide image when `contains_readable_text` is false and all visible text is represented as native PPT text.

For research or strict QA, keep an independent required-object truth file and run the evaluator with `--required-objects`. The truth should list every icon, arrow, note, tape, checkbox, underline, chart glyph, badge, and illustration that must be independently movable/editable. Passing pixel diff is not enough.

Use the manifest preview as the default visual QA artifact because it reflects this skill's generated OOXML positions and text boxes. If PowerPoint or WPS is available, a screenshot from that app is also useful. Do not use macOS Quick Look thumbnails as an acceptance signal because they can distort PPT text layout and produce false line-break failures.

To create a simple pixel diff:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
python3 "$SKILL_DIR/scripts/render_diff.py" \
  --expected source.png \
  --actual preview.png \
  --out diff.png \
  --comparison original_vs_rebuilt_diff.png \
  --report diff.json
```

Use `diff.png` and `diff.json` for numeric/algorithmic comparison. Use `original_vs_rebuilt_diff.png` for human QA because it places source, rebuilt preview, and pixel diff together.

## Repair Workflow

Repair only the smallest failing scope:

1. Run validation and inspect `validation.json`.
2. Inspect the preview, real renderer screenshot, or diff image.
3. Classify the failure:
   - text inventory or OCR miss
   - missing or visibly degraded asset
   - missing or invalid asset provenance
   - bad crop or chroma-key cleanup
   - bad coordinate or size
   - broken PPTX part or relationship
   - preview-only font/rendering issue
4. Fix the narrowest artifact: `manifest.json`, one crop from the `$imagegen` asset sheet, one `$imagegen` repair job, or the deterministic script.
5. Rebuild and rerun validation.

Never hide a failure by deleting a `text_inventory` item, removing an asset from the expected layout, or accepting a placeholder as final. If the user explicitly accepts a lower-fidelity result, record the limitation in the final response and in the run notes.

## Common Repairs

- Missing words: add text boxes to the manifest rather than regenerating visual assets.
- Clipped text: increase box width/height, reduce font size, or split into multiple boxes.
- Chinese glyph boxes in preview: switch preview font to a macOS CJK font such as `/System/Library/Fonts/PingFang.ttc`, `/System/Library/Fonts/STHeiti Medium.ttc`, or another installed Chinese font.
- Low fidelity clean base: rerun `$imagegen` with a narrower clean-base prompt, explicitly naming leftover text/icons or drift to remove, then keep the existing text/assets when possible.
- Low fidelity assets: rerun `$imagegen` with a narrower asset sheet prompt, increase padding, request fewer objects per pass, then resplit only the affected assets.
- Overlapping objects: assign fixed dimensions and positions in the manifest; do not rely on automatic layout for reconstructed slides.
