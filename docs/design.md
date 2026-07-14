# 设计理念

Image to Editable PPT Skill 解决的问题只有一个：把「看得见但改不动」的幻灯片，变回「可以逐个对象编辑」的 PowerPoint。

关于这个 skill 设计和调优的完整实践经验，可以看这篇文章：[2000 个 GitHub Star 换来的经验：好的 AI Skill 是调出来的，不是写出来的](https://mp.weixin.qq.com/s/LaxWBX-nogHPpSxlk-Vs8Q)。

## 对象级重建，而不是整页贴图

一张幻灯片图片里的内容，对编辑来说价值并不相同。这个 skill 把每页拆成三类对象分别处理：

- **可读文字** → 尽量恢复为原生文本框，可以直接改字、改字号、改颜色。
- **简单几何**（矩形、圆形、线条、箭头等）→ 尽量恢复为 PowerPoint 形状，可以移动、缩放、改样式。
- **复杂视觉元素**（照片、插画、图标、纹理、手绘装饰）→ 保留为带来源记录的独立图片资产，可以整体移动和替换，但不保证内部可编辑。

对表格、图表、流程图等结构化区域，会优先保留可编辑语义；低置信度时保留为资产，并在验证报告里说明。

## 测量驱动的文字还原

文字的大小和位置不靠目测。转换开始时，整个输入会作为一个批量任务提交给 OCR（PaddleOCR-VL），为每页生成文字标注：精确的框坐标、按源图墨水实测的字号、同级字号分组和识别出的文字内容。AI 在重建时以这些测量值为准，同级文字字号自动保持一致。

不配置 OCR Token 时，skill 会退化为内置的离线检测器——纯几何测量，知道文字在哪、多大，但不识别内容，文字还原质量会打折扣。这也是为什么我们推荐花一分钟申请一个免费 Token，参见[安装与配置](installation.md)。

## 重建 → 自我检查 → 页面内修正

视觉相似不等于可编辑，一次生成也很难直接达标。所以每一页的重建者（主 agent 本地模式或 page worker）会执行一个循环：先重建，再对照源图自检，发现缺字、错位、资产缺失就在页面内修正，可能进行多轮迭代，直到结果足够接近原图。

这个循环是这个 skill 费 token 的根本原因——page worker 可能对一页做很多轮尝试。把一个图片 PPT 转成可编辑 PPT 的成本，可能是生成图片 PPT 成本的 2-3 倍。我们认为这是值得的：交付一个改不动的「像素级复刻」没有意义，但也因此**建议没有强烈可编辑需求时不要使用这个 skill**。

## 多页并行，状态可查

多页输入由主 agent 按并发槽位分派给 page worker 并行重建，每页有独立工作目录和 manifest；分派、页面结果和接受状态都通过 `editppt` CLI 记录，最终由 `editppt run finalize` 按页顺序组装并运行 deck 校验。流程细节参见[标准工作流](workflow.md)。

判断转换质量时，不要只看预览图：应同时看 PPTX 结构、文本覆盖、资产来源和预览/diff。

## 双 skill 分工

这个 skill 只做「重建」，不做「创作」。从文章、报告、大纲生成全新 PPT 是 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill) 的职责；两者的分工是：

- **codex-ppt**：内容 → 图片式 PPT。视觉统一、流程可控，适合大多数分享和汇报场景。
- **image-to-editable-ppt**：图片式页面 → 可编辑 PPT。只在确实需要逐对象编辑时使用。

关于两个技能的详细对比介绍，参见 [skill_duo_intro.pdf](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/main/assets/skill_duo_intro.pdf)——这份 PPT 本身就是由 codex-ppt skill 生成的。
