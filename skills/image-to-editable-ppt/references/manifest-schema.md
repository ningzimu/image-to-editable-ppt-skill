# Manifest Schema 第一版

本文件描述 JSON 文件职责和 owner。字段会随 `editppt` runtime 实现细化。

## `deck_manifest.json`

Owner：`editppt prepare` 创建，`editppt run finalize` 读取。

用途：

- 输入类型。
- page 顺序。
- page manifest 路径。
- notes manifest 路径。
- final output 路径。
- run-level image backend contract。
- 用户原始要求和 sample page 反馈。

关键字段：

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "input_type": "image|images|pdf|pptx",
  "max_concurrent_pages": 4,
  "image_backend": {},
  "user_requirements_and_feedback": [],
  "pages": [],
  "notes_manifest": "notes_manifest.json",
  "output": "final/origin_edited.pptx"
}
```

`image_backend` 由 `editppt prepare` 写入默认值，必要时由 `editppt run backend` 覆盖。`user_requirements_and_feedback` 由 `editppt run sample` 追加简短字符串，只记录用户要求、用户对 sample page 的反馈，以及用户确认后的明确调整。

## `page_jobs.json`

Owner：`editppt run` 命令写入。

用途：

- page 状态 source of truth。
- dispatch 记录。
- result 记录。
- repair 和 blocker 记录。

草案：

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "max_concurrent_pages": 4,
  "pages": [
    {
      "page_id": "page_001",
      "status": "pending",
      "page_dir": "pages/page_001",
      "page_request": "pages/page_001/page_request.json",
      "source": "pages/page_001/source.png",
      "sample_page_approved": false,
      "dispatch": null,
      "result": null,
      "repair": [],
      "blocker": null
    }
  ]
}
```

`sample_page_approved` 由 `editppt run sample` 写。`dispatch` 由 `editppt run dispatch` 写。`result` 由 `editppt run sample` 或 `editppt run record` 写。`repair` 由 `editppt run repair` 写。`accepted` 由 `editppt run finalize` 写。

## `page_request.json`

Owner：`editppt prepare`。

用途：给 page worker 的任务边界。

包括：

- page id
- page dir
- source image
- slide size
- max concurrent pages
- allowed write scope
- required outputs
- user constraints
- image backend contract
- user requirements and feedback

不得包含：

- page type 预判。
- imagegen_required 预判。
- object-level 决策。

sample page 确认后，剩余页面的 `page_request.json` 必须包含 `user_requirements_and_feedback`。如果本 run 使用 image backend，`page_request.json` 也必须包含同一份 `image_backend`。

## `page_result.json`

Owner：page worker 创建，`editppt run record` 校验。

包括：

- manifest path
- page pptx path
- preview path
- contact sheet path
- validation path
- qa note
- known limits
- page-local output hashes，可由 `editppt run record` 补充

## `pages/page_NNN/manifest.json`

Owner：page worker。

用途：page-level PPTX 构建 source of truth。

必须包含：

- `slide`
- `source`
- `text_inventory`
- `visual_inventory`
- `background_strategy`
- `quality_checks`
- `text_boxes`
- `shapes`
- `images`
- `asset_provenance`
- page strategy / known limits

`quality_checks` 至少包含：

```json
{
  "font_size_calibrated": true,
  "visual_inventory_matched": true,
  "background_strategy_checked": true,
  "shape_corner_geometry_checked": true
}
```

`background_strategy` 至少说明：

- mode：`native-or-script`、`source-preserving-local-repair`、`imagegen-full-clean-base` 等。
- source consistency：保留哪些构图、透视、物体、颜色、光照和细节。
- removed foreground：哪些前景会被移除并重建。
- comparison note：preview 对照 source 后的背景一致性结论。

`roundRect` shape 必须记录 `source_corner_radius_px`，可以额外记录 `corner_reason`。原图是直角矩形时必须使用 `rect`。

推荐记录：

```json
{
  "type": "roundRect",
  "box_px": [64, 169, 472, 187],
  "source_corner_radius_px": 12,
  "corner_category": "small-radius",
  "corner_reason": "source card corners are lightly rounded"
}
```

`corner_category` 可选值：`straight`、`small-radius`、`large-radius`、`pill`。`straight` 不应使用 `roundRect`。

`source-derived-rasterization` 资产必须记录：

```json
{
  "path": "assets/example.png",
  "source": "source.png",
  "source_type": "source-derived-rasterization",
  "source_region_px": [100, 200, 60, 60],
  "require_edge_safe_alpha": true,
  "provenance_note": "Small non-text icon cropped to preserve source identity."
}
```

`source_region_px` 使用 `[x, y, width, height]`。如果使用 `[left, top, right, bottom]`，字段名必须写成 `source_bbox_px`。

`require_edge_safe_alpha` 是可选严格校验：仅当该资产应完整落在透明画布内时设置为 `true`；默认不因为可见像素贴边直接判失败。

它只允许用于无可读文字的小型独立视觉对象，不能用于整页、整卡片、整图表或文字区域。

## `pages/page_NNN/imagegen-jobs.json`

Owner：`editppt image` 命令。

用途：记录 clean base、asset sheet、repair asset 的生成和处理过程。

状态和 provenance 记录规则见 `workflow-contract.md`。

## `notes_manifest.json`

Owner：`editppt prepare` 创建，`editppt run finalize` 读取。

用途：

- PPT/PPTX speaker notes 原文。
- notes hash。
- page 映射。

notes 不交给 page worker，不翻译、不摘要、不改写。
