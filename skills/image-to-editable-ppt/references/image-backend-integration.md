# Image Backend Integration

## Backend Contract

Use `deck_manifest.json.image_backend` as the run-level contract. Copy it into each non-sample `page_request.json` before dispatch. A page worker must use only `page_request.json.image_backend`; if unavailable, return a blocker.

`imagegen-jobs.json` remains the page-local job record for generated or edited images, regardless of backend.

## Backend Selection

Prefer the current environment's built-in image generation/editing tool when available. In Codex, the built-in backend contract is `tool_name: image_gen` and `tool_call: image_gen.imagegen`; it does not require `OPENAI_API_KEY`. Use `editppt image` only when the built-in tool is unavailable, lacks a required capability, or the user explicitly requests API/CLI or a third-party OpenAI-compatible proxy.

Do not switch to API/CLI for ordinary size, quality, batching, transparent asset, targeted repair, or output-path convenience. A prompt that mentions `gpt-image-2` does not require API configuration when the built-in image tool is available.

If API/CLI fallback is actually required, configure it once through the unified CLI:

```bash
editppt config --api-key "your-api-key" --model gpt-image-2
```

For a third-party OpenAI-compatible proxy, read the provider's image-generation/editing documentation first, then set the provider's base URL and model name:

```bash
editppt config \
  --api-key "your-api-key" \
  --base-url "https://your-openai-compatible-endpoint/v1" \
  --model openai/gpt-image-2
```

The config file is `~/.editppt/config.yaml`; on Windows it is `%USERPROFILE%\.editppt\config.yaml`. Never write API keys into the project directory, run directory, or skill directory.

Normal `editppt prepare` already records the built-in Codex `image_gen` backend by default. Only override the backend when API fallback or a custom backend is required:

```bash
editppt run backend <run> --mode cli-api-fallback --model gpt-image-2
```

## Input Images

Label every input image role: `edit target`, `visual reference`, or `supporting input`. In built-in mode, inspect local edit targets before generation/editing so they are visible in the worker context. In CLI/API mode, pass required local images through `editppt image edit`.

## Clean Base

Clean base is for removing foreground objects that will be rebuilt and restoring the occluded background. Use it for photos, textures, illustrations, complex gradients, and semantic inpainting. Do not use it for plain colors, simple gradients, ordinary cards, table lines, chart frames, or regular backgrounds that native shapes or deterministic runtime can rebuild reliably.

The source image must be treated as an edit target and strict visual reference. Preserve composition, perspective, object positions, color, lighting, material, depth, and background identity. List concrete `preserve` and `remove` items in prompts.

## Asset Sheet

Generate sparse chroma-key asset sheets for independent bitmap assets. Require a flat key background, wide spacing, complete objects, no readable text, no whole cards/charts/page fragments, no merged objects, no cross-object shadows, and no missing required object from `visual_inventory`.

Use `#00ff00` by default. Use `#ff00ff` when green subjects make key removal unsafe.

## Output Handling

Copy every selected generated image into the page directory and record it with `editppt image import`. Manifests must not reference only agent-default generated-image paths.

## Transparent Assets

Generate asset sheets on a flat chroma-key background and process them with `editppt image process-sheet`. Validate alpha edges before referencing assets.

For small non-text visual objects where source identity matters more than redrawing, use `editppt image crop <page_dir> --source source.png --box <left,top,right,bottom> --out assets/<name>.png --source-type source-derived-rasterization --padding <n>` and record `source_region_px` or `source_bbox_px`.

## Prompt Patterns

For clean bases, preserve source identity and list preserve/remove items. For asset sheets, require spacing, complete objects, no readable text, no object merging, and source-consistent symbols. For repairs, make one minimal change and re-check preview/contact sheet.

### Clean Base: Photo / Texture Background

```text
Use case: precise-object-edit
Input images: Image 1: edit target slide and strict visual reference
Primary request: create the same slide background after removing foreground text and foreground objects that will be rebuilt separately.
Preserve exactly: original canvas ratio, composition, camera angle, perspective, crop, major object positions, screen/panel layout, colors, lighting direction, contrast, texture/materials, depth of field, and background identity.
Remove only: readable title, subtitle, caption, label, number, Chinese character, English word, logo-like text, icon, sticker, badge, hand-drawn mark, decorative object, and callout object that will be overlaid separately.
Constraints: fill removed areas with coherent continuation of the original source background. Do not invent a new room, new dashboard, new product, new illustration, new camera angle, new object placement, or different lighting. No ghost text, no blur patches, no dark boxes, no pseudo text, no watermark.
```

### Clean Base: Dense Layout Base

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference
Primary request: create a clean layout-only base for rebuilding an editable PowerPoint page.
Constraints: preserve broad background fills, panels, empty cards, empty containers, table/grid lines, chart frames, shadows that belong to containers, spacing, and overall composition. Remove all readable text, labels, numbers, formulas, Chinese characters, English words, icons, arrows, pictograms, badges, stickers, hand-drawn marks, and reusable foreground objects that will be rebuilt separately. Leave clean blank areas matching surrounding fills. No pseudo text, no fake labels, no watermark.
```

### Asset Sheet

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference
Primary request: create one sparse asset sheet containing only the reusable non-text foreground visual objects from the slide.
Scene/backdrop: perfectly flat solid <#00ff00 or #ff00ff> chroma-key background.
Subject: icons, pictograms, badges, stickers, hand-drawn marks, decorative arrows, check marks, warning symbols, chart glyphs, underlines, tapes, logo-like marks, and other non-text foreground objects listed below. Use the same count, order, semantic identity, colors, stroke style, and rough proportions as the source inventory:
<asset list>
Constraints: every object must be fully visible, internally complete, separated from every other object by generous pure chroma-key space, and surrounded by padding. Spacing is more important than asset size. No missing objects, no substituted symbols, no touching, no overlap, no cross-object shadows, no readable text, no labels, no letters, no numbers, no pseudo text, no full cards, no full panels, no full charts, no page fragments, no watermark. Do not add objects not present in the reference.
```

Asset sheet notes:

- 绿色资产不要用 `#00ff00`，改用 `#ff00ff` 或其他缺席颜色。
- 紫色/洋红资产不要用 `#ff00ff`。
- asset sheet 拥挤或对象粘连时，应重新生成更稀疏的 sheet，不要强行后处理。

### Clean Base Repair

```text
Use case: precise-object-edit
Input images: Image 1: current clean base; Image 2: original slide reference
Primary request: repair only the specified remaining problem in the clean base.
Problem to fix: <leftover text | ghost mark | bad inpainting | duplicated icon | layout drift>
Constraints: change only the specified problem area. Preserve the rest of the clean base composition, colors, texture, lighting, panels, and spacing. Remove leftover readable text or foreground objects completely. No pseudo text, no blur patches, no new objects, no watermark.
```

### Asset Repair

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference; Image 2: previous failed asset or sheet
Primary request: regenerate only the specified foreground asset(s) as clean isolated bitmap object(s) on a flat chroma-key background.
Assets to repair: <asset list>
Constraints: each asset must be complete, separated, unclipped, and surrounded by pure chroma-key padding. Keep the visual metaphor and style close to the slide reference. No readable text, no labels, no extra objects, no shadows touching other assets, no watermark.
```
