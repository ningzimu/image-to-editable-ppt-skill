# Repair Policy

## 原则

修最小失败范围，不推倒重来。

repair item 必须包含：

- page id
- failure type
- evidence path
- suggested scope
- required output
- previous attempt summary

## 失败类型

- `missing_text`
- `clipped_text`
- `wrong_text_wrapping`
- `missing_asset`
- `bad_asset_split`
- `bad_clean_base`
- `bad_asset_provenance`
- `layout_drift`
- `broken_pptx`
- `notes_mismatch`
- `imagegen_blocked`

## 返工范围

优先顺序：

1. 修改一个 text box。
2. 修改一个 coordinate 或 shape。
3. 重新切分一个 asset sheet。
4. 重新生成一个 asset sheet。
5. 重新生成一个 clean base。
6. 重派整页 page worker。

不要为了一个文本框重建整页。

## Repair worker

repair worker 必须收到：

- repair item id
- 原 page dir
- 失败证据
- 允许修改范围
- 相关 preview/contact sheet
- 上一次 validation

repair worker 只能写当前 page dir。

## Blocker

以下情况停止并报告 blocker：

- 子 agent 不可用。
- 必需 `$imagegen` 不可用。
- 多次 repair 后仍没有可执行下一步。
- 输入格式无法归一化。
- 脚本无法构建有效 PPTX。

不设计低保真降级模式。blocker 不是低保真完成。
