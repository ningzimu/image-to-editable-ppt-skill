# Image to Editable PPT Skill

[![中文](https://img.shields.io/badge/docs-中文-red)](README.md) [![GitHub stars](https://img.shields.io/github/stars/ningzimu/image-to-edited-ppt-skill?style=flat&logo=github&label=stars)](https://github.com/ningzimu/image-to-edited-ppt-skill/stargazers) [![GitHub forks](https://img.shields.io/github/forks/ningzimu/image-to-edited-ppt-skill?style=flat&logo=github&label=forks)](https://github.com/ningzimu/image-to-edited-ppt-skill/forks)

A Codex skill for converting images, PDFs, and image-based PPT/PPTX files into editable PowerPoint `.pptx` output. It normalizes inputs into per-page source images, then rebuilds editable text, simple shapes, and positioned visual assets.

The skill rebuilds readable text as editable PowerPoint text boxes whenever practical, keeps simple geometry as native shapes, and records complex visual elements as independent image assets with provenance.

## Highlights

- Convert one image, multiple images, a multi-page PDF, or an image-based PPT/PPTX into editable `.pptx`.
- Use Codex subagents for per-page parallel reconstruction in multi-page jobs; the parent agent performs final QA and assembly.
- Preserve PDF/PPT/PPTX page order; multiple image input does not promise relative ordering.
- Preserve PPT/PPTX speaker notes on matching output slides without modifying note text.
- Use a manifest to describe slide size, text boxes, shapes, image assets, and provenance.
- Build PPTX files, previews, visual diffs, and validation reports with local scripts.
- Clearly separates full-slide image wrapping from real editable reconstruction.
- Supports hybrid reconstruction: editable text, simple native shapes, and independently movable raster/SVG assets.

## Input And Output Contract

Output is always a PowerPoint `.pptx` file:

| Input | Output |
| --- | --- |
| 1 image | 1-slide `.pptx` |
| Multiple images | Multi-slide `.pptx`, one slide per image; relative image order is not guaranteed |
| Multi-page PDF | Multi-slide `.pptx`; PDF page N maps to output slide N |
| PPT/PPTX | `.pptx` with the same slide count; source slide N maps to output slide N |

Speaker notes are handled only for PPT/PPTX input. The parent agent copies notes to matching output slides unchanged: no translation, summarization, rewriting, or subagent processing.

## Install

Recommended Codex installation:

```bash
npx -y skills@latest add ningzimu/image-to-edited-ppt-skill \
  --skill image-to-editable-ppt \
  --agent codex \
  --global
```

Restart Codex after installation.

For local development, symlink the skill directory:

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/image-to-edited-ppt-skill/skills/image-to-editable-ppt \
  ~/.codex/skills/image-to-editable-ppt
```

Before running dependency-based scripts for the first time, bootstrap the local skill runtime:

```bash
python3 skills/image-to-editable-ppt/scripts/image_to_editable_ppt_runtime.py bootstrap
python3 skills/image-to-editable-ppt/scripts/image_to_editable_ppt_runtime.py doctor
```

The runtime is created at `skills/image-to-editable-ppt/.venv`. Image-based `.pptx` input uses lightweight OOXML/zip parsing to extract one full-slide image per slide, so it does not require LibreOffice.

Dependency split:

- Python packages are installed into the skill-local `.venv` for portability and isolation.
- PDF rendering uses PyMuPDF.
- Image processing uses Pillow.
- Image-based `.pptx` input uses standard-library slide relationship parsing and requires exactly one full-slide embedded picture per slide.
- Legacy `.ppt` files and native/complex `.pptx` files are outside the lightweight path; export them to PDF or per-slide images first.

## Usage

Use `$image-to-editable-ppt` to explicitly select this skill, then provide the source file or files:

```text
$image-to-editable-ppt convert /path/to/slide.png into an editable PowerPoint.
$image-to-editable-ppt convert /path/to/a.png and /path/to/b.png into an editable PowerPoint.
$image-to-editable-ppt convert /path/to/deck.pdf into an editable PowerPoint.
$image-to-editable-ppt convert /path/to/image-based.pptx into an editable PowerPoint and preserve speaker notes.
```

The normal workflow is:

1. Create an isolated job folder and normalize inputs into `pages/page_NNN/source.png`.
2. Dispatch multi-page jobs to per-page subagents.
3. Build one page manifest per page with editable text, simple shapes, and positioned image assets.
4. Assemble the final `.pptx`, copy PPT/PPTX notes when present, and run deck validation.
5. Repair the smallest failing scope if validation or visual QA finds issues.

## Script Entrypoints

These scripts live in `skills/image-to-editable-ppt/scripts/`:

- `image_to_editable_ppt_runtime.py`: Create the local `.venv`, install dependencies, and check Python packages plus optional tools.
- `prepare_inputs.py`: Create a job folder, normalize images/PDF/PPT/PPTX into `pages/page_NNN/source.png`, and write `deck_manifest.json`.
- `build_pptx_from_manifest.py`: Assemble `.pptx` output from either a single-page `manifest.json` or a multi-page `deck_manifest.json`.
- `validate_pptx.py`: Validate PPTX package structure, slide count, manifests, asset provenance, text coverage, and speaker-note hashes.
- `render_diff.py`, `split_alpha_components.py`, and `crop_image_asset.py`: Support preview, diff, and asset-splitting workflows.

Example:

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

## Output Layout

Use one isolated output directory per conversion. All intermediate files and final outputs stay inside it:

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

`output/` is ignored by Git. Put curated README or documentation examples under `assets/`.

## Scope

- This skill reconstructs input pages; it is not a from-scratch deck content generator.
- Complex photos, illustrations, textures, and hand-drawn decorations are usually movable image assets, not internally editable PowerPoint objects.
- Tables, charts, and diagrams should only be rebuilt as native objects when confidence is high enough; otherwise keep them as assets and document the limit.
- Image-based `.pptx` input supports only one full-slide embedded picture per slide; export legacy `.ppt` or native/complex `.pptx` files to PDF or per-slide images first.
- Visual similarity is not enough. Acceptance should check package structure, editable text coverage, asset provenance, preview, and diff.

## License

MIT
