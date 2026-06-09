# Page Decision Tree

This file is the single source of truth for page decisions. Every `source.png` must be judged in three steps:

1. Background recognition and repair.
2. Foreground asset separation.
3. PPT native element reconstruction.

Do not draw PPT native elements first and then decide background and foreground assets afterward. First define the boundaries between background, foreground, and native structure; then write the manifest.

## Pre-Decision Checklist

Before the three-step decision process, build a page inventory:

- Page size and page type.
- All readable text.
- Background type: solid color, gradient, regular texture, photo, illustration, dashboard, spatial/product image, complex graphic background.
- Whether the background is occluded by text, icons, labels, stickers, hand-drawn marks, or other foreground objects that will be rebuilt later.
- Foreground visual objects: icons, pictograms, logo-like marks, foreground photos, screenshots, image blocks, textures, illustrations, people, plants, devices, hand-drawn marks, stickers, decorative lines, badges.
- PPT native element candidates: text, text boxes, cards, panels, tables, axes, lines, flow boxes, dividers, simple arrows.
- Formula candidates: objective functions, constraints, matrices, fractions, roots, cases, multiline equation groups, ordinary math expressions. Formulas must be listed separately and must not be grouped with ordinary text.
- Source glyph height, container height, line spacing, and density for each text level.
- Corner geometry for every rectangle/card/table outline: straight, slight radius, obvious radius, pill.

The manifest must record `visual_inventory`, `background_strategy`, and `quality_checks`. `quality_checks.font_size_calibrated`, `visual_inventory_matched`, `background_strategy_checked`, and `shape_corner_geometry_checked` must all be `true`.

## 1. Background Recognition and Repair

The first step decides only the background. Do not process foreground assets or text in this step.

### 1.1 Backgrounds That Do Not Need Image Tools

The following backgrounds do not need `editppt image` repair. Rebuild them directly with PPT structural objects or deterministic runtime:

- Solid-color backgrounds.
- Simple gradients.
- Ordinary cards, panels, and container fills.
- Table lines, axes, gridlines, chart frames.
- Regular repeated textures, regular divider bands, simple shadows.
- Blank background regions not occluded by foreground.

Record this kind of background in `background_strategy.mode` as `native-or-script` or an equivalent mode. Do not call the image backend for solid-color or regular backgrounds.

### 1.2 Reusable Background Regions

Existing background regions may be reused only when all of these conditions are satisfied:

- The background itself has no text, labels, icons, stickers, hand-drawn marks, or other foreground objects that need removal.
- Reusing the region will not create a duplicate "one copy in the background, another copy as editable objects" problem.
- The reused region is not a full-page `source.png` with native text overlay.
- The reused region is a background/illustration area within the page, not a whole card, whole table, or whole chart screenshot used to bypass editability.

### 1.3 Backgrounds That Need Image Tool Repair

Use `editppt image edit --image <source.png>` for background repair or clean bases when:

- Complex photos, spaces, real product images, complex dashboards, or complex illustrated backgrounds are occluded by foreground text or icons.
- After removing text, labels, icons, stickers, or hand-drawn marks, occluded areas need to be completed.
- Background and foreground are stuck together, and native shapes cannot preserve source identity.

The clean base target is the same background after removing foreground objects that will be rebuilt later. It is not a new image with a similar theme. The prompt must treat the source as both the edit target and strict visual reference, and must state:

- Preserve: original aspect ratio, composition, perspective, object positions, colors, lighting, materials, textures, depth of field, and background identity.
- Remove: readable text, labels, numbers, icons, stickers, badges, hand-drawn marks, and decorative objects that will be rebuilt later.
- Forbid: new rooms, new dashboards, new products, new camera angles, new object positions, different lighting, pseudo-text, watermarks, blurry patches, or smear artifacts.

If the occlusion is small, prefer local completion or a small patch. Do not let the image backend reimagine the whole background.

### 1.4 Dashboard Is Not Background by Default

A dashboard is not background by default, and it is not a single image block to be screenshotted wholesale.

Dashboard titles, numbers, tables, axes, legends, ordinary chart elements, metric cards, filters, and labels should usually be decomposed in step 3 into PPT native text and structural objects.

