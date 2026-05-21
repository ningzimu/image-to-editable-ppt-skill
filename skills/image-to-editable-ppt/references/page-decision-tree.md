# 页面决策树

## 1. 检查页面

page worker 收到 `source.png` 后，先建立清单：

- 页面尺寸和类型。
- 所有可读文字。
- 结构对象：卡片、面板、表格、坐标轴、线条、流程框、图表框、分隔线。
- 视觉对象：图标、pictogram、logo-like mark、照片、纹理、插画、手绘标记、贴纸、装饰线、徽章。
- 背景是否被前景对象遮挡。
- 每类文字的 source 字形高度、容器高度、行距和密度。
- 每个矩形/卡片/表格外框的角形：直角、轻微圆角、明显圆角。

## 2. 文字

所有可读文字默认成为原生 PPT text box。

不要用生成图承载可编辑文字。不要用隐藏文本、透明文本、1 pt 文本或 off-canvas 文本满足 text inventory。

字号不要靠默认值猜测。先按 source 中的实际字形高度估算：

- 同一层级文字用同一组 font size，例如标题、副标题、表头、正文、标签、状态徽章。
- 对中文密集版面，初稿宁可比估算小 5%-10%，不要偏大；过大的字会挤压布局并掩盖结构误差。
- 字形高度接近容器高度时，font size 通常需要明显小于容器高度；给 PowerPoint/WPS 的 font metrics 留余量。
- 构建 preview 后，逐类对比 source。如果标题、正文或标签比 source 更粗大、更拥挤或换行更多，先下调 font size 再继续。

manifest 必须通过 `quality_checks.font_size_calibrated=true` 明确记录已经做过字号校准。

## 3. 结构对象

只有基础 primitive 和简单结构对象可以使用原生 PPT shape：

- 直线、虚线、折线。
- 矩形、圆角矩形、圆形、椭圆。
- 普通箭头和连接线。
- 纯色卡片、面板、分隔线、边框。
- 表格线、坐标轴、网格线。
- 简单柱状图、进度条、状态色块。
- 没有风格细节的基础流程框和容器。

角形选择必须保守：

- 先判断 source 角形类别：`straight`、`small-radius`、`large-radius`、`pill`。
- `straight` 用 `rect`。
- `small-radius`、`large-radius`、`pill` 用 `roundRect`，并估算 `source_corner_radius_px`。
- 圆角半径是对象级属性，不是布尔开关。大面板的 8-12 px 轻微圆角不能被重建成 70 px 的大圆角。
- 不确定时放大查看 source 角点；如果仍不确定，记录判断依据并偏向较小半径。
- 每个 `roundRect` shape 必须记录 `source_corner_radius_px`，`corner_reason` 只作为补充说明，不能替代半径。

## 4. 前景视觉对象

以下对象默认用 `$imagegen` 重绘成独立资产：

- 图标、pictogram、symbol、logo-like mark。
- 徽章、贴纸、胶带、印章、角标。
- 手绘标记、手绘箭头、装饰下划线、圈注、对勾、叉号。
- 复杂箭头、图标化节点、带纹理或阴影的元素。
- dashboard 或图表里的语义小图标、趋势图标、警告符号、状态符号。

如果无法确定一个非文字元素是基础结构还是风格化视觉对象，默认用 `$imagegen` 重绘。

但 `$imagegen` 不是“改样式”的许可。page worker 必须先建立 `visual_inventory`，再选择资产来源：

- 简单 primitive：直线、矩形、圆、普通箭头、表格线等，用 native shape。
- 风格化但可重绘的视觉对象：用 `$imagegen` asset sheet，要求对象数量、顺序和语义与 inventory 一致。
- 需要高度一致的小型源图视觉对象：如果无可读文字，且 imagegen 重绘会明显改变身份或丢失细节，可以裁为独立 `source-derived-rasterization` 资产。它必须是可移动的独立对象，并记录 `source_region_px` 或 `source_bbox_px`。
- 承载可读文字的区域、整卡片、整表格、整图表、整页截图不能走 source-derived raster 来冒充可编辑化。

asset sheet 生成后必须对账：

- 切分出的资产数量必须覆盖 inventory 里所有必需视觉对象。
- 每个资产命名要和 inventory 对应，不要把缺失图标写进 known limits 后直接通过。
- 如果 generated asset 明显变样、少笔画、少 icon、变成别的符号，先局部重绘或改用合规的 source-derived raster asset。

source-derived raster asset 的裁剪要求：

- 使用官方脚本裁剪，不要手写临时裁剪脚本。
- crop box 必须覆盖完整对象并额外留安全边距，常见小图标至少 6-12 px。
- 需要透明化时用 border background removal。透明化后可见像素贴到图片边缘时，先作为可疑信号复核 source/contact sheet；它不自动等同于裁断。
- 只有在资产天然应该完整落在透明画布内、且 manifest 显式设置 `require_edge_safe_alpha: true` 时，validation 才把 visible pixels touch edge 作为硬失败。

## 5. 背景策略

按成本递增选择：

1. 原生 PPT 可重建：纯色、简单渐变、普通卡片、表格线、图表框。
2. 确定性脚本可重建：可采样纯色、规则网格、简单重复模式。
3. 已有背景可复用：没有烙印文字，也没有后续要独立重建的前景对象。
4. `$imagegen` 修复：复杂背景被文字、图标、标签、贴纸、手写标记遮挡，移除后需要合理补全。

clean base 不能包含后续会重建的文字或前景对象。否则会产生背景一份、可编辑对象一份的重复。

复杂背景的首要目标是保留 source identity：

- 对照片、空间、真实产品图、复杂 dashboard、插画，clean base 必须以 source 为 edit target 和强约束参考。
- 遮挡少时，只修复被移除文字、标签、图标、贴纸遮住的局部区域；不要让 `$imagegen` 重新想象整张背景。
- 如果遮挡区域很小，优先局部 inpainting 或小 patch；如果背景本身是纯色/规则形状，直接用脚本或 native shape 补齐。
- 当前景覆盖较多、需要整张 clean base 时，可以用 `$imagegen` 重建背景图，但必须对照 source 保留原始构图、透视、物体位置、色彩、光照、材质和关键细节。目标是“去掉前景后的同一张背景”，不是同主题新图。
- 整张 clean base 必须在 `background_strategy` 写 `mode: "imagegen-full-clean-base"`、`source_consistency_contract`、`removed_foreground` 和 `comparison_note`。
- clean base prompt 只写“保留背景”不够；必须列出保留的 camera/perspective/layout/color/light/detail，以及只移除哪些前景。

## 6. 层级

推荐 z-index：

- clean background/base：0
- native structural shapes：10-20
- generated assets：30
- native editable text：40+

## 7. Manifest

页面 manifest 使用 source-image pixel coordinates：

- `source.width_px`
- `source.height_px`
- `box_px: [x, y, width, height]`
- `points_px: [x1, y1, x2, y2]`

文本框要比源图字形边界更宽松，避免 PowerPoint/WPS/preview font metrics 导致裁切或错误换行。

文字和装饰不要重复拆分：

- 一个可读字的笔画必须只属于 native text box，不能再额外用 shape 画同一笔画。
- 独立装饰线、分隔线、按钮下划线可以作为 shape，但必须确认它不是文字的一部分。
- 如果拆分后 preview 出现多一个横杠、多一个点或重复符号，必须删除重复 shape。

还必须包含：

- `visual_inventory`
- `background_strategy`
- `quality_checks.font_size_calibrated`
- `quality_checks.visual_inventory_matched`
- `quality_checks.background_strategy_checked`
- `quality_checks.shape_corner_geometry_checked`
