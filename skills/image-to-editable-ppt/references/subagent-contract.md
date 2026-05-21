# Subagent 契约

## 基本原则

- 每个来源页面必须分派给一个 page subagent。
- 单页输入也必须分派给 page subagent。
- 主 agent 不做页面重建。
- page subagent 只写自己的 page 目录。
- page subagent 必须自己 build、preview、contact sheet、validate。
- 子 agent 不可用时停止，不顺序执行。

## Page worker 输入

page worker prompt 必须包含：

- run dir
- page id
- page dir
- source image 绝对路径
- allowed write scope
- forbidden paths
- required outputs
- 必读 references
- 必读 `$imagegen/SKILL.md`
- 返回格式

## Page worker 禁止事项

page worker 不得：

- 编辑 `deck_manifest.json`
- 编辑 `page_jobs.json`
- 编辑 `notes_manifest.json`
- 编辑其他 page 目录
- 编辑 final PPTX
- 用本地绘图代码替代 `$imagegen`
- 手写 `imagegen-jobs.json` 完成状态
- 把 source crop 当成默认视觉资产

## Page worker 输出

page worker 必须在 page dir 内产出：

```text
manifest.json
imagegen-jobs.json
page.pptx
preview.png
split_assets_contact.png
validation.json
page_result.json
```

`page_result.json` 必须是 JSON，至少包含：

```json
{
  "page_manifest": "manifest.json",
  "imagegen_jobs": "imagegen-jobs.json",
  "page_pptx": "page.pptx",
  "preview": "preview.png",
  "contact_sheet": "split_assets_contact.png",
  "validation": "validation.json",
  "page_result": "page_result.json",
  "qa_note": "one sentence",
  "known_limits": []
}
```

返回格式：

```text
page_manifest=/absolute/path/to/pages/page_001/manifest.json
page_pptx=/absolute/path/to/pages/page_001/page.pptx
preview=/absolute/path/to/pages/page_001/preview.png
contact_sheet=/absolute/path/to/pages/page_001/split_assets_contact.png
validation=/absolute/path/to/pages/page_001/validation.json
page_result=/absolute/path/to/pages/page_001/page_result.json
qa_note=<one sentence>
known_limits=<none or short list>
```

## Repair worker

repair worker 与 page worker 边界相同，但必须额外收到：

- repair item id
- 失败类型
- 证据路径
- 允许修改的最小范围
- 上一次 `preview.png`
- 上一次 `split_assets_contact.png`
- 上一次 `validation.json`

repair worker 不应重建整页，除非 repair item 明确说明整页 manifest 不可用。

## Dispatch 记录

主 agent spawn worker 后，必须运行 `record_page_dispatch.py`。脚本记录：

- page id
- agent id / nickname，如果 runtime 提供
- dispatch prompt path
- dispatch prompt sha256
- page_request sha256
- dispatched_at
- repair item id，如果是 repair dispatch

没有 dispatch 记录的 page result，`record_page_result.py` 应拒绝。