Only the following areas may be handled as background or image regions:

- Maps.
- Heatmaps.
- Complex screenshot base images.
- Complex chart image regions whose data cannot be reliably restored.
- Complex textures or base imagery that function as visual background and will not be duplicated by later native objects.

Do not screenshot a whole dashboard, whole table, whole card, or whole chart to skip editable structure.

### 1.5 Background Record

`background_strategy` must explain at least:

- `mode`: `native-or-script`, `source-preserving-local-cleanup`, `imagegen-full-clean-base`, or similar.
- `source_consistency_contract`: composition, perspective, colors, lighting, object positions, and key details that must be preserved.
- `removed_foreground`: foreground objects removed from the background and rebuilt later.
- `comparison_note`: background consistency conclusion after comparing against the source.

## 2. Foreground Asset Separation

The second step decides only the source of non-text foreground visual objects. Foreground objects must enter `visual_inventory` before their source is chosen.

### 2.1 Foreground Assets Must Use Image Edit Separation

Every non-text foreground visual object must use `editppt image edit --image <source.png>` asset-sheet separation, including:

- Foreground photos, foreground screenshots, video covers, foreground image blocks, map fragments, chart-image fragments, and rectangular illustrations.
- Icons, pictograms, symbols, logo-like marks.
- Badges, stickers, tapes, stamps, corner tags.
- Hand-drawn marks, hand-drawn arrows, decorative underlines, circles, checkmarks, crosses.
- Complex arrows, icon-like nodes, objects with texture or shadow.
- Semantic small icons, trend icons, warning symbols, and status symbols in dashboards or charts.
- Leaves, plants, people, animals, computers, phones, devices, scene illustrations, and any other non-text object that carries page style.

These objects must not be approximated with native primitives, even if they appear to be made from circles, lines, rectangles, or ellipses. The criterion is not "can it be drawn"; the criterion is whether it is a foreground visual asset rather than a layout primitive.

Do not use direct source-image snippets as a substitute for source-faithful asset-sheet separation.

### 2.2 Asset Sheet Prompt Principles

An asset sheet is source-faithful separation, not redraw. The prompt must require:

- Separate existing objects from the source.
- Preserve original shapes, strokes, colors, proportions, internal spacing, texture, and visual identity.
- Use a flat chroma-key background; choose the key color based on the subject colors in `visual_inventory`.
- Every object is complete, does not touch or overlap other objects, and has sufficient padding.
- Object count and order match `visual_inventory`.
- Do not generate readable text, labels, pseudo-text, or watermarks.
- Do not generate whole cards, whole panels, whole charts, or full-page fragments.
- Do not redraw, beautify, simplify, replace with synonymous symbols, or create cleaner substitute icons.

The key color can be cyan, green, magenta, red, orange, or another high-saturation pure color. The selection criterion is not a fixed color; the color must not appear in the current assets and must be sufficiently distant from all subject colors, stroke colors, shadow colors, and highlight colors. For example, green subjects should not use `#00ff00`, blue/purple subjects should not use cyan/blue families, purple or magenta subjects should not use `#ff00ff`, and white subjects should not use white or light gray backgrounds. If `process-sheet` background removal makes the subject fade, cuts off edges, or leaves key-color remnants, first regenerate an asset sheet with a different key color, then consider tuning removal parameters.

### 2.3 Asset Sheet Reconciliation and Fixes

After an asset sheet is generated, reconcile it:

- Split asset count covers all required objects in `visual_inventory`.
- Every asset name corresponds to the inventory.
- Missing objects, wrong symbols, missing strokes, severe deformation, background attachment, text contamination, or synonymous substitution must be regenerated or fixed before use.
- Minor line width, antialiasing, proportion, shadow, or detail differences may be delivered as warnings with the current PPT.
- Approximating a foreground object that must be separated with native primitives is not a warning; it must be changed to source-faithful separation.

## 3. PPT Native Element Reconstruction

The third step reconstructs all objects that should be carried by native PowerPoint structure and handles formula assets. At this point, background and foreground asset sources have already been decided.

