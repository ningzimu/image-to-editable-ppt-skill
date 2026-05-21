# `$imagegen` 集成

## 入口

所有图片生成、图片编辑、背景修复、透明 bitmap 和 asset sheet 都必须使用 `$imagegen`。

使用前读取：

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

不要在本 skill 里直接调用 Image API，不写临时 SDK 脚本。

## Built-in-first

`$imagegen` 默认使用 built-in `image_gen`。本 skill 不切换模型、不自行决定 CLI fallback。若 `$imagegen` 自己要求用户确认 fallback，则按 `$imagegen` 规则询问。

## 本地图片角色

page worker 必须明确每张输入图片角色：

- `source.png` 作为 edit target：用于 clean base、背景修复、去文字。
- `source.png` 作为 visual reference：用于 asset sheet 风格和对象参考。
- 已生成的 clean base 或 asset sheet 作为 repair target。

如果 built-in edit 需要本地图片进入上下文，先让图片可见，再调用 built-in edit。

## Clean base

clean base 用于移除后续会重建的前景对象，并修复被遮挡的背景。

适用：

- 照片、纹理、插画、纸张质感、复杂渐变、复杂光影。
- 前景文字、图标、标签、贴纸、手写标记遮住了背景。
- 移除后需要 semantic inpainting。

不适用：

- 纯色。
- 简单渐变。
- 普通卡片、表格线、图表框。
- 可用 native shape 或脚本可靠重建的规则背景。

保真要求：

- clean base 必须把 `source.png` 作为 edit target 和强约束参考，不要只凭文字 prompt 生成同主题新图。
- 输出应保持原始构图、透视、主要物体位置、屏幕内容布局、色彩、光照、材质、景深和背景身份。
- 只移除后续会重建的前景文字、图标、标签、贴纸、手绘标记和装饰对象。
- 如果整张 clean base 与 source 的空间、物体、光照或 dashboard 内容明显不同，不能通过 QA；应重新编辑或缩小为局部修复。
- prompt 中必须具体列出 `preserve` 项和 `remove` 项，例如会议室桌椅位置、大屏位置、屏幕蓝色图形结构、窗户/灯带方向等。

## Asset sheet

默认使用稀疏 chroma-key asset sheet 来减少生图次数。

要求：

- 背景是纯色 chroma-key。
- 元素之间留足距离。
- 每个元素内部完整。
- 不要可读文字。
- 不要整卡片、整图表、整页面片段。
- 不要对象粘连、跨对象阴影、裁切边缘。
- 不要漏掉 `visual_inventory` 中的必需对象。
- 不要把 source 中的 icon 改成同类但不同的符号。

生成后：

1. 用 `$imagegen` helper 去 chroma-key。
2. 用 `process_asset_sheet.py` 做去底、组件切分或定点裁剪；`split_alpha_components.py` 只是它的内部组件拆分 helper。
3. 检查 alpha 和切分结果。
4. 与 `visual_inventory` 对账：数量、命名、语义和大体外观都必须匹配。
5. 写入 manifest provenance。

如果某个小型视觉对象需要高度一致、没有可读文字、且 imagegen 重绘会改变身份，可以裁为独立 `source-derived-rasterization` 资产，并记录 source 区域。它不能用于整页、整卡片、整图表或承载文字的区域。

## 结果记录

生成图通常先落到 `$CODEX_HOME/generated_images/...`。

page worker 必须用 `record_imagegen_result.py` 把选中结果复制到 page 目录，并记录：

- source path
- output path
- prompt path/hash
- input image roles
- sha256
- metadata
- completed_at

不要让 `manifest.json` 引用只存在于 `$CODEX_HOME/generated_images/...` 的图片。
