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

`manifest.json` is the authoritative page source used by final deck assembly. It must be sufficient to rebuild the page without reading any custom page script. `text_inventory` and `visual_inventory` are only inventories; they do not substitute for positioned `text_boxes`, `images`, and `shapes`.

Goal:
Rebuild the source page as object-level editable PowerPoint. All page object categories, native shape boundaries, and separable asset boundaries must follow `references/page-decision-tree.md`. Do not invent an object-source strategy outside this prompt.

Before writing `manifest.json`, every image/page must complete the three-step decision process in `page-decision-tree.md`:
1. Background recognition and repair: decide whether the background can be restored through PPT structural objects/deterministic runtime, or whether `editppt image edit --image <source.png>` is required to create a source-preserving clean base.
2. Foreground asset separation: every non-text foreground visual object, including foreground photos, screenshots, illustrations, icons, decorations, and similar assets, must use `editppt image` edit mode for source-faithful asset-sheet separation according to the decision tree.
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

Use `editppt image generate/edit/batch` to generate clean bases, background repairs, and asset sheets. Use `editppt formula render-latex` to generate formula image assets and manifest image fragments. Which objects must be separated with `editppt image edit --image <source.png>`, which objects may use native shapes, and which formulas must be converted to LaTeX are all governed by `page-decision-tree.md`. Deterministic CLI/runtime tools may only be used for normalization, recording, background removal, splitting, formula rendering, building, validation, and QA.

`manifest.json` must also contain:

- `visual_inventory`: inventory of non-text visual objects, at least recording id, description, decision, and corresponding asset/background.
- `background_strategy`: background handling mode, source-consistency constraints, whether local repair is used, whether a full imagegen clean base is used, and why.
- `quality_checks`: `font_size_calibrated`, `visual_inventory_matched`, `background_strategy_checked`, and `shape_corner_geometry_checked` must all be true.
- Positioned build objects:
  - every `text_boxes[]` item must include `box_px` and calibrated text styling such as `font_size`;
  - every `images[]` item must include `box_px`;
  - every non-line `shapes[]` item must include `box_px`;
  - every line shape must include `points_px`.
  Missing object coordinates are a current-page failure, even if a separately generated `page.pptx` looks correct.
- Text sizing:
  - make each text `box_px` track the source text bounds plus modest padding, not the entire surrounding card or panel;
  - start from the deterministic builder's default text fitting instead of an oversized default font;
  - keep `fit_text` enabled unless a text box has been manually calibrated and must preserve an exact font size;
  - if the first preview still looks larger than the source, reduce the recorded `font_size` before setting `font_size_calibrated: true`.

Before returning:

- Build page.pptx from manifest.json with the deterministic runtime, not from a separate hand-written PowerPoint script that bypasses the manifest.
- Render preview.png from the same manifest.json.
- Create split_assets_contact.png.
- Run page validation.
- Confirm validation.json contains top-level `passed: true`.
- Confirm `editppt run record` can validate `page.pptx` against `manifest.json`; if manifest rebuild validation would fail, set `passed: false` and fix the manifest before returning.
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
