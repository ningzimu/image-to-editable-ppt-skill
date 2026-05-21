# 状态机

关键状态只能由脚本推进。聊天里的“完成了”不算状态。

## Run-level 状态

```text
created
-> inputs_prepared
-> pages_dispatched
-> pages_recorded
-> deck_built
-> deck_validated
-> complete
```

状态 owner：

- `created` / `inputs_prepared`：`prepare_deck_run.py`
- `pages_dispatched`：所有页面都由 `record_page_dispatch.py` 记录后确认。
- `pages_recorded`：所有页面都由 `record_page_result.py` 记录后确认。
- `deck_built`：`finalize_deck_run.py`
- `deck_validated`：`finalize_deck_run.py`
- `complete`：`finalize_deck_run.py`

## Page-level 状态

正常路径：

```text
pending
-> dispatched
-> recorded
-> accepted
```

repair 路径：

```text
recorded
-> repair_needed
-> repair_dispatched
-> recorded
-> accepted
```

blocker 路径：

```text
pending|dispatched|recorded|repair_needed
-> blocked
```

状态 owner：

- `pending`：`prepare_deck_run.py`
- `dispatched`：`record_page_dispatch.py`
- `recorded`：`record_page_result.py`
- `repair_needed`：`queue_page_repairs.py`
- `repair_dispatched`：`record_page_dispatch.py`，必须带 repair item id。
- `accepted`：`finalize_deck_run.py`
- `blocked`：发现 blocker 的脚本写入，必须带 reason 和 evidence path。

不记录 `worker_returned` 状态。worker 返回是聊天态，不是文件态。只有 `record_page_result.py` 成功后，page 才算 `recorded`。

## 并发兼容

运行时可能限制同时存在的 subagent 数量。本 skill 不在脚本层实现 scheduler；主 agent 负责按批次 spawn。

`prepare_deck_run.py` 写入 `max_concurrent_pages`，默认值为 4。`page_job_status.py` 只读输出：

- `max_concurrent_pages`
- `active_dispatches`
- `dispatch_slots_available`
- `dispatchable_pages`

主 agent 每轮最多 spawn `dispatch_slots_available` 个 page worker。worker 返回并由 `record_page_result.py` 记录后，再运行 `page_job_status.py` 开下一批。

`record_page_dispatch.py` 只记录已经 spawn 的 worker，不假装控制真实并发。

## Imagegen job 状态

page-local `imagegen-jobs.json` 使用脚本推进：

```text
planned
-> generated
-> recorded
-> processed
-> referenced
```

含义：

- `planned`：记录 prompt、输入图片角色、预期输出路径。
- `generated`：page worker 已通过 `$imagegen` 得到候选输出，但尚未复制到 page 目录。
- `recorded`：`record_imagegen_result.py` 已复制选中输出并写入 hash、metadata。
- `processed`：`process_asset_sheet.py` 已完成去底、切分或裁剪。
- `referenced`：`manifest.json` 已引用最终资产，validation 能找到 provenance。

page worker 不能手写 `imagegen-jobs.json` 把 job 标成完成。

## blocker 与 repair_needed

`repair_needed` 表示有具体失败证据，并且存在明确的最小返工范围。

`blocked` 表示无法继续正常流程，例如：

- 子 agent 不可用。
- 必需的 `$imagegen` 不可用。
- 输入无法归一化。
- repair 多次失败且没有可执行下一步。

`blocked` 是停止信号，不是低保真完成结果。
