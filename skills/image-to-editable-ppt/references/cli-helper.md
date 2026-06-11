# CLI Helper

This is the `editppt` command manual: install check, command tree, and syntax examples. Workflow policy lives in `SKILL.md`; object decisions and text-hints usage live in `references/page-decision-tree.md`; file and field contracts live in `references/manifest-schema.md`.

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
|   |-- reset                   - return a failed or stuck page to pending for re-dispatch
|   |-- hints                   - regenerate per-page text hints for a prepared run
|   `-- finalize                - rebuild the final PPTX from recorded page manifests and validate it
|-- page                        - page-local helpers
|   |-- hints                   - detect and measure text lines for one page directory
|   |-- build                   - build page.pptx and preview.png from manifest.json
|   |-- contact-sheet           - create the origin-versus-preview comparison image
|   `-- validate                - validate page.pptx against manifest.json as run record will
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
editppt page hints --help
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

If `pipx` itself is unavailable, fall back to one of:

```bash
uv tool install --force --editable <skill-root>/cli
python3 -m pip install --user -e <skill-root>/cli
```

`<skill-root>` is the `image-to-editable-ppt` directory that contains `SKILL.md`. On Windows, use the same directory's `cli` subdirectory path.

After the CLI is available, run local runtime checks:

```bash
editppt setup
editppt doctor
editppt config --api-key "<key>" --base-url "<openai-compatible-base-url>" --model "<image-model>"
```

Write `editppt config` only when API fallback is needed or when the user explicitly provides a third-party image API. Do not write API keys into the project directory, run directory, prompts, or manifests.

Optional but recommended on first use: configure a PaddleOCR-VL token. The offline detector only measures text geometry (where and how large); with a token the hints also carry recognized text content and cleaner block boundaries. Store it next to the other credentials:

```bash
editppt config --paddle-ocr-token "<token>"
```

`editppt doctor` reports the current text-hints backend; without a token everything still works through the built-in offline detector. When and how to ask the user about the token — including the application URL and the regenerate step — is defined in `SKILL.md` Phase 1.

## Run Commands

```bash
editppt prepare input.png
editppt prepare input.pdf
```

Purpose: normalize a single image, multiple images, a PDF, or an image-based PPTX into a run directory and generate `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, plus per-page `pages/page_NNN/source.png`, `page_request.json`, and text hints.

```bash
editppt run next <run> --json
```

Purpose: read current run state and return the next stage. `stage=dispatch_pages` lists `suggested_pages` that must each be dispatched to a page worker — single-page inputs dispatch their one page the same way. `stage=wait` means wait for dispatched pages to complete. `stage=finalize` means proceed to final assembly. `stage=configure_backend` appears only when `deck_manifest.json.image_backend` is missing; follow the returned `next_command`.

Generate the page-worker prompt with the skill script before spawning a worker:

```bash
python <skill-root>/scripts/build-page-worker-prompt.py <run> --page page_001 --out <absolute-run-dir>/pages/page_001/worker-prompt.md
```

```bash
editppt run dispatch <run> --page page_001 --agent-id <worker-id> --prompt-file <absolute-run-dir>/pages/page_001/worker-prompt.md
```

Purpose: record that a page has been dispatched to a worker. This command only records a dispatch that has really happened; first create the worker with the current environment's available subagent/multi-agent tool, then run this command. `--prompt-file` uses the same absolute path as the prompt-builder `--out`. `--agent-id` is any stable identifier the parent chooses for this worker (use the spawn tool's id when it provides one); the same id must be reused at `run record`.

```bash
editppt run record <run> --page page_001 --agent-id <worker-id>
```

Purpose: after the page worker writes its required outputs (see `manifest-schema.md`), validate `page.pptx` against `manifest.json` and record the page result. Missing `box_px` / `points_px` on positioned objects is a page failure. The command also fails when `validation.json` does not contain top-level `passed: true` — a failed page is never recorded; fix the root cause, `run reset` the page, and dispatch a new worker.

```bash
editppt run reset <run> --page page_001
```

Purpose: return a dispatched or recorded page to `pending`, clearing its dispatch and result records, so a new worker can be dispatched. Use it when a worker returned a failed page, `run record` rejected the outputs, or a dispatched worker is lost. The failure-handling policy is in `SKILL.md` Phase 3.

```bash
editppt run finalize <run>
```

Purpose: after all pages are recorded, rebuild, validate, and output the final PPTX. Final assembly reads each recorded `pages/page_NNN/manifest.json` in page order; `page.pptx` is a page-local deliverability artifact, not the final assembly input.

## Page Build Commands

These are the worker-side commands for turning a finished `manifest.json` into the required page artifacts. Use them instead of writing any page-local PowerPoint or imaging code.

```bash
editppt page build pages/page_001
```

Purpose: build `page.pptx` and render `preview.png` from `manifest.json` with the deterministic runtime. Optional `--manifest/--out/--preview` override the default file names inside the page directory.

```bash
editppt page contact-sheet pages/page_001
```

Purpose: create `split_assets_contact.png`, the origin-versus-preview comparison image, from `source.png` and `preview.png` in the page directory.

```bash
editppt page validate pages/page_001
```

Purpose: validate `page.pptx` against `manifest.json` with the same manifest-contract checks `editppt run record` will run (record additionally verifies the full artifact set, hashes, and top-level `passed: true`). Run it before returning so manifest-contract failures are fixed inside the page instead of bouncing back from the parent's record step. Optional `--report <file>` writes a JSON report.

## Text Measurement Commands

```bash
editppt run hints <run>
```

Purpose: regenerate `text_hints.json`/`text_hints.png` for every page of a prepared run — for example right after configuring a PaddleOCR token, so the current run gets content-aware hints without re-running prepare.

```bash
editppt page hints pages/page_001
```

Purpose: detect the text lines on one page's `source.png` and write `text_hints.json` (each line's source-pixel `box_px`, measured glyph height, and derived font sizes) plus `text_hints.png`, the source image with every detected line framed and labeled. `editppt prepare` already runs this for every page (PDF inputs are OCR'd in one batch job when a PaddleOCR token is available via the `PADDLE_OCR_TOKEN` environment variable or `~/.editppt/config.yaml`; otherwise the built-in offline detector runs). Use this command only to regenerate hints for a page. How to consume the hints is defined in `page-decision-tree.md` section 3.1.

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

The asset sheet key color is determined by the generation prompt; `process-sheet` samples the key color from the image edge. Key-color selection and when to regenerate a sheet with a different key color are defined in `page-decision-tree.md` section 2.2.

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
