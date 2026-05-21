---
name: image-to-editable-ppt
description: 当用户提供一张或多张幻灯片图片、图片版 PPT/PPTX 或 PDF，并要求转成可编辑 PowerPoint/PPTX、重建幻灯片对象、保留页面备注或做可编辑化复刻时使用。
---
# Image to Editable PPT

## Overview

这个 skill 用于把视觉型幻灯片输入重建成对象级可编辑的 PowerPoint `.pptx`。

输入可以是一张图片、多张图片、PDF、图片版 PPT/PPTX。输出始终是 `.pptx`。目标不是把整页截图包进 PPT，而是尽量让可读文字成为原生 PowerPoint 文本框，让基础结构成为原生形状，让复杂视觉元素成为独立图片资产，并用 manifest、预览和验证报告保证结果可检查、可返工。

默认取舍：对象级可编辑率优先。宁可视觉略粗糙，也不要用整页 raster 冒充可编辑 PPT。

## Hard Constraints

- 每一个来源页面都必须由 page subagent 重建，包括单张图片输入。
- 主 agent 不做页面重建，只做 orchestration。
- 不设计父 agent 单独执行、顺序降级执行或低保真降级模式。没有可用 page subagent 就停止，不进入页面重建。
- 所有生图、改图、背景修复、透明 bitmap 资产和 asset sheet 都必须使用 `$imagegen` skill。
- `$imagegen` 的默认路径是 built-in `image_gen`。不要在本 skill 里直接调用 Image API。
- 如果页面需要 `$imagegen`，但 `$imagegen` 或 built-in `image_gen` 不可用，停止该页并报告 blocker，不伪造资产。
- 原始整页 `source.png` 加可编辑文本覆盖是失败模式，不是 fallback。
- 只有基础 primitive 和简单结构对象可以用原生 PPT shape。非文字视觉对象不确定时，默认用 `$imagegen` 重绘成独立资产。
- page worker 必须先做文字字号、视觉对象、背景策略和形状角形的清单校准，再写 manifest；不能靠审美猜测默认字号或默认圆角。
- 关键状态只能由脚本推进。agent 不能手写 JSON 把 page、imagegen job 或 run 标成完成。

## Visible Progress Plan

正常运行时，主 agent 必须保持一个用户可见 checklist，同一时间只有一个 active step：

1. 准备输入和任务目录。
2. 分派页面重建。
3. 重建页面对象。
4. 检查并修复页面。
5. 组装和验证 PPTX。

完成条件：

- `准备输入和任务目录`：`deck_manifest.json`、`page_jobs.json`、`pages/page_NNN/source.png`、`notes_manifest.json` 已存在。
- `分派页面重建`：主 agent 按 `max_concurrent_pages` 分批 spawn page subagent；每个已 spawn page 都由 `record_page_dispatch.py` 记录为 dispatched。如果不能继续 spawn subagent，停在这里并报告 blocker。
- `重建页面对象`：每个 page 都由 page worker 产出 `manifest.json`、`page.pptx`、`preview.png`、`split_assets_contact.png`、`validation.json`、`page_result.json`。
- `检查并修复页面`：所有 page 通过 `record_page_result.py` 记录，repair queue 清空；无法修复时报告 blocker。
- `组装和验证 PPTX`：`final/<origin>_edited.pptx` 和 `final/validation.json` 已存在。

不要只因为聊天里说完成就标记步骤完成；必须有真实文件或脚本推进的状态。

## Default Workflow

1. 运行 `prepare_deck_run.py` 创建 run 目录、归一化输入、生成 deck/page manifest 和 page request。
2. 运行 `page_job_status.py` 查看待分派页面、active dispatches 和可用 dispatch slot。
3. 主 agent 按 `max_concurrent_pages` 分批 spawn 普通 Codex worker subagent；不要一次性 spawn 超过运行时并发上限。
4. spawn 后立即运行 `record_page_dispatch.py` 记录 dispatch。
5. 每个 page worker 只在自己的 page 目录内工作，完成 page-level build、preview、contact sheet、validation。
6. page worker 返回后，主 agent 运行 `record_page_result.py` 检查文件、路径和 hash，并推进 page 状态。
7. 再次运行 `page_job_status.py`；如果还有 pending/repair_needed page，就继续下一批分派。
8. 如有页面问题，运行 `queue_page_repairs.py` 生成 repair item，再分批分派 repair worker。
9. 所有 page accepted 后，运行 `finalize_deck_run.py` 组装最终 PPTX、复制 notes、运行 deck validation 和 QA summary。

正常主入口是 `prepare_deck_run.py`。不再保留旧输入归一化脚本作为公开入口或兼容 wrapper。

## Generation Delegation

使用 `$imagegen` 前必须读取并遵守：

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

本 skill 只组合 `$imagegen`，不重新定义图片生成 API 规则。

页面内需要 `$imagegen` 的常见场景：

- complex background 上有文字、图标或前景对象，需要 source-preserving foreground removal + localized background restoration。
- 图标、pictogram、徽章、贴纸、手绘标记、风格化箭头、装饰符号等需要作为独立资产。
- 需要生成 chroma-key asset sheet，再本地去底、切分、透明化。
- 需要 targeted repair 某个 clean base 或某个前景资产。

