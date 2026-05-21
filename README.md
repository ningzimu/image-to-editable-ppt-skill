# Image to Editable PPT Skill

[![English](https://img.shields.io/badge/docs-English-blue)](README_en.md) [![GitHub stars](https://img.shields.io/github/stars/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=stars)](https://github.com/ningzimu/image-to-editable-ppt-skill/stargazers) [![GitHub forks](https://img.shields.io/github/forks/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=forks)](https://github.com/ningzimu/image-to-editable-ppt-skill/forks)

![Image to Editable PPT 项目概览](assets/image-to-editable-ppt-overview.png)

一个面向 Codex 的图片、PDF、图片版 `.pptx` 转可编辑 PowerPoint 的 skill。它先把输入归一化为逐页任务，再由 page subagent 重建为 `.pptx`：可读文字尽量恢复为原生文本框，简单几何尽量恢复为 PowerPoint 形状，复杂视觉元素保留为带来源记录的独立图片资产。

它适合把截图式或图片式幻灯片变成更容易二次编辑的 PPT，让文字、简单形状和视觉素材尽量分开调整。

> [!TIP]
> 本 skill 不负责从文章、报告、大纲或想法直接生成全新 PPT。如果你要做的是“生成一份 PPT”，可以使用 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill)。

## 转换效果示例

<table>
  <tr>
    <th>原图</th>
    <th>转换后可编辑效果</th>
  </tr>
  <tr>
    <td><img src="assets/showcase-origin-market-snapshot.png" alt="市场概览原图" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-market-snapshot.png" alt="市场概览转换后可编辑效果" width="420"></td>
  </tr>
  <tr>
    <td><img src="assets/showcase-origin-status-report.png" alt="项目进展汇报原图" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-status-report.png" alt="项目进展汇报转换后可编辑效果" width="420"></td>
  </tr>
</table>

## 特点

- 适用场景广泛，支持多种输入：单张图片、多张图片、多页 PDF、图片版 `.pptx` 到可编辑 `.pptx`。
- 采用多 agent 架构：Codex sub agent 并行重建每一个页面，加快多页任务的重建速度；主 agent 负责分派、质量检查、修复调度和最终组装。
- 全面复用 Codex 现有特性，包括 sub agent 和 `$imagegen`；采用纯视觉重建方案，无需第三方 OCR 或版面分析服务依赖。
- 多张图片按提供顺序生成页面；PDF 和 `.pptx` 保留原页码顺序。
- `.pptx` 输入的页面备注会复制到输出对应页，备注内容不改动。
- 根据具体页面情况决定是否通过 `$imagegen` / gpt-image-2 做图片分层抽取；需要时用稀疏 asset sheet 合并前景素材，尽可能降低 gpt-image-2 调用次数。
- 支持复杂视觉页的混合策略：可编辑文字 + 简单形状 + 独立图片资产。

## 输入与输出契约

输出始终是 PowerPoint `.pptx`：

| 输入             | 输出                                           |
| ---------------- | ---------------------------------------------- |
| 1 张图片         | 1 页 `.pptx`                                 |
| 多张图片         | 多页 `.pptx`，每张图片 1 页，按提供顺序排列  |
| 多页 PDF         | 多页 `.pptx`，PDF 第 N 页对应输出第 N 页     |
| 图片版 `.pptx` | 页数一致的 `.pptx`，原第 N 页对应输出第 N 页 |

只有 `.pptx` 输入会处理页面备注。备注由主 agent 按页原样复制到输出 PPTX：不翻译、不摘要、不改写，也不交给 page subagent 处理。

## 适用场景

- 把一张或多张 slide 图片重建成可调整文字和元素位置的 PPT。
- 把多张图片或多页 PDF 转成一个多页 `.pptx`。
- 把图片式 `.pptx` 页面转换为更容易二次编辑的 `.pptx`，并保留原页面备注。
- 复刻单页视觉设计，同时保留文本可编辑性。
- 对比源图与输出页面，定位缺字、错位或资产缺失。

## 运行要求

- Codex 需要能分派 page subagent；如果不能创建 page subagent，skill 会停止并报告 blocker。
- 复杂背景修复、图标重绘、透明 asset sheet 和局部修复依赖 `$imagegen` / built-in `image_gen`。

## 已知限制

- 本 skill 针对 Codex 进行深度适配，目前不支持其他 agent。
- 本 skill 在 Codex 的会员体系（Plus / Max）下测试正常，第三方 API 接入方式的兼容性未测试。
- 受限于模型基础理解能力和对 skill 的遵循能力，不保证 gpt-5.5 以下模型的使用效果。
- 部分图片元素和文字位置可能会有轻微偏移，不能保证 100% 复刻原始页面。

## 安装

推荐使用 `skills` CLI 安装到 Codex 的全局 skills 目录：

```bash
npx -y skills@latest add ningzimu/image-to-editable-ppt-skill \
  --skill image-to-editable-ppt \
  --agent codex \
  --global
```

也可以直接在 Codex 对话里输入：

```text
$skill-installer https://github.com/ningzimu/image-to-editable-ppt-skill
```

也可以从 GitHub Releases 下载 `image-to-editable-ppt-skill-v*.zip`，解压后把其中的 `image-to-editable-ppt` 文件夹放到 `~/.codex/skills/image-to-editable-ppt`。

安装完成后，重启 Codex 让新 skill 生效。

## 使用方式

在 Codex 里可以用 `$image-to-editable-ppt` 显式选中这个技能。图片、PDF 和 `.pptx` 可以直接粘贴或附加到对话框，也可以提供本地路径：

```text
$image-to-editable-ppt 把这张图片转成可编辑 PPT。
$image-to-editable-ppt 把这些图片转成一个可编辑 PPT。
$image-to-editable-ppt 把 /path/to/deck.pdf 转成可编辑 PPT。
$image-to-editable-ppt 把 /path/to/image-based.pptx 转成可编辑 PPT。
```

skill 通常会完成这些步骤：

1. 创建独立任务目录，并把输入归一化为 `pages/page_NNN/source.png`。
2. 每一页都分配给 page subagent，包括单页输入；多页输入按 `max_concurrent_pages` 分批分派。
3. 每页创建 manifest，重建可编辑文本、简单形状和图片资产。
4. 用状态脚本记录 dispatch、page result、repair 和 accepted 状态。
5. 主 agent 组装最终 `.pptx`，复制 `.pptx` 页面备注，并运行 deck validation。

## 输出结构

每次转换必须使用一个独立输出目录，所有中间文件和最终结果都保存在其中：

```text
output/image-to-editable-ppt/{job-id}/        # 单次转换任务目录
├── input/                                    # 原始输入文件副本
├── deck_manifest.json                        # 整个 deck 的页面清单和输出配置
├── page_jobs.json                            # 每页分派、修复和完成状态
├── run_state.json                            # 当前任务的整体运行状态
├── notes_manifest.json                       # PPTX 页面备注提取与映射记录
├── final/                                    # 最终输出目录
│   ├── {origin}_edited.pptx                  # 最终可编辑 PPTX
│   ├── validation.json                       # 最终 deck 校验结果
│   └── run_summary.json                      # 本次转换摘要
└── pages/                                    # 按页拆分的重建工作区
    ├── page_001/                             # 第 1 页工作目录
    │   ├── source.png                        # 归一化后的页面源图
    │   ├── page_request.json                 # 分派给 page subagent 的页面请求
    │   ├── imagegen-jobs.json                # 本页 imagegen 调用和结果记录
    │   ├── assets/                           # 本页拆出的独立图片资产
    │   ├── page.pptx                         # 本页单页 PPTX
    │   ├── preview.png                       # 本页重建预览图
    │   ├── split_assets_contact.png          # 本页资产切分检查图
    │   ├── manifest.json                     # 本页文本、形状和资产描述
    │   ├── validation.json                   # 本页校验结果
    │   └── page_result.json                  # 本页最终结果和限制记录
    └── page_002/                             # 后续页面工作目录
        └── ...
```

## 边界

- 这个 skill 面向输入页面的可编辑重建，不是从零生成整套 PPT 内容。
- 每一页都必须通过 page subagent 重建；没有可用 subagent 时不会降级为主 agent 手工重建。
- 复杂视觉资产需要 `$imagegen`；如果缺少可用图片生成/编辑能力，相关页面会作为 blocker 处理。
- 对照片、插画、纹理、手绘装饰等复杂视觉元素，通常只能作为独立图片资产移动，不能保证内部对象可编辑。
- 对表格、图表、流程图等结构化区域，会优先保留可编辑语义，但低置信度时应保留为资产并在验证报告里说明。
- 视觉相似不等于可编辑。最终判断应同时看 PPTX 结构、文本覆盖、资产来源和预览/diff。

## 仓库结构

```text
.
├── .github/                              # GitHub 工作流和仓库检查配置
├── skills/                               # Codex skill 安装包目录
│   └── image-to-editable-ppt/            # 可安装的 image-to-editable-ppt skill
│       ├── SKILL.md                      # skill 入口说明和执行规则
│       ├── requirements.txt              # 本地脚本所需的 Python 依赖
│       ├── agents/                       # Codex UI 展示用的 skill 元数据
│       ├── references/                   # 页面重建、状态机、QA 等参考规范
│       └── scripts/                      # 输入归一化、组装、校验等辅助脚本
├── AGENTS.md                             # 仓库级协作和编辑规则
├── CHANGELOG.md                          # 用户可见变更记录
├── LICENSE                               # 开源许可证
├── README.md                             # 中文说明文档
└── README_en.md                          # 英文说明文档
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ningzimu/image-to-editable-ppt-skill&type=Date)](https://www.star-history.com/#ningzimu/image-to-editable-ppt-skill&Date)

## 许可证

MIT