### 3.1 Text and Text Boxes

All readable text defaults to native PPT text boxes. Formulas are not ordinary readable text in this section; they must be transcribed to LaTeX and rendered as formula image assets according to 3.2.

Do not use generated images to carry editable text. Do not use hidden text, transparent text, 1 pt text, or off-canvas text to satisfy text inventory.

Exceptions are text that is part of brand or background identity rather than ordinary editable text:

- Logo wordmarks, brand symbols, and trademark text.
- Brand text on product packaging.
- Place names on map base imagery.
- Small text inside UI screenshots that is not required to be editable.
- Signage in photo backgrounds.
- Textures such as newspapers, book pages, or code.
- Tiny text with very low OCR confidence that does not affect main meaning.

These exceptions should be explained in `visual_inventory` or `asset_provenance`. Do not disguise main titles, subtitles, body text, table text, legends, axis labels, numbers, tags, or button text as exceptions.

Do not guess font sizes from defaults. First estimate from actual source glyph height:

- Use the same font-size group for the same text level, such as title, subtitle, header, body, label, or status badge.
- For dense Chinese layouts, the first draft should be 5%-10% smaller than the estimate rather than oversized.
- When glyph height is close to container height, font size usually needs to be clearly smaller than container height; leave room for PowerPoint/WPS font metrics.
- Text boxes should be looser than the source glyph bounds to avoid clipping or incorrect wrapping caused by PowerPoint/WPS/preview font metrics.
- The deterministic builder clamps oversized requested fonts to fit the text box, so keep `fit_text` enabled for first drafts and make `box_px` follow the source text bounds, not the whole container.
- After building a preview, compare text by level against the source. If title, body, or label text is larger, heavier, more crowded, or wraps more than in the source, reduce font size before continuing.

The manifest must record completed font-size calibration with `quality_checks.font_size_calibrated=true`.

### 3.2 Formula Handling

Formulas are not reconstructed as ordinary native text boxes. When a formula is present:

- First transcribe the formula from the source into LaTeX.
- Use `editppt formula render-latex` to render it into an SVG, PNG, or PDF image asset.
- Prefer SVG. If the target environment is unstable or SVG preview/PowerPoint compatibility is problematic, use PNG.
- The render command must write into the page directory, for example:

```bash
editppt formula render-latex <page_dir> \
  --tex "\\sum_{i \\in N} p_{ij} x_{ij} \\ge a_j u_j" \
  --out assets/formula_c2_1.svg \
  --box 105,392,390,90 \
  --id formula_c2_1 \
  --fragment assets/formula_c2_1.fragment.json
```

Then merge the fragment's `images`, `asset_provenance`, and `formula_inventory` into `manifest.json`.

Formula asset record requirements:

- Record formula id, LaTeX source, and `decision: "latex-rendered-image"` in `visual_inventory`.
- `asset_provenance.source_type` must be `latex-rendered-formula`.
- `asset_provenance.source` points to the corresponding `.tex` file.
- `provenance_note` explains that the formula was rendered from LaTeX and that visual fidelity is prioritized over formula object-level editability.
- Do not assemble formulas with Unicode subscripts/superscripts, do not hand-write many formula text boxes, and do not use source-image snippets for formulas.

If the machine lacks a TeX engine, SVG/PNG converter, or LaTeX compilation fails:

- Continue producing the current openable PPT.
- Record the formula id, LaTeX source, CLI error, and required tool/package installation or repair in `validation.json`.
- Do not replace the formula with a full-page screenshot.

### 3.3 Structural Primitives and Layout Objects

The following objects may use native PPT shapes or structural objects:

- Straight lines, dashed lines, polylines.
- Rectangles, rounded rectangles, circles, ellipses.
- Ordinary arrows and connectors.
- Solid-color cards, panels, dividers, borders.
- Tables, table lines, axes, gridlines.
- Simple bar charts, progress bars, status color blocks.
- Simple callouts.
- Basic flow boxes and containers without style-specific details.

These objects must only be layout structure; they must not carry semantic icons or visual identity. A DNA mark, lock, network node, target, magnifier, or checkmark inside a circular icon is not a structural primitive and must be separated in step 2.

