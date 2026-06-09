# Page Worker Prompt Template

```text
Rebuild one page for image-to-editable-ppt.

Run dir: <absolute run dir>
Page id: <page_001>
Page dir: <absolute page dir>
Source image: <absolute page dir>/source.png

You own only this Page dir. Do not edit deck_manifest.json, page_jobs.json, notes_manifest.json, final outputs, the original input, or any other page directory.

Read and follow these local references:
- <skill root>/SKILL.md
- <skill root>/references/cli-helper.md
- <skill root>/references/page-decision-tree.md
- <skill root>/references/manifest-schema.md
- <skill root>/references/qa-rubric.md

Before any image generation or image editing, use the `editppt image` backend specified by `page_request.json.image_backend`. If `editppt image` is unavailable, first follow the CLI error guidance and try `codex login` or `editppt config`; if it is still unavailable, complete the page using the best currently possible editable structure and record the missing assets and reason in `validation.json`.
When you need parameter details for the image backend, input images, batch JSONL, clean bases, or asset sheets, read `editppt image --help` and the relevant subcommand help.

The manifest must reuse `page_request.json.slide` and `page_request.json.content_box`. Do not convert the page to 16:9 yourself and do not recalculate the canvas. All `box_px`, `points_px`, and `polygon_px` values are in `source.png` pixels; the runtime maps them into `content_box` so the source image is not stretched.

Goal:
Rebuild the source page as object-level editable PowerPoint. All page object categories, native shape boundaries, separable asset boundaries, and source-derived raster exceptions must follow `references/page-decision-tree.md`. Do not invent an object-source strategy outside this prompt.

Before writing `manifest.json`, every image/page must complete the three-step decision process in `page-decision-tree.md`:
1. Background recognition and repair: decide whether the background can be restored through PPT structural objects/deterministic runtime, or whether `editppt image edit --image <source.png>` is required to create a source-preserving clean base.
2. Foreground asset separation: decide which large, regular regions can be cropped precisely; all other icons, illustrations, decorations, and similar foreground assets must use `editppt image` edit mode for source-faithful asset-sheet separation according to the decision tree.
3. PPT native element reconstruction: text, text boxes, simple rectangles/rounded rectangles, simple arrows, tables, and similar objects are rebuilt with native PPT structural objects, with font size, corner geometry, and layout calibrated. Formulas do not use native text; first transcribe them to LaTeX, then use `editppt formula render-latex` to render independent image assets into the PPT.

The Page dir must contain:
- manifest.json
- imagegen-jobs.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json
- page_result.json

`validation.json` must be JSON that `editppt run record` can read directly. It must contain a top-level boolean field named `passed`. Write `"passed": true` when the page is deliverable; write `"passed": false` and explain the failure in the same JSON when it is not deliverable. Do not store the pass state only in `runtime_validation.passed`, `status`, or any other nested field.

`page_result.json` must be JSON and must include at least:

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

Use `editppt image generate/edit/batch` to generate clean bases, background repairs, and asset sheets. Use `editppt formula render-latex` to generate formula image assets and manifest image fragments. Which objects must be separated with `editppt image edit --image <source.png>`, which objects may use native shapes or source-derived rasters, and which formulas must be converted to LaTeX are all governed by `page-decision-tree.md`. Deterministic CLI/runtime tools may only be used for normalization, recording, background removal, splitting, cropping, formula rendering, building, validation, and QA.

`manifest.json` must also contain:

- `visual_inventory`: inventory of non-text visual objects, at least recording id, description, decision, and corresponding asset/background.
- `background_strategy`: background handling mode, source-consistency constraints, whether local repair is used, whether a full imagegen clean base is used, and why.
- `quality_checks`: `font_size_calibrated`, `visual_inventory_matched`, `background_strategy_checked`, and `shape_corner_geometry_checked` must all be true.

The allowed scope and crop requirements for source-derived raster assets are defined in `page-decision-tree.md`. If a source-derived raster is used, it must be created with `editppt image crop` and must record `source_region_px` or `source_bbox_px`.

Before returning:

- Build page.pptx from manifest.json.
- Render preview.png.
- Create split_assets_contact.png.
- Run page validation.
- Confirm validation.json contains top-level `passed: true`.
- Check that all required outputs exist.
- As the page reconstructor, self-check preview/contact sheet: font sizes are not too large, no visual objects are missing, complex backgrounds have not been replaced wholesale, and rectangles/corners match the source.
- If a page-local issue is found, fix it inside the current page before returning.

Return only:
page_manifest=`<absolute path>`
page_pptx=`<absolute path>`
preview=`<absolute path>`
contact_sheet=`<absolute path>`
validation=`<absolute path>`
page_result=`<absolute path>`

```

```
