# Asset Sheet Prompt 模板

```text
Use case: productivity-visual
Input images: Image 1: slide visual reference
Primary request: create one sparse asset sheet containing only the reusable non-text foreground visual objects from the slide.
Scene/backdrop: perfectly flat solid <#00ff00 or #ff00ff> chroma-key background.
Subject: icons, pictograms, badges, stickers, hand-drawn marks, decorative arrows, check marks, warning symbols, chart glyphs, underlines, tapes, logo-like marks, and other non-text foreground objects listed below. Use the same count, order, semantic identity, colors, stroke style, and rough proportions as the source inventory:
<asset list>
Constraints: every object must be fully visible, internally complete, separated from every other object by generous pure chroma-key space, and surrounded by padding. Spacing is more important than asset size. No missing objects, no substituted symbols, no touching, no overlap, no cross-object shadows, no readable text, no labels, no letters, no numbers, no pseudo text, no full cards, no full panels, no full charts, no page fragments, no watermark. Do not add objects not present in the reference.
```

使用说明：

- 绿色资产不要用 `#00ff00`，改用 `#ff00ff` 或其他缺席颜色。
- 紫色/洋红资产不要用 `#ff00ff`。
- asset sheet 拥挤或对象粘连时，应重新生成更稀疏的 sheet，不要强行后处理。