项目实际使用的生成图片必须复制到 page 目录，并通过 page-local `imagegen-jobs.json` 记录。不要让 manifest 引用只存在于 `$CODEX_HOME/generated_images/...` 的图片。

复杂背景默认保留 source identity。可以用 `$imagegen` 生成 clean background，但必须把 source 当作 edit target 和强约束参考来修复/重建，不能生成一个“同类但不同”的新背景。遮挡少时优先局部修复；遮挡多或需要整张 clean base 时，也必须保留原始构图、透视、主要物体位置、色彩、光照和背景细节，并在 manifest 的 `background_strategy` 里记录保真策略。

## Subagent Dispatch

page subagent 是唯一的页面重建执行者。主 agent 不重建页面。

每个 page worker 必须收到自包含 prompt，至少包含：

- run dir、page id、page dir、source image 绝对路径。
- 允许写入范围：只能写当前 page dir。
- 禁止写入范围：deck manifest、notes manifest、final deck、其他 page。
- 必读 reference：`page-decision-tree.md`、`imagegen-integration.md`、`manifest-schema.md`、`qa-rubric.md`。
- 必读 `$imagegen/SKILL.md`。
- required outputs 和返回格式。

page worker prompt 模板在 `prompts/page-worker.md`。

如果无法 spawn page subagent，停止并报告 blocker。不要顺序执行页面重建。

## Rules

- 文字：所有可读文字都应成为可见原生 PPT text box。隐藏、透明、1 pt、off-canvas 或 metadata-only 文本不算可编辑文字。
- 字号：先根据 source 字形高度、容器高度和同行密度估算，再用 preview 对照缩放；不确定时偏小而不是偏大。manifest 必须记录 `quality_checks.font_size_calibrated=true`。
- 结构：只有基础 primitive 可以用原生 PPT shape，例如直线、矩形、圆形、表格线、坐标轴、简单柱状块、基础容器。矩形容器默认用 `rect`；只有 source 明确是圆角时才用 `roundRect`，并记录 `source_corner_radius_px` 或 `corner_reason`。
- 前景：图标、pictogram、logo-like mark、手绘标记、贴纸、徽章、复杂箭头、装饰元素默认用 `$imagegen` 重绘成独立资产。若源图里的小型视觉对象需要高度一致、无可读文字、且重绘会改变身份，可作为独立 source-derived raster asset 裁出并记录来源区域；这不是整页截图 fallback。
- 背景：纯色、简单渐变、规则网格、普通卡片可用原生或脚本重建；复杂照片、纹理、插画被前景遮挡时，用 `$imagegen` 做 inpainting/restoration。
- asset sheet：默认用稀疏 chroma-key asset sheet 减少生图次数。元素间距优先，不能拥挤、粘连、互相投影。
- provenance：每个最终 raster asset 都必须有来源记录。不能把原始 source crop 当成默认视觉资产。
- QA：确定性 validation 必要但不充分。必须检查 `preview.png` 和 `split_assets_contact.png`。
- repair：修最小失败范围。不要为了一个文本框或一个图标重建整页。
- 状态：`page_jobs.json`、`imagegen-jobs.json` 的关键状态必须由脚本推进。

## Acceptance Criteria

- 输出是有效 `.pptx`。
- 单图输出 1 页；多图每图 1 页；PDF 第 N 页对应输出第 N 页；PPT/PPTX 第 N 页对应输出第 N 页。
- PPT/PPTX speaker notes 按页原样复制，不翻译、不摘要、不交给 page worker 改写。
- 每页有 `manifest.json`、`page.pptx`、`preview.png`、`split_assets_contact.png`、`validation.json`、`page_result.json`。
- 每页 source image size、text inventory、object decisions、asset provenance、known limits 都有记录。
- 每个 page 都由 `record_page_dispatch.py` 记录 dispatch，并由 `record_page_result.py` 记录结果。
- 最终 deck 有 `final/<origin>_edited.pptx` 和 `final/validation.json`。
- 若出现 blocker，最终回复必须说明 blocker 阶段、证据路径和未完成原因；不能称为正常完成。

## Reference Map

- `references/architecture.md`：职责边界、run/page 目录结构、owner 原则。
- `references/state-machine.md`：run/page/imagegen 状态机和脚本推进规则。
- `references/subagent-contract.md`：page worker、repair worker 的提示词契约和返回格式。
- `references/imagegen-integration.md`：如何组合 `$imagegen`，包括 clean base、asset sheet、透明化和记录。
- `references/page-decision-tree.md`：页面分析、背景策略、前景/结构对象边界。
- `references/manifest-schema.md`：deck/page/imagegen JSON schema 第一版。
- `references/qa-rubric.md`：结构、文字、资产、背景、视觉 QA 标准。
- `references/repair-policy.md`：repair queue、最小返工范围和 blocker 判定。
- `references/script-contracts.md`：脚本职责、输入输出和允许调用者。
- `prompts/page-worker.md`：普通页面重建 worker prompt。
- `prompts/page-repair-worker.md`：页面修复 worker prompt。
- `prompts/imagegen-clean-base.md`：clean base 生成/编辑 prompt。
- `prompts/imagegen-asset-sheet.md`：稀疏 asset sheet prompt。
- `prompts/imagegen-repair.md`：targeted imagegen repair prompt。
