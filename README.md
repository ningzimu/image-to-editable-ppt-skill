# Image to Editable PPT Skill

[![English](https://img.shields.io/badge/docs-English-blue)](README_en.md) [![GitHub stars](https://img.shields.io/github/stars/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=stars)](https://github.com/ningzimu/image-to-editable-ppt-skill/stargazers) [![GitHub forks](https://img.shields.io/github/forks/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=forks)](https://github.com/ningzimu/image-to-editable-ppt-skill/forks)

![Image to Editable PPT 项目概览](assets/image-to-editable-ppt-overview.png)

一个用于把图片、PDF、图片版PPT 转成可编辑 PowerPoint 的 skill。它先把输入归一化为逐页任务，再重建为 `.pptx`：可读文字尽量恢复为原生文本框，简单几何尽量恢复为 PowerPoint 形状，复杂视觉元素保留为带来源记录的独立图片资产。

它适合把截图式或图片式幻灯片变成更容易二次编辑的 PPT，让文字、简单形状和视觉素材尽量分开调整。

> [!WARNING]
> 目前该skill 采用了多智能体协作复原流程，有着复杂的流程控制，不是轻量转换器。AI 会执行“**重建 → 自我检查 → 页面内修正**”的循环，并可能进行多轮迭代，直到它认为结果足够接近原图。在这个过程中，page worker 可能会对页面做很**多轮尝试**，因此整体上比较费 token。
>
> **推荐 ChatGPT Pro 用户使用；Plus 用户请谨慎使用。**
>
> 复原一个 10 页 PPT 有可能消耗完你的 5 小时额度。单页PPT复原时间可能在10min以上。多页输入会按并发槽位直接分派给 page worker 处理。
>
> **如果没有强烈的可编辑需求，请不要使用这个 skill。**
>
> 更轻量的做法是直接使用 gpt-image-2 的图像编辑能力：把你不满意的那一页 PPT 图片发给它，让它针对性修改，并返回修改后的图片。

> [!TIP]
> 本 skill 不负责从文章、报告、大纲或想法直接生成全新 PPT。如果你要做的是“生成一份 PPT”，可以使用 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill)。
>
> 关于 `codex-ppt` 和 `image-to-editable-ppt` 这两个技能的详细介绍，参见 [skill_duo_intro.pdf](assets/skill_duo_intro.pdf)。该 PPT 由 `codex-ppt` skill 生成，提示词为：“请分别阅读 Codex PPT和 Image to Editable PPT 这两个技能的内容，然后用 Codex PPT 帮我做一个PPT吧，20页，每个技能的介绍10页。”

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
  <tr>
    <td><img src="assets/showcase-origin-mdt-kidney-cancer.jpg" alt="肾癌 MDT 信息图原图" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-mdt-kidney-cancer.png" alt="肾癌 MDT 信息图转换后可编辑效果" width="420"></td>
  </tr>
</table>

## 特点

- 适用场景广泛，支持多种输入：单张图片、多张图片、多页 PDF、图片版PPT 到可编辑 `.pptx`。
- 单张图片输入由主 agent 直接重建。
- 多页输入由主 agent 按 `max_concurrent_pages` 直接分派给 page worker/subagent 并行处理。
- 图片生成和编辑统一通过 `editppt image` CLI 完成；CLI 会优先使用本机 Codex OAuth，缺失时再使用 OpenAI-compatible API 配置。
- 第三方 API fallback 配置保存在 `~/.editppt/config.yaml`；Windows 下对应 `%USERPROFILE%\.editppt\config.yaml`。
- 采用纯视觉重建方案，无需第三方 OCR 或版面分析服务依赖。
- 多张图片按提供顺序生成页面；PDF 和 `.pptx` 保留原页码顺序。
- `.pptx` 输入的页面备注会复制到输出对应页，备注内容不改动。
- 根据具体页面情况决定是否通过已确认 image backend 做图片分层抽取；需要时用稀疏 asset sheet 合并前景素材，尽可能降低图片生成调用次数。
- 支持复杂视觉页的混合策略：可编辑文字 + 简单形状 + 独立图片资产。

## 适用场景

- 把一张或多张 slide 图片重建成可调整文字和元素位置的 PPT。
- 把多张图片或多页 PDF 转成一个多页 `.pptx`。
- 把图片版PPT页面转换为更容易二次编辑的 `.pptx`，并保留原页面备注。
- 复刻单页视觉设计，同时保留文本可编辑性。
- 对比源图与输出页面，定位缺字、错位或资产缺失。

## 运行要求

- 多页输入需要 agent 能分派 page worker/subagent；如果不能创建 page worker，应换到支持 page worker 的环境执行。
- 复杂背景补全、前景图标提取、透明 asset sheet 和局部图片编辑统一走 `editppt image edit/generate/batch`。
- 如果本机有 Codex OAuth（`~/.codex/auth.json`），CLI 会直接使用；否则使用 API fallback。
- API fallback 配置保存在 `~/.editppt/config.yaml`；Windows 下对应 `%USERPROFILE%\.editppt\config.yaml`。

## 图片 Backend 与第三方 API 配置

`editppt image` 会自动选择图片后端：优先使用本机 Codex OAuth；如果不可用，再读取 `~/.editppt/config.yaml` 或环境变量里的 OpenAI-compatible API 配置。

通常不需要手动配置。只有这些情况才需要配置 API fallback：

- 用户明确要求使用第三方 API 或 OpenAI 兼容中转站。
- 在 Claude Code、OpenClaw、Hermes Agent 等非 Codex 环境中使用，并且没有可用的 Codex OAuth auth。
- `editppt image` 报告 Codex OAuth 和 `OPENAI_API_KEY` 都不可用。

API key 只写入用户级配置，不要写进项目目录、run 目录或 skill 目录。常用命令：

```bash
editppt config --api-key "your-api-key" --model gpt-image-2

editppt config \
  --api-key "your-api-key" \
  --base-url "https://your-openai-compatible-endpoint/v1" \
  --model openai/gpt-image-2

editppt doctor --check-api
```

## 已知问题

- 其他 agent 需要支持 skill 加载、文件读写、CLI 执行，以及 page worker/subagent 分派机制。
- Codex OAuth 路径依赖本机 Codex auth 和订阅侧图片额度；API fallback 依赖所选 OpenAI-compatible 服务的图片生成/编辑能力。
- 本 skill有着相对复杂的流程控制，Token花费比较高。将一个图片PPT转换成可编辑PPT的成本，**可能是生成图片PPT成本的2-3倍**。
- 受限于模型基础理解能力和对 skill 的遵循能力，**不保证 gpt-5.5 以下模型的使用效果**。
- 部分图片元素和文字位置可能会有轻微偏移，**不能保证 100% 复刻原始页面**。

## 安装

```text
安装 image-to-editable-ppt 这个 skill，地址是 https://github.com/ningzimu/image-to-editable-ppt-skill
```

## 更新

```text
更新 image-to-editable-ppt 这个 skill，地址是 https://github.com/ningzimu/image-to-editable-ppt-skill
```

## 使用方式

在支持显式选择 skill 的 agent 里，可以用对应语法选中 `image-to-editable-ppt`；Codex 中可使用 `$image-to-editable-ppt`。图片、PDF 和 `.pptx` 可以直接粘贴或附加到对话框，也可以提供本地路径：

```text
$image-to-editable-ppt 把这张图片转成可编辑 PPT。
$image-to-editable-ppt 把这些图片转成一个可编辑 PPT。
$image-to-editable-ppt 把 <path-to-deck.pdf> 转成可编辑 PPT。
$image-to-editable-ppt 把 <path-to-image-based.pptx> 转成可编辑 PPT。
```

skill 通常会完成这些步骤：

1. 创建独立任务目录，把输入归一化为 `pages/page_NNN/source.png`，并写入默认 `editppt image` backend。
2. 单张图片由主 agent 直接重建，并用 `editppt run record --agent-id main` 记录；多页输入按 `max_concurrent_pages` 分批分派给 page worker。
3. 每个 page worker 负责自己的页面目录，完成页面重建、自检和 page-local 修正。
4. 每页创建 manifest，重建可编辑文本、简单形状和图片资产。
5. 用 `editppt` 命令记录 dispatch、page result 和 accepted 状态。
6. 主 agent 用 `editppt run finalize` 按页顺序读取已记录的 `manifest.json` 重建最终 `.pptx`，复制 `.pptx` 页面备注，并运行 deck validation。

## 输出结构

输出始终是 PowerPoint `.pptx`：

| 输入      | 输出                                           |
| --------- | ---------------------------------------------- |
| 1 张图片  | 1 页 `.pptx`                                 |
| 多张图片  | 多页 `.pptx`，每张图片 1 页，按提供顺序排列  |
| 多页 PDF  | 多页 `.pptx`，PDF 第 N 页对应输出第 N 页     |
| 图片版PPT | 页数一致的 `.pptx`，原第 N 页对应输出第 N 页 |

只有 `.pptx` 输入会处理页面备注。备注由主 agent 按页原样复制到输出 PPTX：不翻译、不摘要、不改写，也不交给 page worker 处理。

每次转换必须使用一个独立输出目录，所有中间文件和最终结果都保存在其中：

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
    │   ├── worker-prompt.md                  # 多页任务中生成给 page worker 的提示词
    │   ├── imagegen-jobs.json                # 本页图片生成/编辑调用和结果记录
    │   ├── assets/                           # 本页拆出的独立图片资产
    │   ├── page.pptx                         # 本页单页 PPTX；record 阶段用于校验和交付性检查
    │   ├── preview.png                       # 本页重建预览图
    │   ├── split_assets_contact.png          # 本页资产切分检查图
    │   ├── manifest.json                     # 本页文本、形状和资产描述；finalize 的权威输入
    │   ├── validation.json                   # 本页校验结果
    │   └── page_result.json                  # 本页产物索引
    └── page_002/                             # 后续页面工作目录
        └── ...
```

## 边界

- 这个 skill 面向输入页面的可编辑重建，不是从零生成整套 PPT 内容。
- 多页输入通过 page worker/subagent 并行重建。
- 复杂视觉资产需要可用 `editppt image` backend；如果缺少图片生成/编辑能力，仍应先交付当前可打开、结构有效的 PPT，并在验证结果里说明缺失资产。
- 对照片、插画、纹理、手绘装饰等复杂视觉元素，通常只能作为独立图片资产移动，不能保证内部对象可编辑。
- 对表格、图表、流程图等结构化区域，会优先保留可编辑语义，但低置信度时应保留为资产并在验证报告里说明。
- 视觉相似不等于可编辑。最终判断应同时看 PPTX 结构、文本覆盖、资产来源和预览/diff。

## 仓库结构

```text
.
├── .github/                              # GitHub 工作流和仓库检查配置
├── skills/                               # Skill 安装包目录
│   └── image-to-editable-ppt/            # 可安装的 image-to-editable-ppt skill
│       ├── SKILL.md                      # skill 入口说明和执行规则
│       ├── agents/                       # Agent 展示用的 skill 元数据
│       ├── cli/                          # 自包含 `editppt` CLI 和确定性 runtime 模块
│       ├── references/                   # 页面重建、状态机、QA 等参考规范
│       ├── prompts/                      # page worker prompt 模板
│       └── scripts/                      # skill 内 prompt 组装脚本
├── AGENTS.md                             # 仓库级协作和编辑规则
├── CHANGELOG.md                          # 用户可见变更记录
├── LICENSE                               # 开源许可证
├── README.md                             # 中文说明文档
└── README_en.md                          # 英文说明文档
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ningzimu/image-to-editable-ppt-skill&type=Date)](https://www.star-history.com/#ningzimu/image-to-editable-ppt-skill&Date)

## 交流群

扫描二维码加入 Skill 交流群，分享使用经验、反馈问题，并获取更新通知。

<img src="assets/image-to-editable-ppt-community-qr.png" alt="Image to Editable PPT Skill 交流群二维码" width="220">

## 许可证

MIT
