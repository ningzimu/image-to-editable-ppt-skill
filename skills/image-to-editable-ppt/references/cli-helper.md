# CLI Helper

This is the `editppt` command manual. It reduces hand-written scripts, hand-written state JSON, and repeated trial-and-error.

Usage principles:

- If a deterministic action can be completed with `editppt`, call the CLI directly instead of rewriting it as a temporary Python script.
- When full parameters are needed, read `editppt <command> --help` or `editppt image <command> --help` first.

## Command Tree

```text
editppt                         - top-level CLI for setup, run orchestration, image assets, and formulas
|-- setup                       - create or verify the user-level runtime home and config files
|-- doctor                      - check local runtime health, dependencies, and backend availability
|-- config                      - write user-level OpenAI-compatible image API fallback settings
|-- prepare                     - normalize image/PDF/PPTX inputs into a run directory and page jobs
|-- run                         - advance run state and coordinate page workers
|   |-- next                    - read current run state and return the next required action
|   |-- status                  - inspect run/page state for debugging or manual checks
|   |-- backend                 - override or inspect the run-level image backend contract
|   |-- dispatch                - record that a real page worker/subagent was spawned
|   |-- record                  - validate required page outputs and record page result hashes
|   `-- finalize                - rebuild the final PPTX from recorded page manifests and validate it
|-- image                       - generate, edit, import, and process bitmap assets
|   |-- generate                - create a new image from a text prompt
|   |-- edit                    - edit a source image for clean bases or source-faithful asset sheets
|   |-- batch                   - run multiple generate/edit jobs from JSONL with concurrency
|   |-- import                  - copy a selected image into the page dir and record provenance
|   `-- process-sheet           - split a chroma-key asset sheet into transparent assets
`-- formula                     - render formula assets from agent-transcribed LaTeX
    `-- render-latex            - render LaTeX into SVG/PNG/PDF plus a manifest fragment
```

## Common Help Entrypoints

```bash
editppt --help
editppt run --help
editppt image --help
editppt image edit --help
editppt image batch --help
editppt formula render-latex --help
```

`editppt image` automatically chooses the image backend: Codex OAuth first, then OpenAI-compatible API credentials from `~/.editppt/config.yaml` or environment variables if OAuth is unavailable.

## Skill Script Commands

```bash
python <skill-root>/scripts/build-page-worker-prompt.py <run> --page page_001 --out <absolute-run-dir>/pages/page_001/worker-prompt.md
```

Purpose: generate a page-worker prompt from the skill-local `prompts/page-worker.md` template. This is a skill script, not an `editppt` CLI command, because it reads skill documentation and references.

The script writes the prompt file and prints JSON with `prompt_file`, `page_id`, and `dispatch_command_template`. It does not create a page worker and must run before `editppt run dispatch`.

## Pre-Run Check

The `editppt` CLI is a required runtime surface for this skill. First confirm that the CLI is available:

```bash
editppt --help
```

If the shell returns command not found, or if the skill was just updated, install the skill-local CLI in editable mode:

```bash
pipx install --force --editable <skill-root>/cli
```

`<skill-root>` is the `image-to-editable-ppt` directory that contains `SKILL.md`. On Windows, use the same directory's `cli` subdirectory path.

After the CLI is available, run local runtime checks:

```bash
editppt setup
editppt doctor
editppt config --api-key "<key>" --base-url "<openai-compatible-base-url>" --model "<image-model>"
```

Write `editppt config` only when API fallback is needed or when the user explicitly provides a third-party image API. Do not write API keys into the project directory, run directory, prompts, or manifests.

## Common Single-Page Commands

```bash
editppt prepare input.png
```

