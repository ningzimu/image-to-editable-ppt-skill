# Standard Workflow

This page describes the complete conversion process from input to final `.pptx`, so you can understand what the AI is doing and what each stage produces.

## End-to-End Process

1. **Create a task directory and normalize the input**: create an isolated task directory, normalize the input (images, PDF, or image-based PowerPoint) into `pages/page_NNN/source.png`, detect whether built-in `image_gen.imagegen` is available, and record the image backend selected for the run.
2. **Create OCR text annotations (when a Token is configured)**: submit the entire input to OCR as a batch task. OCR produces page-level text annotations—bounding boxes, measured font sizes, font-size groups, and recognized text—which guide measurement-based text reconstruction.
3. **Dispatch pages**: for a one-page input, the main agent claims the page with `editppt run dispatch --local` and reconstructs it locally. For multi-page input, pages are dispatched in batches of up to `max_concurrent_pages` to page workers for parallel reconstruction.
4. **Reconstruct and self-check each page**: each reconstructor owns its page directory and performs reconstruction, source comparison, and page-local corrections, potentially over multiple iterations. It creates a manifest and rebuilds editable text, simple shapes, and image assets. When needed, it uses the image backend to separate foreground and background elements or extract assets.
5. **Record state**: `editppt` commands record dispatch state, page results, and acceptance state, so progress can be inspected at any time.
6. **Assemble and validate the final deck**: the main agent runs `editppt run finalize`, reads each accepted `manifest.json` in page order, rebuilds the final `.pptx`, copies speaker notes from `.pptx` inputs, and runs deck validation.

## Input-to-Output Mapping

The output is always a PowerPoint `.pptx`:

| Input | Output |
| --- | --- |
| One image | One-slide `.pptx` |
| Multiple images | Multi-slide `.pptx`, one slide per image in the order provided |
| Multi-page PDF | Multi-slide `.pptx`, with PDF page N mapped to output slide N |
| Image-based PowerPoint | A `.pptx` with the same slide count, with source slide N mapped to output slide N |

Only `.pptx` inputs include speaker-note handling. The main agent copies notes unchanged to the corresponding output slides without translation, summarization, rewriting, or page-worker processing.

## Output Directory Structure

Each conversion uses an isolated output directory that contains all intermediate files and final results:

```text
output/image-to-editable-ppt/{job-id}/        # Conversion task directory
├── input/                                    # Copy of the original input
├── deck_manifest.json                        # Page list and output configuration for the deck
├── page_jobs.json                            # Dispatch and completion state for each page
├── run_state.json                            # Overall task state
├── notes_manifest.json                       # Speaker-note extraction and mapping records
├── final/                                    # Final output directory
│   ├── {origin}_edited.pptx                  # Final editable PPTX
│   ├── validation.json                       # Final deck validation results
│   └── run_summary.json                      # Conversion summary
└── pages/                                    # Per-page reconstruction workspaces
    ├── page_001/                             # Workspace for slide 1
    │   ├── source.png                        # Normalized source image
    │   ├── page_request.json                 # Page request and image backend
    │   ├── worker-prompt.md                  # Prompt generated for the page reconstructor
    │   ├── imagegen-jobs.json                # Image generation/edit calls and results for this page
    │   ├── assets/                           # Separate image assets extracted from this page
    │   ├── page.pptx                         # Single-slide PPTX for this page
    │   ├── preview.png                       # Reconstruction preview
    │   ├── split_assets_contact.png          # Contact sheet for inspecting separated assets
    │   ├── manifest.json                     # Text, shape, and asset descriptions for this page
    │   ├── validation.json                   # Page validation results
    │   └── page_result.json                  # Page output index
    └── page_002/                             # Workspace for subsequent slides
        └── ...
```

## Limitations

- This skill reconstructs an input page as editable objects; it does not generate a new presentation from scratch. That is the responsibility of [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill).
- Complex visual elements such as photos, illustrations, textures, and hand-drawn decoration can usually be moved only as separate image assets; their internal objects are not guaranteed to be editable.
- For structured regions such as tables, charts, and flowcharts, the skill prioritizes preserving editable semantics. When confidence is low, it keeps the region as an asset and explains the choice in the validation report.
- Some image elements and text positions may be slightly offset. A 100% match to the source page is not guaranteed.
- If the defined image generation or editing path cannot produce a compliant asset, the page fails or remains blocked. The skill does not downgrade the missing asset to a warning, nor does it record, finalize, or deliver an incomplete substitute.
- Visual similarity does not guarantee editability. Final evaluation should consider the PPTX structure, text coverage, asset provenance, and preview/diff together.
