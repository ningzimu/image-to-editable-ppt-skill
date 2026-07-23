# Image to Editable PPT Skill 说明文档

Image to Editable PPT 是一个把图片、PDF、图片版 PPT 转成**对象级可编辑 PowerPoint**（`.pptx`）的 skill。它先把输入归一化为逐页任务，再重建为 `.pptx`：可读文字尽量恢复为原生文本框，简单几何尽量恢复为 PowerPoint 形状，复杂视觉元素保留为带来源记录的独立图片资产。

![Image to Editable PPT 项目概览](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/image-to-editable-ppt-overview.png)

## 这套文档怎么读

如果你只是想快速上手，先看[快速开始](quickstart.md)。

如果你想了解为什么这个 skill 这么设计、为什么费 token，看[设计理念](design.md)。

如果你要安装、更新、配置 OCR Token 或第三方生图 API，看[安装与配置](installation.md)。

如果你想理解完整转换过程和输出结构，看[标准工作流](workflow.md)。

如果你已经在使用，并且遇到了问题，请查阅[常见问题](faq.md)。

## 子页面

- [快速开始](quickstart.md)：第一次使用时的最短路径、示例命令和产物说明。
- [设计理念](design.md)：对象级重建原则、重建-自检-修正循环，以及和 codex-ppt 的双 skill 分工。
- [安装与配置](installation.md)：安装与更新方式、运行权限建议、OCR Token 申请、图片 backend 与第三方 API fallback。
- [标准工作流](workflow.md)：从输入归一化、页面分派、逐页重建到最终组装校验的完整流程和输出目录结构。
- [常见问题](faq.md)：token 消耗、权限模式、OCR Token、还原精度、agent 支持等高频问题。
- [示例提示词](prompts.md)：单图、多图、PDF、图片版 PPT 转换等可直接复用的提示词。

## 转换效果示例

| 原图 | 转换后可编辑效果 |
| --- | --- |
| ![市场概览原图](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-market-snapshot.png) | ![市场概览转换后](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-market-snapshot.png) |
| ![项目进展汇报原图](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-status-report.png) | ![项目进展汇报转换后](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-status-report.png) |
| ![肾癌 MDT 信息图原图](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-mdt-kidney-cancer.jpg) | ![肾癌 MDT 信息图转换后](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-mdt-kidney-cancer.png) |

## 特色功能

- 支持多种输入：单张图片、多张图片、多页 PDF、图片版 PPT，统一输出可编辑 `.pptx`。
- 对象级重建：文字恢复为原生文本框，简单几何恢复为 PowerPoint 形状，复杂视觉元素保留为独立图片资产，三类对象可以分开调整。
- 测量驱动的文字还原：通过 OCR 为每页生成文字标注（框坐标 + 字号 + 字号分组），模型按测量值还原文字，同级文字字号自动保持一致，参见[安装与配置](installation.md)的 OCR Token 一节。
- 多页并行重建：多页输入由主 agent 分派给 page worker/subagent 并行处理；单页输入由主 agent 本地执行同一重建流程。
- 图片生成和编辑优先调用当前 agent 的内置 `image_gen.imagegen`；只有满足约定的降级条件时才调用 `editppt image`，由 CLI 在 Codex OAuth 和 OpenAI-compatible API 之间选择后端。
- `.pptx` 输入的页面备注会原样复制到输出对应页，不翻译、不摘要、不改写。
- 页面顺序稳定：多张图片按提供顺序生成页面，PDF 和 `.pptx` 保留原页码顺序。

## 关键提醒

**这不是轻量转换器。** 本 skill 采用多智能体协作复原流程，AI 会执行「重建 → 自我检查 → 页面内修正」的循环，可能进行多轮迭代，整体比较费 token。复原一个 10 页 PPT 有可能消耗完 ChatGPT 的 5 小时额度，单页复原时间可能在 10 分钟以上。**推荐 ChatGPT Pro 用户使用；Plus 用户请谨慎使用。**

**如果没有强烈的可编辑需求，请不要使用这个 skill。** 更轻量的做法是直接使用 `gpt-image-2` 的图像编辑能力：把不满意的那一页 PPT 图片发给它，让它针对性修改。

**建议在 Codex 中使用「完全访问权限」执行本 skill**，否则 OCR、图片生成和子 agent 分派等步骤会被审批请求频繁打断，详见[安装与配置](installation.md)。

本 skill 不负责从文章、报告、大纲或想法直接生成全新 PPT。如果你要做的是「生成一份 PPT」，请使用 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill)。

## 相关链接

- GitHub 仓库：https://github.com/ningzimu/image-to-editable-ppt-skill
- 项目主页：https://ppt-skill.ningzimu.vip
- PPT 生成 skill（姊妹项目）：https://github.com/ningzimu/codex-ppt-skill
- 设计与调优经验分享：[2000 个 GitHub Star 换来的经验：好的 AI Skill 是调出来的，不是写出来的](https://mp.weixin.qq.com/s/LaxWBX-nogHPpSxlk-Vs8Q)
