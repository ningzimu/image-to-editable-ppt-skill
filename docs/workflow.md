# 标准工作流

这页描述一次转换从输入到最终 `.pptx` 的完整过程，帮助你理解 AI 在做什么、每个阶段的产物是什么。

## 整体流程

1. **创建任务目录并归一化输入**：创建独立任务目录，把输入（图片/PDF/图片版 PPT）归一化为 `pages/page_NNN/source.png`，同时检测内置 `image_gen.imagegen` 是否可用并记录本次运行选择的图片 backend。
2. **OCR 文字标注（如已配置 Token）**：把整个输入作为一个批量任务提交 OCR，为每页生成文字标注（框坐标、实测字号、字号分组、文字内容），供重建时按测量值还原文字。
3. **页面分派**：如果只有 1 页，主 agent 用 `editppt run dispatch --local` 认领页面并本地重建；如果有多页，按 `max_concurrent_pages` 分批分派给 page worker 并行重建。
4. **逐页重建与自检**：页面重建者负责自己的页面目录，完成页面重建、对照源图自检和 page-local 修正，可能进行多轮迭代。每页创建 manifest，重建可编辑文本、简单形状和图片资产；需要时通过 image backend 做前背景分离和素材抽取。
5. **状态记录**：用 `editppt` 命令记录 dispatch、page result 和 accepted 状态，任务进度随时可查。
6. **最终组装与校验**：主 agent 用 `editppt run finalize` 按页顺序读取已记录的 `manifest.json` 重建最终 `.pptx`，复制 `.pptx` 页面备注，并运行 deck validation。

## 输入与输出对应

输出始终是 PowerPoint `.pptx`：

| 输入 | 输出 |
| --- | --- |
| 1 张图片 | 1 页 `.pptx` |
| 多张图片 | 多页 `.pptx`，每张图片 1 页，按提供顺序排列 |
| 多页 PDF | 多页 `.pptx`，PDF 第 N 页对应输出第 N 页 |
| 图片版 PPT | 页数一致的 `.pptx`，原第 N 页对应输出第 N 页 |

只有 `.pptx` 输入会处理页面备注。备注由主 agent 按页原样复制到输出：不翻译、不摘要、不改写，也不交给 page worker 处理。

## 输出目录结构

每次转换使用一个独立输出目录，所有中间文件和最终结果都保存在其中：

```text
output/image-to-editable-ppt/{job-id}/        # 单次转换任务目录
├── input/                                    # 原始输入文件副本
├── deck_manifest.json                        # 整个 deck 的页面清单和输出配置
├── page_jobs.json                            # 每页分派和完成状态
├── run_state.json                            # 当前任务的整体运行状态
├── notes_manifest.json                       # PPTX 页面备注提取与映射记录
├── final/                                    # 最终输出目录
│   ├── {origin}_edited.pptx                  # 最终可编辑 PPTX
│   ├── validation.json                       # 最终 deck 校验结果
│   └── run_summary.json                      # 本次转换摘要
└── pages/                                    # 按页拆分的重建工作区
    ├── page_001/                             # 第 1 页工作目录
    │   ├── source.png                        # 归一化后的页面源图
    │   ├── page_request.json                 # 页面请求和 image backend
    │   ├── worker-prompt.md                  # 生成给页面重建者的提示词
    │   ├── imagegen-jobs.json                # 本页图片生成/编辑调用和结果记录
    │   ├── assets/                           # 本页拆出的独立图片资产
    │   ├── page.pptx                         # 本页单页 PPTX
    │   ├── preview.png                       # 本页重建预览图
    │   ├── split_assets_contact.png          # 本页资产切分检查图
    │   ├── manifest.json                     # 本页文本、形状和资产描述
    │   ├── validation.json                   # 本页校验结果
    │   └── page_result.json                  # 本页产物索引
    └── page_002/                             # 后续页面工作目录
        └── ...
```

## 能力边界

- 这个 skill 面向输入页面的可编辑重建，不是从零生成整套 PPT 内容——那是 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill) 的职责。
- 对照片、插画、纹理、手绘装饰等复杂视觉元素，通常只能作为独立图片资产移动，不能保证内部对象可编辑。
- 对表格、图表、流程图等结构化区域，会优先保留可编辑语义，但低置信度时保留为资产并在验证报告里说明。
- 部分图片元素和文字位置可能会有轻微偏移，不能保证 100% 复刻原始页面。
- 如果约定的图片生成/编辑路径无法产出合规资产，对应页面会失败或保持阻塞；skill 不会把缺失资产降级为 warning，也不会 record、finalize 或交付不完整的替代结果。
- 视觉相似不等于可编辑。最终判断应同时看 PPTX 结构、文本覆盖、资产来源和预览/diff。
