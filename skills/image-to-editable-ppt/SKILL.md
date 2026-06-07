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

- 单张图片输入由主 agent 直接重建，不分派 page worker，也不进入样张确认流程。
- 多页输入由主 agent 先直接完成一个代表性 sample page 的页面重建；用户确认后，该页直接作为最终结果，其余页面再分派给 page worker。
- 多页输入中，除 sample page 外的页面必须由 page worker/subagent 重建。没有可用 page worker/subagent 就停止，不进入其余页面重建。
- 所有生图、改图、背景修复、透明 bitmap 资产和 asset sheet 都必须使用 `deck_manifest.json.image_backend` 确认的 image backend。
- 优先使用当前环境可用的内置图片生成/编辑工具。仅当内置工具不可用、能力不足，或用户明确要求 API/CLI 时，使用 `editppt image ...`。
- 不创建一次性 SDK runner；API/CLI fallback 只走 `editppt image ...`。
- 不要只因为用户提到 `gpt-image-2`、分辨率、质量、透明资产或单页修复就要求配置第三方 API。只有确认需要 API/CLI fallback 时，才引导用户运行 `editppt config`。
- 第三方 API/OpenAI-compatible 中转站配置必须写入用户级 `~/.editppt/config.yaml`（Windows: `%USERPROFILE%\.editppt\config.yaml`），不要写入项目目录、run 目录或 skill 目录。
- 如果页面需要图片生成或编辑，但确认的 image backend 不可用，停止该页并报告 blocker，不伪造资产。
- 原始整页 `source.png` 加可编辑文本覆盖是失败模式，不是 fallback。
- 只有基础 primitive 和简单结构对象可以用原生 PPT shape。非文字视觉对象不确定时，默认用 confirmed image backend 重绘成独立资产。
- page worker 必须先做文字字号、视觉对象、背景策略和形状角形的清单校准，再写 manifest；不能靠审美猜测默认字号或默认圆角。
- 关键状态只能由 `editppt` 命令推进。agent 不能手写 JSON 把 page、imagegen job 或 run 标成完成。

## Required References

开始前读取：

- `references/workflow-contract.md`：主流程、角色、状态推进、repair 和 blocker。
- `references/cli-contracts.md`：`editppt` 命令职责和何时调用。
- `references/image-backend-integration.md`：如何选择和使用 image backend，包括 clean base、asset sheet、透明化和 prompt patterns。
- `references/page-decision-tree.md`：页面分析、背景策略、前景/结构对象边界。
- `references/manifest-schema.md`：deck/page/image job JSON schema 和 artifact contract。
- `references/qa-rubric.md`：结构、文字、资产、背景、视觉 QA 标准。

page worker 使用 `prompts/page-worker.md`。normal rebuild 和 repair 都使用同一个模板；repair 时附带 repair item、失败证据和允许修改范围。

## Workflow

### Phase 1: Prepare

运行：

```bash
editppt prepare <input...>
```

完成条件：

- run dir 已创建。
- `deck_manifest.json`、`page_jobs.json`、`notes_manifest.json` 已存在。
- 每页有 `pages/page_NNN/source.png` 和 `page_request.json`。
- `deck_manifest.json.image_backend` 已由 `editppt prepare` 写入默认 backend。

只有需要 API fallback 或 custom backend override 时，才运行 `editppt run backend`。

### Phase 2: Rebuild First Page

单页输入：

- 主 agent 直接重建该页。
- 不 spawn page worker。
- 不走 sample approval。

多页输入：

- 主 agent 选择代表性 sample page。
- 主 agent 直接重建 sample page。
- 向用户展示 `page.pptx`、`preview.png`、`split_assets_contact.png`、`validation.json` 和关键 known limits。
- 用户确认后运行 `editppt run sample <run> --page <page_id>`。

### Phase 3: Dispatch Remaining Pages

主 agent 使用：

```bash
editppt run next <run>
```

如果 next 要求 dispatch：

1. 运行 `editppt run prompt <run> --page <page_id> --out <prompt-file>`。
2. spawn page worker。
3. spawn 成功后立即运行 `editppt run dispatch <run> --page <page_id> --agent-id <id> --prompt-file <prompt-file>`。

`editppt run status` 只用于 debug、人工检查或排查并发槽位；正常主流程优先 `editppt run next`。

### Phase 4: Record And Repair

worker 返回后运行：

```bash
editppt run record <run> --page <page_id> --agent-id <id>
```

如果 validation/QA 失败，运行：

```bash
editppt run repair <run> --page <page_id> --reason <reason> --evidence <path>
```

然后重新生成 page-worker prompt，并附带 repair item、失败证据和允许修改范围。repair 不使用独立 prompt 文件。

### Phase 5: Finalize

当 `editppt run next <run>` 返回 finalize 阶段，运行：

```bash
editppt run finalize <run>
```

完成条件：

- `final/<origin>_edited.pptx` 已存在。
- `final/validation.json` 已存在。
- PPT/PPTX speaker notes 已按页原样复制。
- run summary 已写入。

## Page Output Contract

每页必须有：

- `manifest.json`
- `imagegen-jobs.json`
- `page.pptx`
- `preview.png`
- `split_assets_contact.png`
- `validation.json`
- `page_result.json`

`page_result.json` 必须指向当前 page dir 内的文件，并包含 qa note 和 known limits。

## Acceptance Criteria

- 输出是有效 `.pptx`。
- 单图输出 1 页；多图每图 1 页；PDF 第 N 页对应输出第 N 页；PPT/PPTX 第 N 页对应输出第 N 页。
- PPT/PPTX speaker notes 按页原样复制，不翻译、不摘要、不交给 page worker 改写。
- 每页 source image size、text inventory、object decisions、asset provenance、known limits 都有记录。
- 单张图片由主 agent 完成；多页输入中 sample page 由 `editppt run sample` 记录，其余页面由 `editppt run dispatch` 记录 dispatch，并由 `editppt run record` 记录结果。
- 最终 deck 有 `final/<origin>_edited.pptx` 和 `final/validation.json`。

## Blocker Reporting

若出现 blocker，最终回复必须说明：

- blocker 阶段。
- blocker reason。
- evidence path。
- 已完成文件。
- 未完成文件。

不能把 blocker 称为正常完成，也不能用低保真整页截图 fallback。
