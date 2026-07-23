# Design Principles

Image to Editable PPT Skill solves one problem: turning slides that are visible but not editable back into PowerPoint presentations whose individual objects can be edited.

For a complete account of the skill's design and optimization, read [What 2,000 GitHub Stars Taught Me: Great AI Skills Are Tuned, Not Written](https://mp.weixin.qq.com/s/LaxWBX-nogHPpSxlk-Vs8Q).

## Object-Level Reconstruction, Not a Full-Slide Image

The contents of a slide image do not all have the same editing value. This skill separates each page into three object types:

- **Readable text** → restored as native text boxes whenever possible, so you can directly change the text, font size, and color.
- **Simple geometry** (rectangles, circles, lines, arrows, and similar elements) → recreated as PowerPoint shapes whenever possible, so you can move, resize, and restyle them.
- **Complex visual elements** (photos, illustrations, icons, textures, and hand-drawn decoration) → preserved as separate image assets with source records. They can be moved and replaced as a whole, but their internal elements are not guaranteed to be editable.

For structured regions such as tables, charts, and flowcharts, the skill prioritizes preserving editable semantics. When confidence is low, it keeps the region as an asset and explains the choice in the validation report.

## Measurement-Driven Text Restoration

Text size and position are not estimated by eye. At the start of a conversion, the entire input is submitted to OCR (PaddleOCR-VL) as a batch task. OCR generates text annotations for every page: precise bounding boxes, font sizes measured from the source image's ink, same-level font-size groups, and recognized text. The AI reconstructs text from these measurements and automatically keeps same-level text at consistent sizes.

Without an OCR Token, the skill falls back to its built-in offline detector. This detector performs geometric measurement only: it knows where text is and how large it is, but it does not recognize the content. Text reconstruction quality will therefore be lower. This is why we recommend spending a minute to obtain a free Token. See [Installation and Configuration](/en/installation.md).

## Rebuild → Self-Check → Page-Level Revision

Visual similarity does not guarantee editability, and a single generation attempt is unlikely to be sufficient. The reconstructor for each page—either the main agent in local mode or a page worker—runs a loop: rebuild the page, compare it with the source, and make page-level corrections for missing text, misalignment, or missing assets. It may take multiple iterations before the result is close enough to the original.

This loop is the main reason the skill consumes substantial tokens: a page worker may try many iterations on one page. Converting an image-based deck into an editable presentation may cost two to three times as much as generating an image-based deck. We believe the cost is justified because delivering a pixel-perfect copy that cannot be edited defeats the purpose. For the same reason, **do not use this skill unless you have a strong need for editability**.

## Parallel Multi-Page Processing with Inspectable State

For multi-page input, the main agent dispatches pages to page workers for parallel reconstruction according to the available concurrency slots. Each page has its own working directory and manifest. Dispatch state, page results, and acceptance state are all recorded through the `editppt` CLI. Finally, `editppt run finalize` assembles the pages in order and runs deck-level validation. See [Standard Workflow](/en/workflow.md) for details.

Do not judge conversion quality from preview images alone. Review the PPTX structure, text coverage, asset provenance, and preview/diff together.

## Two Skills, Two Responsibilities

This skill performs reconstruction, not creation. Generating a new presentation from an article, report, or outline is the responsibility of [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill). The two skills serve different purposes:

- **codex-ppt**: content → image-based PowerPoint. It provides consistent visuals and a controlled workflow for most presentations and reports.
- **image-to-editable-ppt**: image-based slides → editable PowerPoint. Use it only when object-level editability is genuinely required.

For a detailed comparison of the two skills, see [skill_duo_intro.pdf](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/main/assets/skill_duo_intro.pdf). The presentation itself was generated with codex-ppt skill.
