# 示例提示词

以下提示词以 Codex 的 `$` 语法为例；在其他 agent 里改用对应的 skill 选择语法即可。图片、PDF 和 `.pptx` 可以直接粘贴或附加到对话框，也可以提供本地路径。

## 单张图片转可编辑 PPT

```text
$image-to-editable-ppt 把这张图片转成可编辑 PPT。
```

## 多张图片转成一个 PPT

```text
$image-to-editable-ppt 把这些图片转成一个可编辑 PPT，按我提供的顺序排列页面。
```

## PDF 转可编辑 PPT

```text
$image-to-editable-ppt 把 <path-to-deck.pdf> 转成可编辑 PPT。
```

## 图片版 PPT 转可编辑 PPT

```text
$image-to-editable-ppt 把 <path-to-image-based.pptx> 转成可编辑 PPT，保留每页的演讲者备注。
```

## 配置 OCR Token

```text
这是我申请的百度 AI Studio Access Token：<token>。请帮我配置到 editppt，用于文字校正。
```

## 配置第三方图片 API fallback

```text
我需要配置第三方生图 API。base URL 是 <https://xxx/v1>，模型名是 <model-name>，API key 是 <key>。请帮我写入 editppt 的用户级配置。
```

## 检查转换质量

```text
对比每页源图和转换后的页面，检查有没有缺字、错位或资产缺失，并汇总校验结果。
```

## 继续未完成的任务

```text
刚才的转换中断了。请检查 output/image-to-editable-ppt/ 下最近任务的运行状态，继续完成未处理的页面。
```
