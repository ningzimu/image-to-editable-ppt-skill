# QA Rubric

确定性验证必要但不充分。最终接受前必须检查 preview 和 contact sheet。

## 结构 QA

- PPTX 是有效 zip/package。
- slide count 与输入页数一致。
- PDF/PPTX 页码映射正确。
- media relationship 完整。
- manifest 引用的 asset 文件都存在。
- media hash 与 manifest provenance 匹配。
- speaker notes hash 匹配。
- 不存在 full-slide source raster + editable text overlay 的违规模式。

## 文本 QA

- `text_inventory` 覆盖所有可读文字。
- 每个可编辑文字都是真实可见的 native PPT text box。
- 没有隐藏文本、透明文本、1 pt 文本、off-canvas 文本。
- 预览中没有明显裁切、错误换行、容器文字溢出。
- 中文预览不应显示方框或乱码；必要时使用稳定 CJK 字体。
- 字号和位置必须按 source 校准，不允许默认放大标题、正文或标签。
- 如果 preview 中同层级文字比 source 明显更大、更粗、更拥挤或换行更多，必须 repair。

## 资产 QA

- `visual_inventory` 覆盖所有必需非文字视觉对象。
- 每个必需非文字视觉对象有独立表示，除非明确记录为背景。
- style-bearing 对象应来自 `$imagegen` asset，而不是本地手搓形状。
- asset sheet 切分结果没有粘连、缺边、错名、碎片、跨对象阴影。
- alpha 边缘没有明显 chroma-key 残留。
- 每个最终 raster asset 有 provenance。
- 图标、pictogram 和徽章不能漏项，不能被替换成同类但不同的符号。
- source-derived raster asset 只允许用于无可读文字的小型独立视觉对象，并必须记录 source 区域。
- source-derived raster asset 的可见像素贴到图片边缘是可疑信号，不是默认硬失败；需要对照 source/contact sheet 判断是否裁断。对必须完整落在透明画布内的小图标，可在 manifest 设置 `require_edge_safe_alpha: true` 开启硬校验。

## 背景 QA

- clean base 无可读文字。
- clean base 无会被后续重建的前景对象。
- 背景修复区域无明显 ghost、模糊块、涂抹块、伪文字。
- 纯色/规则背景不应浪费 `$imagegen`。
- 复杂背景 clean base 必须和 source 是同一背景：构图、透视、主要物体位置、色彩、光照和关键细节不能明显漂移。
- 如果 `$imagegen` 生成了同主题但不同背景，即使 deterministic validation 通过，也必须 repair。

## 形状 QA

- source 是直角矩形、表格外框或方形面板时，manifest 必须用 `rect`。
- `roundRect` 只在 source 明确为圆角时使用，并记录 `source_corner_radius_px`。
- 重建圆角半径必须接近 source，轻微圆角不能被放大成胶囊。
- 不要因为设计偏好把普通矩形改成圆角矩形。
- 不要把文字笔画当装饰线重复绘制；出现多一横、多一点、多一符号时需要回看 source 判断是文字笔画还是独立装饰线，再决定是否 repair。

## 视觉 QA

- `preview.png` 必须存在。
- `split_assets_contact.png` 必须存在，并展示 origin 与 preview 对比。
- 视觉漂移、缺图标、缺标签、低质量占位图、粗糙 native-shape 图标都应进入 repair。
- 大容器角形、表格边界、卡片边框要和 source 对齐；圆角误判是 repair blocker，不是低风险 warning。

## 阻塞与 warning

blocker：

- 子 agent 不可用。
- 必需 `$imagegen` 不可用。
- 输入无法归一化。
- final PPTX 无法打开。
- page 缺少 buildable manifest/page.pptx。
- 必需视觉对象缺失。
- 复杂背景 clean base 明显失真或变成不同背景。
- source 直角矩形被重建成圆角矩形，且未能证明 source 有圆角。
- 文字字号/位置明显偏离 source，导致布局拥挤、溢出或遮挡。

warning：

- 轻微视觉漂移。
- 部分非关键装饰未完全一致。
- 已记录的低风险字体差异。

warning 可以如实报告；blocker 不能称为完成。
