# Image to Editable PPT Skill

[![中文](https://img.shields.io/badge/docs-中文-red)](README.md) [![GitHub stars](https://img.shields.io/github/stars/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=stars)](https://github.com/ningzimu/image-to-editable-ppt-skill/stargazers) [![GitHub forks](https://img.shields.io/github/forks/ningzimu/image-to-editable-ppt-skill?style=flat&logo=github&label=forks)](https://github.com/ningzimu/image-to-editable-ppt-skill/forks)

![Image to Editable PPT project overview](assets/image-to-editable-ppt-overview.png)

A Codex skill for converting images, PDFs, and image-based PPT files into editable PowerPoint `.pptx` output. It normalizes inputs into per-page jobs, then page subagents rebuild editable text, simple shapes, and positioned visual assets.

It is useful when screenshot-like or image-based slides need to become easier to edit again, with text, simple shapes, and visual assets separated where practical.

> [!WARNING]
> This skill currently uses a multi-agent collaborative reconstruction workflow with complex flow control. It is not a lightweight converter. The AI runs a "**rebuild -> self-verify -> self-repair**" loop and may iterate multiple times until it judges the result close enough to the source. During this process, page subagents may make **many attempts** per page, so the workflow can consume a large number of tokens.
>
> **GPT Pro is recommended. Plus users should use this skill cautiously.**
>
> Reconstructing a 10-page PPT may consume your entire 5-hour usage window. A single-page PPT reconstruction may take more than 10 minutes. Strongly consider testing with one page first instead of converting all pages at once.
>
> **If you do not strongly need editability, avoid this skill.**
>
> A lighter approach is to use gpt-image-2 image editing directly: provide the specific PPT page image you are unhappy with, ask for a targeted edit, and have it return the modified image.

> [!TIP]
> This skill does not create new decks from articles, reports, outlines, or ideas. If your goal is to generate a PPT, use [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill).
>
> For a detailed introduction to `codex-ppt` and `image-to-editable-ppt`, see [skill_duo_intro.pdf](assets/skill_duo_intro.pdf). This deck was generated with the `codex-ppt` skill using the prompt: "请分别阅读 Codex PPT和 Image to Editable PPT 这两个技能的内容，然后用 Codex PPT 帮我做一个PPT吧，20页，每个技能的介绍10页。"

## Conversion Examples

<table>
  <tr>
    <th>Original</th>
    <th>Editable Result</th>
  </tr>
  <tr>
    <td><img src="assets/showcase-origin-market-snapshot.png" alt="Market snapshot original" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-market-snapshot.png" alt="Market snapshot editable result" width="420"></td>
  </tr>
  <tr>
    <td><img src="assets/showcase-origin-status-report.png" alt="Status report original" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-status-report.png" alt="Status report editable result" width="420"></td>
  </tr>
  <tr>
    <td><img src="assets/showcase-origin-mdt-kidney-cancer.jpg" alt="Kidney cancer MDT infographic original" width="420"></td>
    <td><img src="assets/showcase-editable-ppt-result-mdt-kidney-cancer.png" alt="Kidney cancer MDT infographic editable result" width="420"></td>
  </tr>
</table>

## Highlights

- Broad input coverage for many slide-reconstruction scenarios: one image, multiple images, multi-page PDFs, and image-based PPT files into editable `.pptx`.
- Uses a multi-agent architecture: Codex subagents rebuild every page in parallel where possible, speeding up multi-page reconstruction; the parent agent handles dispatch, QA, repair orchestration, and final assembly.
- Reuses existing Codex capabilities, including subagents and `$imagegen`, in a pure visual reconstruction workflow with no third-party OCR or layout-analysis service dependency.
- Keep multiple images in the provided order; preserve PDF and `.pptx` page order.
- Preserve `.pptx` speaker notes on matching output slides without modifying note text.
- Decides page by page whether to use `$imagegen` / gpt-image-2 for visual layer extraction; when needed, sparse asset sheets group foreground assets to reduce gpt-image-2 calls.
- Supports hybrid reconstruction: editable text, simple native shapes, and independent image assets.

## Input And Output Contract

Output is always a PowerPoint `.pptx` file:

| Input | Output |
| --- | --- |
| 1 image | 1-slide `.pptx` |
| Multiple images | Multi-slide `.pptx`, one slide per image, in the provided order |
| Multi-page PDF | Multi-slide `.pptx`; PDF page N maps to output slide N |
| Image-based PPT | `.pptx` with the same slide count; source slide N maps to output slide N |

Speaker notes are handled only for `.pptx` input. The parent agent copies notes to matching output slides unchanged: no translation, summarization, rewriting, or page-subagent processing.

## Use Cases

- Rebuild one or more slide images into a PowerPoint deck whose text and element positions can be adjusted.
- Convert multiple images or a multi-page PDF into a multi-slide `.pptx`.
- Convert image-based PPT slides into a more editable `.pptx` while preserving source speaker notes.
- Recreate a single-slide visual design while keeping text editable.
- Compare source pages against output slides to find missing text, alignment drift, or missing assets.

## Runtime Requirements

- Codex must be able to dispatch page subagents; if page subagents cannot be created, the skill stops and reports a blocker.
- Complex background repair, icon redraws, transparent asset sheets, and targeted repairs depend on `$imagegen` / built-in `image_gen`.

## Known Limitations

- This skill is deeply adapted for Codex and currently **does not support other agents**.
- This skill has been tested under Codex membership tiers (Plus / Max). **Compatibility with third-party API integrations has not been tested**.
- This skill has relatively complex flow control and high token usage. The cost of converting an image-based PPT into an editable PPT **may be 2-3x the cost of generating an image-based PPT**.
- Results are limited by the model's baseline visual understanding and its ability to follow the skill workflow; usage quality is **not guaranteed for models below gpt-5.5**.
- Some image elements and text positions may shift slightly, so output is **not guaranteed to be a 100% replica of the original page**.

## Install

Recommended Codex installation:

```bash
npx -y skills@latest add ningzimu/image-to-editable-ppt-skill \
  --skill image-to-editable-ppt \
  --agent codex \
  --global
```

You can also type this directly in a Codex conversation:

```text
$skill-installer https://github.com/ningzimu/image-to-editable-ppt-skill
```

You can also download `image-to-editable-ppt-skill-v*.zip` from GitHub Releases, unzip it, and place the contained `image-to-editable-ppt` folder at `~/.codex/skills/image-to-editable-ppt`.

Restart Codex after installation.

## Usage

Use `$image-to-editable-ppt` to explicitly select this skill. Images, PDFs, and `.pptx` files can be pasted or attached directly in the conversation, or provided as local paths:

```text
$image-to-editable-ppt convert this image into an editable PowerPoint.
$image-to-editable-ppt convert these images into one editable PowerPoint.
$image-to-editable-ppt convert /path/to/deck.pdf into an editable PowerPoint.
$image-to-editable-ppt convert /path/to/image-based.pptx into an editable PowerPoint.
```

The normal workflow is:

1. Create an isolated job folder and normalize inputs into `pages/page_NNN/source.png`.
2. Dispatch every page to a page subagent, including single-page inputs; batch multi-page runs by `max_concurrent_pages`.
3. Build one page manifest per page with editable text, simple shapes, and positioned image assets.
4. Use state scripts to record dispatch, page results, repair, and accepted status.
5. Assemble the final `.pptx`, copy `.pptx` speaker notes when present, and run deck validation.

## Output Layout

Use one isolated output directory per conversion. All intermediate files and final outputs stay inside it:

```text
output/image-to-editable-ppt/{job-id}/        # One conversion job folder
├── input/                                    # Original input file copies
├── deck_manifest.json                        # Deck-level page list and output config
├── page_jobs.json                            # Per-page dispatch, repair, and completion state
├── run_state.json                            # Overall job state
├── notes_manifest.json                       # PPTX speaker-note extraction and mapping record
├── final/                                    # Final output folder
│   ├── {origin}_edited.pptx                  # Final editable PPTX
│   ├── validation.json                       # Final deck validation result
│   └── run_summary.json                      # Conversion summary
└── pages/                                    # Per-page reconstruction workspaces
    ├── page_001/                             # Page 1 workspace
    │   ├── source.png                        # Normalized source image for this page
    │   ├── page_request.json                 # Page request sent to the page subagent
    │   ├── imagegen-jobs.json                # Imagegen calls and result records for this page
    │   ├── assets/                           # Independent image assets for this page
    │   ├── page.pptx                         # Single-page PPTX
    │   ├── preview.png                       # Reconstructed page preview
    │   ├── split_assets_contact.png          # Asset-splitting inspection image
    │   ├── manifest.json                     # Text, shape, and asset description for this page
    │   ├── validation.json                   # Page validation result
    │   └── page_result.json                  # Final page result and known limits
    └── page_002/                             # Later page workspace
        └── ...
```

## Scope

- This skill reconstructs input pages; it is not a from-scratch deck content generator.
- Every page must be rebuilt by a page subagent; there is no parent-agent manual reconstruction fallback when subagents are unavailable.
- Complex visual assets need `$imagegen`; if image generation/editing is unavailable, affected pages are treated as blockers.
- Complex photos, illustrations, textures, and hand-drawn decorations are usually movable image assets, not internally editable PowerPoint objects.
- Tables, charts, and diagrams should only be rebuilt as native objects when confidence is high enough; otherwise keep them as assets and document the limit.
- Visual similarity is not enough. Acceptance should check package structure, editable text coverage, asset provenance, preview, and diff.

## Repository Layout

```text
.
├── .github/                              # GitHub workflows and repository checks
├── skills/                               # Codex skill package directory
│   └── image-to-editable-ppt/            # Installable image-to-editable-ppt skill
│       ├── SKILL.md                      # Skill entrypoint and execution rules
│       ├── requirements.txt              # Python dependencies used by local scripts
│       ├── agents/                       # Skill metadata for Codex UI
│       ├── references/                   # Reconstruction, state-machine, and QA references
│       └── scripts/                      # Helper scripts for normalization, assembly, and validation
├── AGENTS.md                             # Repository-level collaboration and editing rules
├── CHANGELOG.md                          # User-visible change log
├── LICENSE                               # Open-source license
├── README.md                             # Chinese documentation
└── README_en.md                          # English documentation
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ningzimu/image-to-editable-ppt-skill&type=Date)](https://www.star-history.com/#ningzimu/image-to-editable-ppt-skill&Date)

## Community

Scan the QR code to join the Skill community group, share usage experience, report issues, and receive update notices.

<img src="assets/image-to-editable-ppt-community-qr.png" alt="Image to Editable PPT Skill community QR code" width="220">

## License

MIT
