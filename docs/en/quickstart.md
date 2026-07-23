# Quick Start

## Who This Is For

This page is for first-time Image to Editable PPT users. Prepare one or more slide images, a PDF, or an image-based `.pptx`, then ask an agent to use the `image-to-editable-ppt` skill to convert it into an editable PowerPoint presentation.

## Before You Begin

- **Usage allowance**: conversion consumes substantial tokens. ChatGPT Pro is recommended; Plus users should proceed with caution, as reconstructing a 10-slide deck may use an entire five-hour allowance. Start with one slide for your first trial.
- **Permissions**: we recommend running the skill in Codex with Full Access enabled. Otherwise, approval prompts may repeatedly interrupt the workflow. See [Installation and Configuration](/en/installation.md).
- **OCR Token (recommended)**: a free Baidu AI Studio Access Token can significantly improve text reconstruction. On first use, the AI will ask for it once. Send it the Token, and it will handle the configuration. See [Installation and Configuration](/en/installation.md).

## Fastest Way to Use It

First install the skill as described in [Installation and Configuration](/en/installation.md). Then use it directly in Codex. You can paste or attach an image, PDF, or `.pptx` in the conversation, or provide a local path:

```text
$image-to-editable-ppt Convert this image into an editable PowerPoint presentation.
```

For multi-page input:

```text
$image-to-editable-ppt Convert <path-to-deck.pdf> into an editable PowerPoint presentation.
```

In other agents that support explicit skill selection, select `image-to-editable-ppt` using that agent's syntax.

## First-Use Recommendations

- Run the complete workflow on a single image first to confirm that the output quality and processing time meet your needs before starting a multi-page task.
- When the AI asks for an OCR Token before conversion, take a minute to obtain and provide one. The skill can run without it, but text reconstruction quality will be lower.
- Stay near your computer during conversion. If Full Access is not enabled, some steps may require manual approval.
- Open the result in PowerPoint and confirm that text, shapes, and image assets can be edited independently. Check `final/validation.json` for validation details.

## Conversion Output

After the task finishes, an isolated output directory at `output/image-to-editable-ppt/{job-id}/` will contain:

- `final/{origin}_edited.pptx`: the final editable PowerPoint file
- `final/validation.json`: the final deck validation results
- `final/run_summary.json`: a summary of the conversion
- `pages/page_NNN/`: each page's reconstruction workspace, including source images, previews, assets, and intermediate files

See [Standard Workflow](/en/workflow.md) for the complete directory structure.
