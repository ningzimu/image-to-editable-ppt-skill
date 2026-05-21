# Page Worker Prompt 模板

```text
重建 image-to-editable-ppt 的一个页面。

Run dir: <absolute run dir>
Page id: <page_001>
Page dir: <absolute page dir>
Source image: <absolute page dir>/source.png

你只拥有这个 Page dir。不要编辑 deck_manifest.json、page_jobs.json、notes_manifest.json、final 输出、input 原件或任何其他 page 目录。

在任何生图或改图前，读取并遵守：
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md

同时遵守这些本地 reference：
- <skill root>/references/page-decision-tree.md
- <skill root>/references/imagegen-integration.md
- <skill root>/references/manifest-schema.md
- <skill root>/references/qa-rubric.md
- <skill root>/references/script-contracts.md

目标：
把 source page 重建成对象级可编辑 PowerPoint。所有可读文字必须是原生 PPT text box。只有基础 primitive 可以是 native PPT shape。图标、pictogram、手绘对象、装饰标记、风格承载对象，以及无法确定的非文字对象，必须使用 $imagegen 生成/编辑为独立资产。

开始写 manifest 前必须完成四个校准清单：
1. 字号校准：按 source 中每类文字的实际字形高度、容器高度、行距和密度估算 font_size。第一次构建后对照 preview；如果 preview 字显得比 source 大，先整体下调对应文字层级。不要凭默认审美把标题、正文或标签放大。
2. 视觉对象清单：列出所有非文字视觉对象，逐个决定 `native-shape`、`imagegen-asset`、`source-derived-raster-asset` 或 `background`。asset sheet 必须覆盖清单中的每个必需对象；发现缺图标或生成变形时先 repair，不要直接通过。
3. 背景策略：纯色/规则背景用 native 或脚本；复杂照片/空间/仪表盘需要 `$imagegen` 时，必须把 source 当作 edit target 和强约束参考。可以做整张 clean base，但结果必须对照 source 保留构图、透视、主要物体位置、色彩、光照和背景身份；不允许生成一个相似但不同的新背景。
4. 角形校准：逐个判断容器角形，而不是按元素大小一刀切。直角用 `rect`；轻微圆角、明显圆角、胶囊按钮用 `roundRect`，并写真实估算的 `source_corner_radius_px`。不要为了现代感把直角改圆角，也不要把轻微圆角夸大成胶囊。

必须在 Page dir 内产出：
- manifest.json
- imagegen-jobs.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json
- page_result.json

`page_result.json` 必须是 JSON，至少包含：

```json
{
  "page_manifest": "manifest.json",
  "imagegen_jobs": "imagegen-jobs.json",
  "page_pptx": "page.pptx",
  "preview": "preview.png",
  "contact_sheet": "split_assets_contact.png",
  "validation": "validation.json",
  "page_result": "page_result.json",
  "qa_note": "one sentence",
  "known_limits": []
}
```

使用 $imagegen 的 built-in image_gen 路径生成 clean base、背景修复、asset sheet 和 repair asset。不要直接调用 Image API。不要使用本地脚本、SVG、canvas、HTML/CSS 或 Python 绘图来伪造复杂视觉资产。确定性脚本只可用于归一化、记录、去底、切分、裁剪、构建、验证和 QA。

manifest.json 还必须包含：
- `visual_inventory`: 非文字视觉对象清单，至少记录 id、描述、决策和对应 asset/background。
- `background_strategy`: 背景处理方式、source-consistency 约束、是否局部修复、是否使用整张 imagegen clean base 以及原因。
- `quality_checks`: `font_size_calibrated`、`visual_inventory_matched`、`background_strategy_checked`、`shape_corner_geometry_checked` 都必须为 true。

允许 source-derived raster asset 的窄场景：小型图标、标记、徽章、手绘对象等无可读文字的视觉对象，若从 source 独立裁出比 imagegen 重绘更一致，且不是整页、整卡片、整图表或承载文字的区域，可以裁为独立图片资产。provenance 必须使用 `source-derived-rasterization` 并记录 `source_region_px` 或 `source_bbox_px`。

source-derived raster asset 必须留安全边距并检查 alpha 边缘。不要手写临时裁剪脚本；用 `process_asset_sheet.py --crop-box ... --crop-source source.png --source-type source-derived-rasterization --crop-padding <n> --crop-remove-border-bg` 生成。裁出的可见像素贴到图片边缘时，只能判为“可能裁断”：需要对照 source/contact sheet 判断是否扩大 crop；只有在 manifest 对该资产显式设置 `require_edge_safe_alpha: true` 时，validation 才把贴边作为硬失败。

不要重复拆源图中的文字笔画。例如标题里的“一键重建”已经包含开头“一”，不要再额外画一个同色横杠去模拟这个字的笔画；只有 source 中独立于文字的装饰线才作为 shape。这是对象拆分原则和 QA 观察点，不是 manifest 必填字段。

返回前必须：
- 从 manifest.json 构建 page.pptx
- 渲染 preview.png
- 创建 split_assets_contact.png
- 运行 page validation
- 检查 required outputs 都存在
- 视觉检查 preview/contact sheet：字号不过大、视觉对象无遗漏、复杂背景没有整体换图、矩形/圆角与 source 一致
- 可行时修复最小 page-local 失败范围

只返回：
page_manifest=<absolute path>
page_pptx=<absolute path>
preview=<absolute path>
contact_sheet=<absolute path>
validation=<absolute path>
page_result=<absolute path>
qa_note=<one sentence>
known_limits=<none or short list>
```
