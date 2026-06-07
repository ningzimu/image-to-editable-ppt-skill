# CLI Contracts

`editppt` 是唯一面向 agent 的命令入口。runtime 模块只做确定性工作，不手工绘制复杂视觉资产。

## `editppt setup` / `editppt doctor` / `editppt config`

职责：

- `setup` 只初始化和检查本机 CLI 环境，不安装 skill，不调用 `npx`。
- `doctor` 检查当前 `editppt` CLI Python 依赖和 API fallback 配置。
- `config` 写入或读取用户级配置 `~/.editppt/config.yaml`。
- `config` 可复用兼容的 `codex-ppt` runtime 配置。
- 不创建二级 venv；Python 依赖由 `pipx install` 根据 `pyproject.toml` 安装。

## `editppt install` / `editppt uninstall` / `editppt update`

职责：

- 通过 `npx -y skills@latest` 安装、卸载或更新 skill。
- `--agent` 直接透传给 `skills` CLI，不维护 agent 白名单。
- 支持 `--dry-run` 打印外部命令。
- `update` 同时支持 CLI 更新和 skill 更新。

## `editppt`

职责：

- 作为面向 agent 的统一 CLI 入口。
- 顶层只暴露 `setup`、`install`、`uninstall`、`update`、`doctor`、`config`、`prepare`、`run`、`image`。
- 用 `run` 子命令包装 backend 配置、状态查看、下一步建议、prompt 生成、dispatch 记录、结果记录、样张记录和 finalization。
- 用 `image` 子命令包装第三方 API 生图/改图、图片导入、asset sheet 处理和裁剪。
- `prepare` 默认把 image backend 配置为 Codex 内置 `image_gen` / `image_gen.imagegen`。
- 保留内部 runtime 模块作为确定性实现，避免 agent 记忆和拼接多套入口。
- 不做页面理解、图片分层、复杂视觉资产生成或手工修复。

## `editppt prepare`

职责：

- 归一化图片、PDF、图片版 PPT/PPTX。
- 创建 run 目录。
- 复制输入到 `input/`。
- 生成 `deck_manifest.json`。
- 生成 `page_jobs.json`。
- 为每页生成 `page_request.json` 和 `source.png`。
- 提取 `notes_manifest.json`。
- 写入默认 built-in image backend contract。

不做页面理解或 image backend 决策。

## `editppt run backend`

职责：

- 写入 `deck_manifest.json.image_backend`。
- 把同一 backend contract 写入每个 `page_request.json`。
- 默认记录 Codex 内置 `image_gen` / `image_gen.imagegen`，不要求 `OPENAI_API_KEY`。
- 仅在用户明确要求 API/CLI，或内置工具不可用时，记录 `cli-api-fallback`。
- 不直接调用 Codex 内置生图工具；真实可用性由 agent 的 tool manifest 或最小 probe 确认。

## `editppt run sample`

职责：

- 校验主 agent 完成的 sample page required outputs。
- 记录 sample page hash、validation 和 result。
- 推进 sample page 到 `recorded`，并写入 `sample_page_approved: true`。
- 把用户要求和反馈追加到 `deck_manifest.json.user_requirements_and_feedback`。
- 把用户要求、反馈和 backend contract 回写到剩余 `page_request.json`。

## `editppt run next`

职责：

- 读取 run/page 状态并输出下一步建议。
- 在正常主流程中作为主 agent 的下一步入口。
- 返回需要 dispatch、wait/repair 或 finalize 的阶段信息。
- 不修改状态。

## `editppt run status`

职责：

- 只读 `page_jobs.json`。
- 输出 pending、dispatched、recorded、repair_needed、blocked pages。
- 输出 `max_concurrent_pages`、`active_dispatches`、`dispatch_slots_available`、`dispatchable_pages`，用于 debug、人工检查或排查并发槽位。
- 不修改状态。

## `editppt run dispatch`

职责：

- page spawn 后记录 dispatch。
- 推进 `pending -> dispatched` 或 `repair_needed -> repair_dispatched`。
- 写 dispatch prompt hash、page_request hash、agent id/nickname。
- 不负责 spawn，也不作为真实并发 scheduler；并发批次由主 agent 根据 `editppt run next` 和实际 worker 返回情况控制。

## `editppt run record`

职责：

- 校验 page worker 返回路径。
- 校验 required outputs 存在且在 page dir 内。
- 记录 hash、完成时间、known limits。
- 推进 `dispatched -> recorded` 或 `repair_dispatched -> recorded`。

## `editppt image generate` / `editppt image edit` / `editppt image batch`

职责：

- 使用 `~/.editppt/config.yaml` 和环境变量调用第三方 OpenAI-compatible 图片 API。
- 支持生图、改图和 JSONL 批量生图。
- 需要 page-run 记录时，必须把输出落到 page 目录并记录 image job。
- 不替代 agent 的视觉判断和 prompt 策略。

## `editppt image import`

职责：

- 复制 confirmed image backend 的选中输出到 page 目录。
- 写 source path、output path、hash、metadata。
- 推进 image job 到 `recorded`。

## `editppt image process-sheet`

职责：

- 运行内置 chroma-key 处理。
- 调用 splitter/cropper。
- 统一处理 asset sheet 自动切分和手动 crop。
- 校验 alpha 和组件。
- 推进 image job 到 `processed`。
- source-derived 小图标裁剪优先走 `editppt image crop`，避免 page worker 手写临时裁剪逻辑。

## `editppt image crop`

职责：

- 从 source 或 generated image 中裁剪局部资产。
- 可选去除边缘背景。
- 写入 manifest provenance。

## 内部 PPTX builder

职责：

- 从 page manifest 构建 page-level PPTX。
- 从 deck manifest 构建 final PPTX。
- 生成 preview。

preview 只用于 QA，不是 PowerPoint/WPS 的精确排版引擎。它必须按 point-to-pixel 换算近似渲染文字，暴露字号过大、溢出和错位风险；page worker 不能把 preview 当成最终排版完全一致的证明。

`roundRect` 必须把 manifest 中的 `source_corner_radius_px`/`radius` 写入 OOXML adjustment，不能让 PowerPoint 使用默认圆角比例。

## 内部 validator

职责：

- 验证 page/deck PPTX。
- 检查 relationship、media hash、text inventory、notes hash、full-slide raster 违规。

## 内部 contact sheet helper

职责：

- 生成 origin/preview side-by-side QA 图。

## `editppt run repair`

职责：

- 根据 validation 和 QA notes 写 `repair_queue.json`。
- 推进 page 到 `repair_needed`。

## `editppt run finalize`

职责：

- 确认所有 page accepted。
- 组装 final PPTX。
- 复制 notes。
- 运行 deck validation。
- 生成 `run_summary.json`。
- 推进 run 到 complete。
