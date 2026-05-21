# Clean Base Prompt 模板

## Photo / Texture Background

```text
Use case: precise-object-edit
Input images: Image 1: edit target slide and strict visual reference
Primary request: create the same slide background after removing foreground text and foreground objects that will be rebuilt separately.
Preserve exactly: original canvas ratio, composition, camera angle, perspective, crop, major object positions, screen/panel layout, colors, lighting direction, contrast, texture/materials, depth of field, and background identity.
Remove only: readable title, subtitle, caption, label, number, Chinese character, English word, logo-like text, icon, sticker, badge, hand-drawn mark, decorative object, and callout object that will be overlaid separately.
Constraints: fill removed areas with coherent continuation of the original source background. Do not invent a new room, new dashboard, new product, new illustration, new camera angle, new object placement, or different lighting. No ghost text, no blur patches, no dark boxes, no pseudo text, no watermark.
```

## Dense Layout Base

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference
Primary request: create a clean layout-only base for rebuilding an editable PowerPoint page.
Constraints: preserve broad background fills, panels, empty cards, empty containers, table/grid lines, chart frames, shadows that belong to containers, spacing, and overall composition. Remove all readable text, labels, numbers, formulas, Chinese characters, English words, icons, arrows, pictograms, badges, stickers, hand-drawn marks, and reusable foreground objects that will be rebuilt separately. Leave clean blank areas matching surrounding fills. No pseudo text, no fake labels, no watermark.
```