### 3.4 Corner Geometry and Shape Details

Corner decisions must be conservative:

- First classify source corner geometry: `straight`, `small-radius`, `large-radius`, or `pill`.
- Use `rect` for `straight`.
- Use `roundRect` for `small-radius`, `large-radius`, and `pill`, and estimate `source_corner_radius_px`.
- Corner radius is an object-level property, not a boolean switch. An 8-12 px slight radius on a large panel must not be rebuilt as a 70 px pill-like radius.
- If uncertain, zoom into the source corner. If still uncertain, record the basis and prefer a smaller radius.
- Every `roundRect` shape must record `source_corner_radius_px`; `corner_reason` is only supplemental and cannot replace the radius.

### 3.5 Text Strokes and Decoration Splitting

Do not duplicate text strokes and decorations:

- A readable character stroke belongs only to the native text box; do not draw the same stroke again as a shape.
- Independent decorative lines, dividers, and button underlines may be shapes, but only after confirming they are not part of text.
- If the split produces an extra dash, dot, or repeated symbol in the preview, remove the duplicate shape.

### 3.6 Layering

Preserve grouping relationships between objects, for example:

- Icon and circular base.
- Badge and number.
- Speech bubble and text.
- Hand-drawn arrow and annotation.
- Card background, title, chart, and labels.

Recommended z-index:

- clean background/base: 0
- native structural shapes: 10-20
- separated foreground assets: 30
- native editable text: 40+
- circles, stickers, or hand-drawn marks that must sit above text in special cases: 50+

Do not let the background cover text. Do not put foreground assets on the wrong layer. Do not let the same text, icon, or decorative object appear both in an image layer and a native object layer.

## Manifest Coordinates and Records

Page manifests use source-image pixel coordinates:

- `source.width_px`
- `source.height_px`
- `box_px: [x, y, width, height]`
- `points_px: [x1, y1, x2, y2]`

They must also contain:

- `text_inventory`
- `visual_inventory`
- `background_strategy`
- `quality_checks.font_size_calibrated`
- `quality_checks.visual_inventory_matched`
- `quality_checks.background_strategy_checked`
- `quality_checks.shape_corner_geometry_checked`

The page reconstructor is responsible for one page-level self-check. The self-check evidence is recorded in structured manifest fields and in `validation.json`. The self-check covers at least:

- Whether the background preserves source composition, perspective, colors, and object positions.
- Whether the background still contains objects that will be rebuilt later.
- Whether all main text is native text.
- Whether font sizes were calibrated against the source.
- Whether foreground assets are complete.
- Whether any full page, whole card, whole table, whole dashboard, or whole chart was turned into a screenshot.
- Whether image-layer text and native text are duplicated.
- Whether rounded corners, straight corners, and shape details are correct.
- Whether dashboards and charts were reasonably decomposed.
- Whether z-index is correct.

## Current-Page Fixes and Warning Decisions

Must be fixed in the current page:

- Background clean base visibly drifts and becomes a new background with a related theme.
- Background still contains text, icons, labels, stickers, or hand-drawn marks that will be rebuilt later.
- An object that step 2 marks as requiring image-edit separation is approximated with native primitives or direct source-image snippets.
- Step 2 asset sheet has missing objects, wrong symbols, missing strokes, severe deformation, background attachment, or text contamination.
- Main readable text remains inside an image and is not made native text.
- The same text, icon, or decorative object appears both in the image layer and as a native object.
- A dashboard, table, card, or chart is screenshotted wholesale, skipping editable structure.
- Text font size or position visibly deviates from the source and causes crowding, overflow, or occlusion.
- A straight-corner source rectangle is rebuilt as a rounded rectangle without evidence that the source has rounded corners.
- Wrong z-index causes text or key objects to be covered.

May be delivered as warnings with the current PPT:

- Minor line-width, antialiasing, proportion, shadow, or detail differences after image-backend separation.
- Minor visual drift in non-critical decorations.
- Recorded low-risk font differences.

Warnings cannot hide failures to follow the three-step decision process. When an object-source decision violates this decision tree, it must be fixed in the current page.
