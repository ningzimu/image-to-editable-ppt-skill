# Script Contracts 第一版

脚本只做确定性工作，不手工绘制复杂视觉资产。

## `image_to_editable_ppt_runtime.py`

职责：

- 创建 skill-local `.venv`。
- 安装依赖。
- doctor 检查。
- 输出 venv python。

## `prepare_deck_run.py`

职责：

- 归一化图片、PDF、图片版 PPT/PPTX。
- 创建 run 目录。
- 复制输入到 `input/`。
- 生成 `deck_manifest.json`。
- 生成 `page_jobs.json`。
- 为每页生成 `page_request.json` 和 `source.png`。
- 提取 `notes_manifest.json`。

不做页面理解或 imagegen 决策。

## `page_job_status.py`

职责：

- 只读 `page_jobs.json`。
- 输出 pending、dispatched、recorded、repair_needed、blocked pages。
- 输出 `max_concurrent_pages`、`active_dispatches`、`dispatch_slots_available`、`dispatchable_pages`，供主 agent 分批 spawn。
- 不修改状态。

## `record_page_dispatch.py`

职责：

- page spawn 后记录 dispatch。
- 推进 `pending -> dispatched` 或 `repair_needed -> repair_dispatched`。
- 写 dispatch prompt hash、page_request hash、agent id/nickname。
- 不负责 spawn，也不作为真实并发 scheduler；并发批次由主 agent 根据 `page_job_status.py` 控制。

## `record_page_result.py`

职责：

- 校验 page worker 返回路径。
- 校验 required outputs 存在且在 page dir 内。
- 记录 hash、完成时间、known limits。
- 推进 `dispatched -> recorded` 或 `repair_dispatched -> recorded`。

## `record_imagegen_result.py`

职责：

- 复制 `$imagegen` 选中输出到 page 目录。
- 写 source path、output path、hash、metadata。
- 推进 imagegen job 到 `recorded`。

## `process_asset_sheet.py`

职责：

- 调用 `$imagegen` chroma-key helper。
- 调用 splitter/cropper。
- 统一处理 asset sheet 自动切分和手动 crop。
- 校验 alpha 和组件。
- 推进 imagegen job 到 `processed`。
- source-derived 小图标裁剪也应走这个脚本，使用 `--crop-source source.png --source-type source-derived-rasterization --crop-padding` 和必要的 `--crop-remove-border-bg`，避免 page worker 手写临时裁剪逻辑。

## `build_pptx_from_manifest.py`

职责：

- 从 page manifest 构建 page-level PPTX。
- 从 deck manifest 构建 final PPTX。
- 生成 preview。

preview 只用于 QA，不是 PowerPoint/WPS 的精确排版引擎。它必须按 point-to-pixel 换算近似渲染文字，暴露字号过大、溢出和错位风险；page worker 不能把 preview 当成最终排版完全一致的证明。

`roundRect` 必须把 manifest 中的 `source_corner_radius_px`/`radius` 写入 OOXML adjustment，不能让 PowerPoint 使用默认圆角比例。

## `validate_pptx.py`

职责：

- 验证 page/deck PPTX。
- 检查 relationship、media hash、text inventory、notes hash、full-slide raster 违规。

## `make_page_contact_sheet.py`

职责：

- 生成 origin/preview side-by-side QA 图。

## `queue_page_repairs.py`

职责：

- 根据 validation 和 QA notes 写 `repair_queue.json`。
- 推进 page 到 `repair_needed`。

## `finalize_deck_run.py`

职责：

- 确认所有 page accepted。
- 组装 final PPTX。
- 复制 notes。
- 运行 deck validation。
- 生成 `run_summary.json`。
- 推进 run 到 complete。
