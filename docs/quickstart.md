# 快速开始

## 适合谁

这页给第一次使用 Image to Editable PPT 的人看。你只需要准备一张或多张幻灯片图片、一份 PDF，或一个图片版 `.pptx`，然后让 agent 使用 `image-to-editable-ppt` skill 把它转成可编辑 PowerPoint。

## 开始前请确认

- **额度**：转换很费 token。推荐 ChatGPT Pro 用户使用；Plus 用户请谨慎，复原一个 10 页 PPT 有可能消耗完 5 小时额度。第一次建议先拿 1 页试水。
- **权限**：建议在 Codex 中使用「完全访问权限」执行，否则流程会被审批请求频繁打断，参见[安装与配置](installation.md)。
- **OCR Token（推荐）**：申请一个免费的百度 AI Studio Access Token 可以显著提升文字还原质量。首次使用时 AI 会主动询问你一次，把 Token 发给它即可，参见[安装与配置](installation.md)。

## 最短使用方式

先安装 skill，参见[安装与配置](installation.md)。然后在 Codex 里直接使用（图片、PDF 和 `.pptx` 可以直接粘贴或附加到对话框，也可以提供本地路径）：

```text
$image-to-editable-ppt 把这张图片转成可编辑 PPT。
```

多页输入同理：

```text
$image-to-editable-ppt 把 <path-to-deck.pdf> 转成可编辑 PPT。
```

在其他支持显式选择 skill 的 agent 里，用对应语法选中 `image-to-editable-ppt` 即可。

## 第一次使用建议

- 先用单张图片跑一次完整流程，确认效果和耗时符合预期，再上多页任务。
- 转换开始前 AI 询问 OCR Token 时，建议花一分钟申请并提供——不配置也能运行，但文字还原质量会打折扣。
- 转换期间尽量保持在电脑旁：如果没有使用完全访问权限，部分步骤可能需要你手动审批。
- 拿到结果后，用 PowerPoint 打开检查文字、形状和图片资产是否可以分开编辑；对照 `final/validation.json` 查看校验结果。

## 转换结果

任务完成后，会在独立输出目录 `output/image-to-editable-ppt/{job-id}/` 下得到：

- `final/{origin}_edited.pptx`：最终可编辑 PowerPoint 文件
- `final/validation.json`：最终 deck 校验结果
- `final/run_summary.json`：本次转换摘要
- `pages/page_NNN/`：每页的重建工作区（源图、预览图、资产等中间产物）

完整目录结构说明参见[标准工作流](workflow.md)。