Purpose: normalize a single image into a run directory and generate `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, `pages/page_001/source.png`, and `pages/page_001/page_request.json`.

```bash
editppt run record <run> --page page_001 --agent-id main
```

Purpose: after the parent agent directly completes the current single page, self-checks it, and writes all page-local outputs, validate `page.pptx` against `manifest.json` and record that page result.

```bash
editppt run finalize <run>
```

Purpose: after recording is complete, rebuild and validate the final PPTX from the recorded page manifests in page order.

## Common Multi-Page Commands

```bash
editppt prepare input.pdf
```

Purpose: normalize a PDF, PPTX, or multiple images into a multi-page run directory and generate `pages/page_NNN/source.png` plus `page_request.json` for each page.

```bash
editppt run next <run> --json
```

Purpose: read current run state and return the next stage. `stage=rebuild_page` applies only to an actual single-page input, where the parent agent may complete the page directly. `stage=dispatch_pages` applies to multi-page inputs, where the parent agent reads `suggested_pages` and must dispatch page workers. `stage=wait` means wait for dispatched pages to complete. `stage=finalize` means proceed to final assembly.

For multi-page inputs, the parent agent must not create page reconstruction artifacts and must not write `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, or `page_result.json`. These files are generated by page workers inside their own `pages/page_NNN/` directories.

Generate the page-worker prompt with the skill script before spawning a worker:

```bash
python <skill-root>/scripts/build-page-worker-prompt.py <run> --page page_001 --out <absolute-run-dir>/pages/page_001/worker-prompt.md
```

```bash
editppt run dispatch <run> --page page_001 --agent-id <worker-id> --prompt-file <absolute-run-dir>/pages/page_001/worker-prompt.md
```

Purpose: record that a page has been dispatched to a worker. This command only records a dispatch that has really happened; first create the worker with the current environment's available subagent/multi-agent tool, then run this command. `--prompt-file` uses the same absolute path as the prompt-builder `--out`.

```bash
editppt run record <run> --page page_001 --agent-id <worker-id>
```

Purpose: after the page worker writes `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, and `page_result.json`, validate `page.pptx` against `manifest.json` and record that page result. Missing `box_px` / `points_px` on positioned objects is a page failure.

```bash
editppt run finalize <run>
```

Purpose: after all pages are recorded, rebuild, validate, and output the final PPTX. Final assembly reads each recorded `pages/page_NNN/manifest.json` in page order and generates the final deck from those manifests. `page.pptx` remains a page-local deliverability artifact, not the final assembly input.

Concurrency slots come from `page_jobs.json.max_concurrent_pages`; the default is 6. In normal flow, prefer `editppt run next` to determine the next action. `editppt run status` is only for debugging or manual inspection.

## Image Backend Commands

Generate a new image:

```bash
editppt image generate \
  --prompt-file prompt.txt \
  --out pages/page_001/assets/support.png
```

Create a clean base or foreground asset sheet from the source image:

```bash
editppt image edit \
  --image pages/page_001/source.png \
  --prompt-file clean-base.prompt.txt \
  --out pages/page_001/assets/clean-base.png

editppt image edit \
  --image pages/page_001/source.png \
  --prompt-file asset-sheet.prompt.txt \
  --out pages/page_001/assets/asset-sheet.png
```

Batch generate or edit:

```bash
editppt image batch \
  --input pages/page_001/image-jobs.jsonl \
  --out-dir pages/page_001/assets \
  --concurrency 6
```

A JSONL job without `image` / `images` is a generate job. A job with `image` / `images` is an edit job.

## Asset Processing Commands

Record a selected image output:

```bash
editppt image import pages/page_001 \
  --job-id icon-sheet \
  --source-image /tmp/generated.png \
  --dest assets/icon-sheet.png \
  --role asset_sheet
```

Process a chroma-key asset sheet:

```bash
editppt image process-sheet pages/page_001 \
  --job-id icon-sheet \
  --asset-sheet-source assets/icon-sheet.png \
  --assets-dir assets/icons
```

The asset sheet key color is determined by the generation prompt. `process-sheet` samples the key color from the image edge. Cyan, green, magenta, and similar colors can all be candidates. Prefer a pure color that does not appear in the current assets and is far from the subject colors. If background removal makes the subject fade, cuts off edges, or leaves key-color remnants, first regenerate the asset sheet with a new key color.

## Formula Commands

```bash
editppt formula render-latex pages/page_001 \
  --tex "\\sum_{i \\in N} p_{ij}x_{ij} \\ge a_j u_j" \
  --out assets/formula_001.svg \
  --box 100,120,360,80 \
  --id formula_001 \
  --fragment assets/formula_001.fragment.json
```

The agent transcribes the formula from the source into LaTeX. The CLI only renders it into an image asset and manifest fragment.
