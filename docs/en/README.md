# Image to Editable PPT Skill Documentation

Image to Editable PPT is a skill that converts images, PDFs, and image-based PowerPoint files into **object-level editable PowerPoint presentations** (`.pptx`). It first normalizes the input into page-level tasks, then rebuilds each page as a `.pptx`: readable text is restored as native text boxes whenever possible, simple geometry is recreated as PowerPoint shapes, and complex visual elements are preserved as separate image assets with source records.

![Image to Editable PPT overview](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/image-to-editable-ppt-overview.png)

## How to Read These Docs

If you just want to get started, see [Quick Start](/en/quickstart.md).

To understand why the skill is designed this way and why it consumes substantial tokens, see [Design Principles](/en/design.md).

For installation, updates, OCR Token setup, or third-party image API configuration, see [Installation and Configuration](/en/installation.md).

To understand the complete conversion process and output structure, see [Standard Workflow](/en/workflow.md).

If you are already using the skill and run into problems, see [FAQ](/en/faq.md).

## Pages

- [Quick Start](/en/quickstart.md): the shortest path for first-time users, example commands, and output files.
- [Design Principles](/en/design.md): object-level reconstruction, the rebuild–self-check–revision loop, and how this skill works alongside codex-ppt.
- [Installation and Configuration](/en/installation.md): installation and update options, recommended permissions, OCR Token setup, image backends, and third-party API fallback.
- [Standard Workflow](/en/workflow.md): the complete flow from input normalization and page dispatch through page reconstruction, final assembly, validation, and the output directory structure.
- [FAQ](/en/faq.md): common questions about token usage, permission modes, OCR Tokens, reconstruction accuracy, and agent support.
- [Example Prompts](/en/prompts.md): reusable prompts for converting a single image, multiple images, a PDF, or an image-based PowerPoint file.

## Conversion Examples

| Original | Editable result |
| --- | --- |
| ![Original market overview](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-market-snapshot.png) | ![Editable market overview](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-market-snapshot.png) |
| ![Original project status report](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-status-report.png) | ![Editable project status report](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-status-report.png) |
| ![Original kidney cancer MDT infographic](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-mdt-kidney-cancer.jpg) | ![Editable kidney cancer MDT infographic](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-mdt-kidney-cancer.png) |

## Key Features

- Multiple input formats: convert a single image, multiple images, a multi-page PDF, or an image-based PowerPoint file into an editable `.pptx`.
- Object-level reconstruction: text becomes native text boxes, simple geometry becomes PowerPoint shapes, and complex visual elements remain separate image assets, so all three object types can be adjusted independently.
- Measurement-driven text restoration: OCR generates text annotations for every page, including bounding boxes, font sizes, font-size groups, and recognized text. The model reconstructs text from these measurements and automatically keeps same-level text at consistent sizes. See the OCR Token section in [Installation and Configuration](/en/installation.md).
- Parallel multi-page reconstruction: the main agent dispatches multi-page inputs to page workers/subagents in parallel; single-page inputs use the same reconstruction flow locally in the main agent.
- Image generation and editing prefer the current agent's built-in `image_gen.imagegen` tool. Only defined fallback conditions invoke `editppt image`, whose CLI selects between Codex OAuth and an OpenAI-compatible API.
- Speaker notes from `.pptx` inputs are copied unchanged to the matching output pages without translation, summarization, or rewriting.
- Stable page order: multiple images follow the order provided, while PDFs and `.pptx` files preserve their original page order.

## Important Notes

**This is not a lightweight converter.** The skill uses a multi-agent reconstruction workflow in which AI performs a rebuild → self-check → page-level revision loop, potentially over multiple iterations. It can consume substantial tokens: reconstructing a 10-slide deck may use an entire five-hour ChatGPT allowance, and a single slide may take more than 10 minutes. **ChatGPT Pro is recommended; Plus users should proceed with caution.**

**Do not use this skill unless you have a strong need for editability.** A lighter alternative is to use `gpt-image-2` directly: send it the slide image you want to change and ask it to make the targeted edits.

**We recommend running this skill in Codex with Full Access enabled.** Otherwise, approval prompts may repeatedly interrupt OCR, image generation, and subagent dispatch. See [Installation and Configuration](/en/installation.md).

This skill does not create a new presentation from an article, report, outline, or idea. If your goal is to generate a presentation, use [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill).

## Related Links

- GitHub repository: https://github.com/ningzimu/image-to-editable-ppt-skill
- Project website: https://ppt-skill.ningzimu.vip
- Presentation-generation skill (sister project): https://github.com/ningzimu/codex-ppt-skill
- Design and optimization experience: [What 2,000 GitHub Stars Taught Me: Great AI Skills Are Tuned, Not Written](https://mp.weixin.qq.com/s/LaxWBX-nogHPpSxlk-Vs8Q)
