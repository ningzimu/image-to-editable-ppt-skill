# Workflow Contract

本文件定义主流程、角色边界、状态推进、repair 和 blocker。`editppt` 是唯一确定性状态推进入口；聊天里的“完成了”不算状态。

## 角色

### 主 agent

主 agent 负责 orchestration 和用户交互：

- 运行 `editppt prepare`。
- 判断是否需要 API fallback 或 custom backend；正常路径不需要额外运行 backend 配置。
- 单页输入时直接重建该页。
- 多页输入时先直接重建一个代表性 sample page，并等待用户确认。
- 用户确认 sample page 后运行 `editppt run sample`。
- 使用 `editppt run next` 决定下一步。
- 为 sample page 之外的页面生成 prompt、spawn page worker，并用 `editppt run dispatch` 记录 dispatch。
- 用 `editppt run record` 记录 page worker 返回结果。
- 必要时用 `editppt run repair` 写 repair item，再用同一个 page worker prompt 的 repair mode 重派。
- 用 `editppt run finalize` 组装和验证最终 PPTX。
- 向用户报告进度、最终路径、QA 结果和 blocker。

主 agent 不负责：

- 批量顺序重建 sample page 之外的多页页面。
- 修改 page worker 的 page-local 输出。
- 让不同 page worker 自行选择不同 image backend。
- 手写关键状态 JSON 跳过 `editppt`。

### Page worker

page worker 负责一个非 sample `pages/page_NNN/` 目录：

- 只读自己的 `page_request.json`、`source.png` 和相关 reference。
- 只写自己的 page dir。
- 使用 `page_request.json.image_backend`。
- 遵守 `page_request.json.user_requirements_and_feedback`。
- 分析文字、结构、背景和前景视觉对象。
- 按页面决策树选择 native text、native shape、clean base、asset sheet 或 source-derived asset。
- 使用 confirmed image backend 生成/编辑需要的 bitmap。
- 用 `editppt image import` / `editppt image process-sheet` / `editppt image crop` 记录和处理生成资产。
- 写 `manifest.json`、`page.pptx`、`preview.png`、`split_assets_contact.png`、`validation.json`、`page_result.json`。

page worker 不得编辑：

- `deck_manifest.json`
- `page_jobs.json`
- `notes_manifest.json`
- final PPTX
- input 原件
- 其他 page 目录
- 已确认 sample page

## 主流程

### Phase 1: Prepare

```bash
editppt prepare <input...>
```

产出：

- run dir
- `deck_manifest.json`
- `page_jobs.json`
- `notes_manifest.json`
- `pages/page_NNN/source.png`
- 每页 `page_request.json`
- 默认 `deck_manifest.json.image_backend`

agent 判断：

- 输入是否成功归一化。
- 是否需要 API fallback/custom backend override。
- 输入是单页还是多页。

只有需要 override 时才运行：

```bash
editppt run backend <run> --mode cli-api-fallback --model <model>
```

### Phase 2: Rebuild First Page

单页输入：

- 主 agent 直接重建该页。
- 不 spawn page worker。
- 不走 sample approval。

多页输入：

- 主 agent 选择代表性 sample page。
- 主 agent 直接重建 sample page。
- 给用户看 `page.pptx`、`preview.png`、`split_assets_contact.png`、`validation.json` 和关键 known limits。
- 用户确认后运行：

```bash
editppt run sample <run> --page <page_id>
```

### Phase 3: Dispatch Remaining Pages

主 agent 使用：

```bash
editppt run next <run>
```

如果 next 要求 dispatch：

1. 用 `editppt run prompt <run> --page <page_id> --out <prompt-file>` 生成 worker prompt。
2. spawn page worker。
3. spawn 成功后立刻运行 `editppt run dispatch <run> --page <page_id> --agent-id <id> --prompt-file <prompt-file>`。

`prompt` 和 `dispatch` 不能完全合并，因为 CLI 不能替 agent spawn worker，也拿不到真实 worker id。`editppt run status` 只用于 debug、排查并发槽位或人工检查；主流程优先 `editppt run next`。

### Phase 4: Record And Repair

worker 返回后：

```bash
editppt run record <run> --page <page_id> --agent-id <id>
```

如果 validation/QA 失败：

```bash
editppt run repair <run> --page <page_id> --reason <reason> --evidence <path>
```

然后重新生成 page worker prompt，并附带 repair item、失败证据和允许修改范围。repair 使用 `page-worker.md` 的 repair mode，不使用独立 repair prompt。

### Phase 5: Finalize

当 `editppt run next <run>` 返回 finalize 阶段：

```bash
editppt run finalize <run>
```

finalize 负责：

- 组装 final PPTX。
- 复制 notes。
- 运行 deck validation。
- 写 run summary。
- 标记 accepted/complete。

## 状态原则

Run/page 状态由 `editppt run` 命令推进。agent 不维护完整状态机，只根据文件事实和 `editppt run next` 继续执行。

必要状态：

- `pending`：`editppt prepare` 创建。
- `dispatched`：`editppt run dispatch` 记录真实已 spawn worker。
- `recorded`：`editppt run sample` 或 `editppt run record` 校验 required outputs 后写入。
- `repair_needed`：`editppt run repair` 写入具体失败证据。
- `accepted` / `complete`：`editppt run finalize` 写入。

不记录 `worker_returned`。worker 返回是聊天态，不是文件态。

## Image Job 记录

`imagegen-jobs.json` 是 page-local provenance/job record，不是完整聊天态状态机。

强制文件态只保留：

- `recorded`：`editppt image import` 已复制选中输出并写入 hash、metadata。
- `processed`：`editppt image process-sheet` 或 `editppt image crop` 已完成去底、切分或裁剪。
- `referenced`：`manifest.json` 已引用最终资产，validation 能找到 provenance。

`planned` 和 `generated` 可作为 agent 内部工作记录，但不要求 page worker 维护它们。

## Repair

repair 只修最小失败范围，不推倒重来。

repair item 至少包含：

- page id
- reason / failure type
- evidence path
- allowed scope
- previous attempt summary

常见 repair 范围：

1. 修改一个 text box。
2. 修改一个 coordinate 或 shape。
3. 重新切分一个 asset sheet。
4. 重新生成一个 asset sheet。
5. 重新生成一个 clean base。
6. 重派整页 page worker。

不要为了一个文本框或一个图标重建整页。

## Blocker

以下情况停止并报告 blocker：

- page worker/subagent 不可用。
- 必需 image backend 不可用。
- 输入无法归一化。
- 多次 repair 后仍没有可执行下一步。
- `editppt` 无法构建或验证有效 PPTX。
- final PPTX 无法打开。
- 必需视觉对象缺失且无法生成或裁剪。

blocker 必须报告：

- blocker 阶段
- reason
- evidence path
- 已完成文件
- 未完成文件

blocker 不是低保真完成结果。
