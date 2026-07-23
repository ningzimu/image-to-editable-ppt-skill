# FAQ

## Why Does It Consume So Many Tokens? Can ChatGPT Plus Users Run It?

This skill uses a multi-agent reconstruction workflow. The AI runs a rebuild → self-check → page-level revision loop for every slide, and a page worker may make many attempts before the result is close enough to the source. Converting an image-based presentation into an editable one may cost two to three times as much as generating an image-based presentation.

**ChatGPT Pro is recommended; Plus users should proceed with caution.** Reconstructing a 10-slide deck may use an entire five-hour allowance, and one slide may take more than 10 minutes. Plus users should start with a single slide.

## When Should I Not Use This Skill?

Do not use it unless you have a strong need for editability. A lighter alternative is to use `gpt-image-2` directly: send it the slide image you want to change and ask it to make targeted edits and return the revised image.

This skill also does not generate a new presentation from an article, report, outline, or idea. That is the responsibility of [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill).

## Why Is Full Access Recommended?

The skill can run for a long time and automatically performs OCR, image generation and editing, file operations, subagent dispatch, and long polling. Ask for Approval mode repeatedly interrupts execution. Auto Approval mode is also known to block requests during OCR or image generation. If you are away from your computer, the conversion will stop. See [Installation and Configuration](/en/installation.md).

## What Is an OCR Token? Is It Required?

It is not required, but it is strongly recommended. The skill uses Baidu PaddleOCR-VL to correct text bounding boxes, font sizes, and font-size groups so that text restoration is based on measurements rather than visual estimates. Obtain a free Token from Baidu AI Studio at <https://aistudio.baidu.com/account/accessToken>. The free allowance is sufficient for personal use.

On first use, the AI will ask for the Token once. Send it the Token, and the setting will persist. Without a Token, the skill falls back to built-in offline detection, which knows where text is and how large it is but does not recognize the content, so text reconstruction quality will be lower.

## Which Input Formats Are Supported?

The skill supports a single image, multiple images, a multi-page PDF, and an image-based `.pptx`, and always outputs an editable `.pptx`. Multiple images become slides in the order provided, while PDFs and `.pptx` files preserve their original page order. Speaker notes from `.pptx` inputs are copied unchanged to the corresponding output slides.

## Can the Conversion Reproduce the Source Image Exactly?

An exact match is not guaranteed. Readable text and simple shapes are restored as editable objects whenever possible, but some image elements and text positions may be slightly offset. Complex elements such as photos, illustrations, and textures usually remain separate image assets and are not guaranteed to be internally editable. Evaluate quality using the PPTX structure, text coverage, asset provenance, and preview comparison together. See the Limitations section in [Standard Workflow](/en/workflow.md).

## Does It Support Agents Other Than Codex?

Yes, with conditions. The agent must support skill loading, file access, and CLI execution. Multi-page tasks also require a page-worker or subagent dispatch mechanism. If the current environment cannot create page workers, run multi-page tasks in an environment that can.

Non-Codex environments such as Claude Code, OpenClaw, and Hermes Agent usually do not have Codex OAuth and require an OpenAI-compatible image API fallback. See [Installation and Configuration](/en/installation.md).

Because results depend on the model's underlying reasoning and its ability to follow the skill, performance is not guaranteed with models below gpt-5.5.

## Which Image Generator Does It Use? Do I Need an API Key?

Image generation and editing prefer the current agent's built-in `image_gen.imagegen` tool. The workflow falls back to `editppt image` only under defined conditions, such as an unavailable or failed built-in tool, an unreadable edit input, or no valid local image result. The CLI tries local Codex OAuth first, using your subscription's image allowance, and then reads OpenAI-compatible API configuration from `~/.editppt/config.yaml`. Codex subscribers usually do not need to configure an API key. For a third-party fallback, give the AI the service's base URL, model name, and API key; it will save them to user-level configuration and mask sensitive values.

## How Do I Update the Skill?

Ask your agent to update it by sending: “Update the image-to-editable-ppt skill from https://github.com/ningzimu/image-to-editable-ppt-skill”. Alternatively, download the latest zip from Releases, replace the existing directory, and restart the agent. API credentials and the OCR Token are stored outside the skill directory in `~/.editppt/config.yaml`, so updates do not remove them. See [Installation and Configuration](/en/installation.md).

## What Should I Do If a Conversion Stops Partway Through?

First check whether the permission mode is waiting for your approval (see the Full Access question above). Per-page dispatch and completion state are recorded in `page_jobs.json` and `run_state.json` inside the task directory. Ask the AI to inspect the current run state and continue any unfinished pages.
