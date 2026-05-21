# Imagegen Repair Prompt 模板

## Clean Base Repair

```text
Use case: precise-object-edit
Input images: Image 1: current clean base; Image 2: original slide reference
Primary request: repair only the specified remaining problem in the clean base.
Problem to fix: <leftover text | ghost mark | bad inpainting | duplicated icon | layout drift>
Constraints: change only the specified problem area. Preserve the rest of the clean base composition, colors, texture, lighting, panels, and spacing. Remove leftover readable text or foreground objects completely. No pseudo text, no blur patches, no new objects, no watermark.
```

## Asset Repair

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference; Image 2: previous failed asset or sheet
Primary request: regenerate only the specified foreground asset(s) as clean isolated bitmap object(s) on a flat chroma-key background.
Assets to repair: <asset list>
Constraints: each asset must be complete, separated, unclipped, and surrounded by pure chroma-key padding. Keep the visual metaphor and style close to the slide reference. No readable text, no labels, no extra objects, no shadows touching other assets, no watermark.
```
