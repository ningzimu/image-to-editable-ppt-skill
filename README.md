# Image to Editable PPT Skill

[![English](https://img.shields.io/badge/docs-English-blue)](README_en.md) [![GitHub stars](https://img.shields.io/github/stars/ningzimu/image-to-edited-ppt-skill?style=flat&logo=github&label=stars)](https://github.com/ningzimu/image-to-edited-ppt-skill/stargazers) [![GitHub forks](https://img.shields.io/github/forks/ningzimu/image-to-edited-ppt-skill?style=flat&logo=github&label=forks)](https://github.com/ningzimu/image-to-edited-ppt-skill/forks)

一个面向 Codex 的图片、PDF、图片版 PPT/PPTX 转可编辑 PowerPoint 的 skill，也可用于其他支持 `SKILL.md` 的 agent。它把输入归一化为逐页图片，再重建为 `.pptx`：文字尽量恢复为可编辑文本框，简单几何尽量恢复为原生形状，复杂视觉元素保留为带来源记录的独立图片资产。

这个仓库只维护 skill 本身和仓库级说明；日常生成结果默认写入 `output/`，不会提交到 Git。

## 特点

- 单张图片、多张图片、多页 PDF、图片版 PPT/PPTX 到可编辑 `.pptx`。
- 多页场景按页并行分配给 Codex 子 agent，主 agent 负责质量检查和最终组装。
- PDF/PPT/PPTX 保留页码顺序；多张图片不承诺相对顺序。
- PPT/PPTX 输入的页面备注会复制到输出对应页，备注内容不改动。
- 使用 manifest 描述页面尺寸、文本框、形状、图片资产和来源记录。
- 通过本地脚本组装 PPTX、生成预览、输出 diff 和 validation report。
- 明确区分“整页图片封装”和“可编辑重建”：整页 raster 不能冒充对象级可编辑 PPT。
- 支持复杂视觉页的混合策略：可编辑文字 + 简单形状 + 独立 raster/SVG 资产。

## 输入与输出契约

输出始终是 PowerPoint `.pptx`：

| 输入 | 输出 |
| --- | --- |
| 1 张图片 | 1 页 `.pptx` |
| 多张图片 | 多页 `.pptx`，每张图片 1 页，不承诺相对顺序 |
| 多页 PDF | 多页 `.pptx`，PDF 第 N 页对应输出第 N 页 |
| PPT/PPTX | 页数一致的 `.pptx`，原第 N 页对应输出第 N 页 |

只有 PPT/PPTX 输入会处理页面备注。备注由主 agent 按页原样复制到输出 PPTX：不翻译、不摘要、不改写，也不交给子 agent 处理。

## 适用场景

- 把一张或多张 slide 图片重建成可调整文字和元素位置的 PPT。
- 把多张图片或多页 PDF 转成一个多页 `.pptx`。
- 把图片式 PPT/PPTX 页面转换为更容易二次编辑的 `.pptx`，并保留原页面备注。
- 复刻单页视觉设计，同时保留文本可编辑性和验证产物。
- 对比源图与重建预览，定位缺字、错位、资产缺失或关系损坏。

## 安装

推荐使用 `skills` CLI 安装到 Codex 的全局 skills 目录：

```bash
npx -y skills@latest add ningzimu/image-to-edited-ppt-skill \
  --skill image-to-editable-ppt \
  --agent codex \
  --global
```

安装完成后，重启 Codex 让新 skill 生效。

本地开发时可以用软链接，方便实时调试：

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/image-to-edited-ppt-skill/skills/image-to-editable-ppt \
  ~/.codex/skills/image-to-editable-ppt
```

首次运行依赖型脚本前，建议在 skill 目录里创建本地运行环境：

```bash
python3 skills/image-to-editable-ppt/scripts/image_to_editable_ppt_runtime.py bootstrap
python3 skills/image-to-editable-ppt/scripts/image_to_editable_ppt_runtime.py doctor
```

运行环境默认创建在 `skills/image-to-editable-ppt/.venv`。图片版 `.pptx` 会用轻量 OOXML/zip 解析直接提取每页整图，不需要 LibreOffice。

依赖分工：

- Python 包安装到 skill 本地 `.venv`，便于迁移和隔离。
- PDF 渲染使用 PyMuPDF。
- 图片处理使用 Pillow。
- 图片版 `.pptx` 输入使用标准库解析 slide relationship，并要求每页只有一张整页嵌入图片。
- 旧 `.ppt` 或原生/复杂 `.pptx` 不走轻量路径；请先导出为 PDF 或逐页图片。

## 使用方式

在 Codex 里可以用 `$image-to-editable-ppt` 显式选中这个技能，并提供源文件：

```text
$image-to-editable-ppt 把 /path/to/slide.png 转成可编辑 PPT。
$image-to-editable-ppt 把 /path/to/a.png 和 /path/to/b.png 转成可编辑 PPT。
$image-to-editable-ppt 把 /path/to/deck.pdf 转成可编辑 PPT。
$image-to-editable-ppt 把 /path/to/image-based.pptx 转成可编辑 PPT，并保留备注。
```

skill 通常会完成这些步骤：

1. 创建独立任务目录，并把输入归一化为 `pages/page_NNN/source.png`。
2. 多页场景按页分配给子 agent 并行重建。
3. 每页创建 manifest，重建可编辑文本、简单形状和图片资产。
4. 主 agent 组装最终 `.pptx`，复制 PPT/PPTX 备注，并运行 deck validation。
5. 根据验证结果做最小范围修复。

## 脚本入口

这些脚本位于 `skills/image-to-editable-ppt/scripts/`：

- `image_to_editable_ppt_runtime.py`：创建本地 `.venv`、安装依赖，并检查 Python 包与可选工具。
- `prepare_inputs.py`：创建 job 目录，把图片/PDF/PPT/PPTX 归一化为 `pages/page_NNN/source.png`，并生成 `deck_manifest.json`。
- `build_pptx_from_manifest.py`：从单页 `manifest.json` 或多页 `deck_manifest.json` 组装 `.pptx`。
- `validate_pptx.py`：校验 PPTX 包结构、页数、manifest、资产来源、文本覆盖和备注 hash。
- `render_diff.py`、`split_alpha_components.py`、`crop_image_asset.py`：辅助预览、差异检查和资产拆分。

示例：

```bash
python3 skills/image-to-editable-ppt/scripts/prepare_inputs.py /path/to/deck.pdf
python3 skills/image-to-editable-ppt/scripts/build_pptx_from_manifest.py \
  --deck-manifest output/image-to-editable-ppt/{job-id}/deck_manifest.json \
  --out output/image-to-editable-ppt/{job-id}/rebuilt.pptx
python3 skills/image-to-editable-ppt/scripts/validate_pptx.py \
  output/image-to-editable-ppt/{job-id}/rebuilt.pptx \
  --deck-manifest output/image-to-editable-ppt/{job-id}/deck_manifest.json \
  --report output/image-to-editable-ppt/{job-id}/validation.json
```

## 输出结构

每次转换必须使用一个独立输出目录，所有中间文件和最终结果都保存在其中：

```text
output/image-to-editable-ppt/{job-id}/
├── input/
├── deck_manifest.json
├── rebuilt.pptx
├── validation.json
├── notes_manifest.json
└── pages/
    ├── page_001/
    │   ├── source.png
    │   ├── run_request.json
    │   ├── imagegen-jobs.json
    │   ├── assets/
    │   ├── split_assets_contact.png
    │   ├── manifest.json
    │   ├── preview.png
    │   ├── diff.png
    │   ├── diff.json
    │   ├── validation.json
    │   └── qa_notes.md
    └── page_002/
        └── ...
```

`output/` 是生成产物目录，默认被 `.gitignore` 忽略。需要放入 README 或文档的精选示例图，请放到 `assets/`。

## 边界

- 这个 skill 面向输入页面的可编辑重建，不是从零生成整套 PPT 内容。
- 对照片、插画、纹理、手绘装饰等复杂视觉元素，通常只能作为独立图片资产移动，不能保证内部对象可编辑。
- 对表格、图表、流程图等结构化区域，会优先保留可编辑语义，但低置信度时应保留为资产并在验证报告里说明。
- 图片版 `.pptx` 只支持每页一张整页嵌入图片；旧 `.ppt` 或原生/复杂 `.pptx` 请先导出为 PDF 或逐页图片。
- 视觉相似不等于可编辑。最终判断应同时看 PPTX 结构、文本覆盖、资产来源和预览/diff。

## 仓库结构

```text
.
├── .github/              # PR 模板和轻量仓库检查
├── assets/               # README 或文档使用的精选示例资源
├── skills/
│   └── image-to-editable-ppt/
│       ├── SKILL.md
│       ├── requirements.txt
│       ├── agents/
│       ├── references/
│       └── scripts/
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── README.md
└── README_en.md
```

## 许可证

MIT
