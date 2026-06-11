# Changelog

Release notes are generated from this file. Keep changelog entries in English.

## Unreleased

## 0.2.0

### Features

- Add the installable skill-local `editppt` CLI package with setup, doctor, config, prepare, run, image, and formula command groups. (#3)
- Add a unified image backend through `editppt image`, using Codex OAuth when available and OpenAI-compatible API fallback credentials from `~/.editppt/config.yaml`. (#3)
- Add concurrent `editppt image batch` support for generate/edit jobs, including reference-image edit inputs. (#3)
- Add `editppt formula render-latex` for rendering LaTeX formulas into PPT image assets and manifest fragments. (#3)
- Add source-aspect-preserving slide preparation with automatic custom slide canvases and content boxes for non-widescreen inputs. (#3)
- Add `editppt page hints`: dependency-free text-line detection and measurement on `source.png` (per-tile binarization, bridge-tolerant XY-cut segmentation, ink metrics). It outputs advisory `text_hints.json` and a labeled `text_hints.png` overlay so the page author fills `text_boxes` positions and font sizes from measurement instead of visual estimation. (#5)
- Distribute text hints during prepare: every page directory receives `text_hints.json` and the labeled `text_hints.png` overlay alongside its `source.png`, so page workers start with measurements in place. With a PaddleOCR-VL token (`PADDLE_OCR_TOKEN` env var or `~/.editppt/config.yaml`), every input type is OCR'd in a single batch job — PDFs are submitted directly and image/PPTX page sources are bundled into a temporary PDF first — with text blocks locally re-measured and rescaled to each page's resolution. Without a token or on failure, the built-in offline detector runs per page; pages where the OCR layout model collapses (dense diagrams classified as one figure, <=2 text lines while the offline detector finds 6+) automatically fall back to the offline result. `--no-text-hints` skips the step. (#5)
- Add `editppt run hints` to regenerate a prepared run's text hints in place (e.g. right after configuring a PaddleOCR token mid-run), and make the missing-token notice an explicit ask-the-user-once checkpoint before page reconstruction instead of a fire-and-forget tip. (#5)
- Add `editppt config --paddle-ocr-token` and first-use guidance: doctor reports the active text-hints backend and, when no token is configured, prepare and doctor point to the token application page (https://aistudio.baidu.com/account/accessToken). The token is stored masked in `~/.editppt/config.yaml` alongside the image API credentials. (#5)
- Snap measured font sizes to design levels: detected lines are clustered into size groups (same-level text gets exactly one font size instead of per-line jitter), exposed as `size_group` in the hints output. (#5)
- Trust measured font sizes in the deterministic builder: text boxes tagged `"font_size_source": "measured"` are clamped only at the geometric fit limit instead of the conservative 0.9 safety shrink, which made correctly sized text systematically smaller than the source. Hand-written boxes keep the existing conservative behavior. (#5)
- Add `editppt run reset`: return a failed or stuck page to `pending`, clearing its dispatch and result records so a new worker can be dispatched. This closes the previously dead-ended failure paths — a worker returning `passed: false`, a rejected record, or a lost worker. (#5)
- Add `editppt page build`, `editppt page contact-sheet`, and `editppt page validate`: page workers build `page.pptx`/`preview.png` from `manifest.json`, create the origin-versus-preview contact sheet, and pre-check the page with the same manifest-contract checks `run record` runs — through documented CLI commands instead of undocumented runtime scripts. (#5)

### Improvements

- Move deterministic runtime code from loose skill scripts into the self-contained `editppt` CLI package and remove legacy script entrypoints from the installable skill root. (#3)
- Rework the workflow around CLI-managed run state: `editppt prepare`, `editppt run next`, `prompt`, `dispatch`, `record`, and `finalize`. (#3)
- Dispatch multi-page inputs directly to page workers according to runtime concurrency slots, with a default concurrency of 6. (#3)
- Rebuild the final PPTX from recorded page manifests during `editppt run finalize`, making `manifest.json` the authoritative final assembly source. (#3)
- Validate each page PPTX against its page manifest during `editppt run record` so page-local outputs cannot bypass the manifest contract. (#3)
- Require source-pixel coordinates for positioned manifest objects and reject manifests that omit required `box_px`, `points_px`, or `polygon_px` fields. (#3)
- Add deterministic text fitting in the manifest builder to clamp oversized first-draft text boxes before preview and PPTX output. (#3)
- Route foreground bitmap assets through source-faithful asset sheets and remove the public source-crop image workflow. (#3)
- Store only page artifacts, hashes, and validation outputs in page result records. (#3)
- Simplify page correction flow so page reconstructors fix page-local issues before record instead of creating repair queues. (#3)
- Expose image backend usage, asset-sheet processing, formula rendering, and run orchestration guidance through agent-friendly CLI help. (#3)
- Move page-worker prompt assembly out of the installable CLI and into a skill-local prompt builder script. (#5)
- Remove the `editppt run prompt` subcommand so the CLI no longer reads skill prompt templates or reference files. (#5)
- Keep CLI environment diagnostics scoped to CLI config, dependencies, and image backend readiness without requiring skill-root discovery. (#5)
- Replace path-like prompt placeholders with explicit `{{NAME}}` tokens and fail the prompt build when any placeholder remains unfilled. (#5)
- Dispatch every page to a page worker, including single-page inputs: `editppt run next` no longer returns a `rebuild_page` stage and `editppt run record` no longer accepts direct main-agent recording from `pending`, so single-page and multi-page runs follow one identical flow and one prompt contract. (#5)
- Reject non-deliverable pages at record time: `editppt run record` fails with a `run reset` hint when `validation.json` does not contain top-level `passed: true`, so the `recorded` state always means deliverable and finalize can no longer be reached with failed pages aboard. (#5)

### Fixes

- Resolve `editppt image process-sheet --asset-sheet-source` relative paths from the page directory. (#3)
- Accept structured `text_inventory` entries during PPTX validation. (#3)
- Align single-page direct recording, page-worker prompt paths, and asset-sheet helper examples with the actual `editppt` runtime state machine. (#3)
- Reject recorded or final page manifests whose positioned objects would otherwise fall back to default top-left locations. (#3)
- Preserve custom deck size metadata when finalizing decks from manifests instead of forcing all outputs into widescreen mode. (#3)
- Fix page-worker prompt truncation: a nested code fence in `prompts/page-worker.md` cut the generated worker prompt off before the manifest field requirements, the pre-return checklist, and the return format. The prompt builder now matches the last closing fence so nested fences cannot truncate the template. (#5)

### Documentation

- Translate installable skill documentation and agent metadata to English. (#3)
- Rewrite the skill workflow and page-worker prompt around the `editppt` CLI-first contract. (#3)
- Replace legacy architecture, state-machine, subagent, repair, and imagegen references with a shorter `cli-helper.md`, manifest schema, page decision tree, and QA rubric. (#3)
- Document that page manifests must be sufficient to rebuild page PPTX files and final decks. (#3)
- Document source-pixel coordinate requirements and deterministic text-fitting behavior for page manifests. (#3)
- Require absolute worker prompt paths, real page-worker dispatch for multi-page runs, and top-level `passed` in page validation outputs. (#3)
- Update Chinese and English README files for CLI installation, update instructions, backend configuration, multi-agent usage, and reconstruction limits. (#3)
- Clarify that image API fallback configuration is AI-assisted, without manual CLI installation or key-configuration commands in the READMEs. (#5)
- Document the OCR token in both READMEs: text size/position correction relies on a free PaddleOCR-VL token (application URL, config command, free-quota reassurance), replacing the outdated "no third-party OCR dependency" claim; the offline detector remains the degraded fallback. (#5)
- Lock the three-step execution order in the worker prompt and decision tree: text hints belong to step 3 and are consumed only after background and foreground decisions, with step-1/2 image jobs submitted first so the order costs no wall-clock time. (#5)
- Clarify that final deck assembly rebuilds from recorded page manifests rather than concatenating page-level PPTX files. (#5)
- Document the skill-local page-worker prompt builder script in the skill workflow and CLI helper. (#5)
- Restructure skill documentation around single-ownership: every rule lives in exactly one file, other files carry pointers. The page decision tree absorbs the QA rubric (now a Final Self-Check plus a Fix versus Warning section), the manifest schema becomes the only home for JSON field contracts, the CLI helper becomes a pure command manual, and the worker prompt shrinks to hard-rule reminders plus pointers with a mandatory read-references-first instruction. (#5)
- Drop SKILL.md from the page-worker required reading list so workers load only page-level references instead of the parent orchestration contract. (#5)
- Broaden skill description triggers, add a CLI availability check to the entry contract, and document non-pipx install fallbacks (`uv tool install`, `pip install --user`). (#5)
- Document the failure-handling loop in SKILL.md Phase 3: never re-dispatch a page unchanged, diagnose repeated same-root-cause failures autonomously instead of pushing debugging questions to the user, and define the worker failure contract — a failed page returns at minimum `validation.json` (`passed: false` with the concrete reason) plus `page_result.json`, and leftover artifacts from a failed attempt are untrusted by the next worker. (#5)
- Document the `asset_provenance` field contract (the five allowed `source_type` values, required `source` and `provenance_note`) and the validator's substring-level keyword scanning of inventory and provenance text. (#5)
- Treat formula rendering blocked by missing local TeX tooling as a recorded warning with `passed: true` instead of an undefined pass state. (#5)
- Add a skill documentation architecture spec to AGENTS.md: design principles (single-ownership, reader-role split, docs-and-CLI-move-together) and per-file responsibility boundaries for future contributors. (#5)

## 0.2.0-beta.2

### Features

- Add `editppt page hints`: dependency-free text-line detection and measurement on `source.png` (per-tile binarization, bridge-tolerant XY-cut segmentation, ink metrics). It outputs advisory `text_hints.json` and a labeled `text_hints.png` overlay so the page author fills `text_boxes` positions and font sizes from measurement instead of visual estimation. (#5)
- Distribute text hints during prepare: every page directory receives `text_hints.json` and the labeled `text_hints.png` overlay alongside its `source.png`, so page workers start with measurements in place. With a PaddleOCR-VL token (`PADDLE_OCR_TOKEN` env var or `~/.editppt/config.yaml`), every input type is OCR'd in a single batch job — PDFs are submitted directly and image/PPTX page sources are bundled into a temporary PDF first — with text blocks locally re-measured and rescaled to each page's resolution. Without a token or on failure, the built-in offline detector runs per page; pages where the OCR layout model collapses (dense diagrams classified as one figure, <=2 text lines while the offline detector finds 6+) automatically fall back to the offline result. `--no-text-hints` skips the step. (#5)
- Add `editppt run hints` to regenerate a prepared run's text hints in place (e.g. right after configuring a PaddleOCR token mid-run), and make the missing-token notice an explicit ask-the-user-once checkpoint before page reconstruction instead of a fire-and-forget tip. (#5)
- Add `editppt config --paddle-ocr-token` and first-use guidance: doctor reports the active text-hints backend and, when no token is configured, prepare and doctor point to the token application page (https://aistudio.baidu.com/account/accessToken). The token is stored masked in `~/.editppt/config.yaml` alongside the image API credentials. (#5)
- Snap measured font sizes to design levels: detected lines are clustered into size groups (same-level text gets exactly one font size instead of per-line jitter), exposed as `size_group` in the hints output. (#5)
- Trust measured font sizes in the deterministic builder: text boxes tagged `"font_size_source": "measured"` are clamped only at the geometric fit limit instead of the conservative 0.9 safety shrink, which made correctly sized text systematically smaller than the source. Hand-written boxes keep the existing conservative behavior. (#5)
- Add `editppt run reset`: return a failed or stuck page to `pending`, clearing its dispatch and result records so a new worker can be dispatched. This closes the previously dead-ended failure paths — a worker returning `passed: false`, a rejected record, or a lost worker. (#5)
- Add `editppt page build`, `editppt page contact-sheet`, and `editppt page validate`: page workers build `page.pptx`/`preview.png` from `manifest.json`, create the origin-versus-preview contact sheet, and pre-check the page with the same manifest-contract checks `run record` runs — through documented CLI commands instead of undocumented runtime scripts. (#5)

### Fixes

- Fix page-worker prompt truncation: a nested code fence in `prompts/page-worker.md` cut the generated worker prompt off before the manifest field requirements, the pre-return checklist, and the return format. The prompt builder now matches the last closing fence so nested fences cannot truncate the template. (#5)

### Improvements

- Move page-worker prompt assembly out of the installable CLI and into a skill-local prompt builder script. (#5)
- Remove the `editppt run prompt` subcommand so the CLI no longer reads skill prompt templates or reference files. (#5)
- Keep CLI environment diagnostics scoped to CLI config, dependencies, and image backend readiness without requiring skill-root discovery. (#5)
- Replace path-like prompt placeholders with explicit `{{NAME}}` tokens and fail the prompt build when any placeholder remains unfilled. (#5)
- Dispatch every page to a page worker, including single-page inputs: `editppt run next` no longer returns a `rebuild_page` stage and `editppt run record` no longer accepts direct main-agent recording from `pending`, so single-page and multi-page runs follow one identical flow and one prompt contract. (#5)
- Reject non-deliverable pages at record time: `editppt run record` fails with a `run reset` hint when `validation.json` does not contain top-level `passed: true`, so the `recorded` state always means deliverable and finalize can no longer be reached with failed pages aboard. (#5)

### Documentation

- Clarify that image API fallback configuration is AI-assisted, without manual CLI installation or key-configuration commands in the READMEs. (#5)
- Document the OCR token in both READMEs: text size/position correction relies on a free PaddleOCR-VL token (application URL, config command, free-quota reassurance), replacing the outdated "no third-party OCR dependency" claim; the offline detector remains the degraded fallback. (#5)
- Lock the three-step execution order in the worker prompt and decision tree: text hints belong to step 3 and are consumed only after background and foreground decisions, with step-1/2 image jobs submitted first so the order costs no wall-clock time. (#5)
- Clarify that final deck assembly rebuilds from recorded page manifests rather than concatenating page-level PPTX files. (#5)
- Document the skill-local page-worker prompt builder script in the skill workflow and CLI helper. (#5)
- Restructure skill documentation around single-ownership: every rule lives in exactly one file, other files carry pointers. The page decision tree absorbs the QA rubric (now a Final Self-Check plus a Fix versus Warning section), the manifest schema becomes the only home for JSON field contracts, the CLI helper becomes a pure command manual, and the worker prompt shrinks to hard-rule reminders plus pointers with a mandatory read-references-first instruction. (#5)
- Drop SKILL.md from the page-worker required reading list so workers load only page-level references instead of the parent orchestration contract. (#5)
- Broaden skill description triggers, add a CLI availability check to the entry contract, and document non-pipx install fallbacks (`uv tool install`, `pip install --user`). (#5)
- Document the failure-handling loop in SKILL.md Phase 3: never re-dispatch a page unchanged, diagnose repeated same-root-cause failures autonomously instead of pushing debugging questions to the user, and define the worker failure contract — a failed page returns at minimum `validation.json` (`passed: false` with the concrete reason) plus `page_result.json`, and leftover artifacts from a failed attempt are untrusted by the next worker. (#5)
- Document the `asset_provenance` field contract (the five allowed `source_type` values, required `source` and `provenance_note`) and the validator's substring-level keyword scanning of inventory and provenance text. (#5)
- Treat formula rendering blocked by missing local TeX tooling as a recorded warning with `passed: true` instead of an undefined pass state. (#5)
- Add a skill documentation architecture spec to AGENTS.md: design principles (single-ownership, reader-role split, docs-and-CLI-move-together) and per-file responsibility boundaries for future contributors. (#5)

## 0.2.0-beta.1

### Features

- Add the installable skill-local `editppt` CLI package with setup, doctor, config, prepare, run, image, and formula command groups. (#3)
- Add a unified image backend through `editppt image`, using Codex OAuth when available and OpenAI-compatible API fallback credentials from `~/.editppt/config.yaml`. (#3)
- Add concurrent `editppt image batch` support for generate/edit jobs, including reference-image edit inputs. (#3)
- Add `editppt formula render-latex` for rendering LaTeX formulas into PPT image assets and manifest fragments. (#3)
- Add source-aspect-preserving slide preparation with automatic custom slide canvases and content boxes for non-widescreen inputs. (#3)

### Improvements

- Move deterministic runtime code from loose skill scripts into the self-contained `editppt` CLI package and remove legacy script entrypoints from the installable skill root. (#3)
- Rework the workflow around CLI-managed run state: `editppt prepare`, `editppt run next`, `prompt`, `dispatch`, `record`, and `finalize`. (#3)
- Dispatch multi-page inputs directly to page workers according to runtime concurrency slots, with a default concurrency of 6. (#3)
- Rebuild the final PPTX from recorded page manifests during `editppt run finalize`, making `manifest.json` the authoritative final assembly source. (#3)
- Validate each page PPTX against its page manifest during `editppt run record` so page-local outputs cannot bypass the manifest contract. (#3)
- Require source-pixel coordinates for positioned manifest objects and reject manifests that omit required `box_px`, `points_px`, or `polygon_px` fields. (#3)
- Add deterministic text fitting in the manifest builder to clamp oversized first-draft text boxes before preview and PPTX output. (#3)
- Route foreground bitmap assets through source-faithful asset sheets and remove the public source-crop image workflow. (#3)
- Store only page artifacts, hashes, and validation outputs in page result records. (#3)
- Simplify page correction flow so page reconstructors fix page-local issues before record instead of creating repair queues. (#3)
- Expose image backend usage, asset-sheet processing, formula rendering, and run orchestration guidance through agent-friendly CLI help. (#3)

### Fixes

- Resolve `editppt image process-sheet --asset-sheet-source` relative paths from the page directory. (#3)
- Accept structured `text_inventory` entries during PPTX validation. (#3)
- Align single-page direct recording, page-worker prompt paths, and asset-sheet helper examples with the actual `editppt` runtime state machine. (#3)
- Reject recorded or final page manifests whose positioned objects would otherwise fall back to default top-left locations. (#3)
- Preserve custom deck size metadata when finalizing decks from manifests instead of forcing all outputs into widescreen mode. (#3)

### Documentation

- Translate installable skill documentation and agent metadata to English. (#3)
- Rewrite the skill workflow and page-worker prompt around the `editppt` CLI-first contract. (#3)
- Replace legacy architecture, state-machine, subagent, repair, and imagegen references with a shorter `cli-helper.md`, manifest schema, page decision tree, and QA rubric. (#3)
- Document that page manifests must be sufficient to rebuild page PPTX files and final decks. (#3)
- Document source-pixel coordinate requirements and deterministic text-fitting behavior for page manifests. (#3)
- Require absolute worker prompt paths, real page-worker dispatch for multi-page runs, and top-level `passed` in page validation outputs. (#3)
- Update Chinese and English README files for CLI installation, update instructions, backend configuration, multi-agent usage, and reconstruction limits. (#3)

## 0.1.0

### Features

- Expand the image-to-editable-ppt skill to normalize images, PDFs, and PPT/PPTX inputs into page jobs, assemble deck manifests into multi-page PPTX files, and preserve PPT/PPTX speaker notes. (#1)
- Add skill-local runtime management scripts and dependencies for input preparation, deck assembly, and validation. (#1)
- Add page-local artifact helpers for chroma cleanup, asset splitting, PPTX building, validation, and visual QA artifacts. (#1)

### Improvements

- Add deterministic run-state scripts for deck preparation, page status inspection, subagent dispatch/result recording, repair queueing, imagegen result recording, asset-sheet processing, contact-sheet generation, and final deck validation. (#1)
- Add batch-dispatch metadata so the parent agent can respect runtime subagent concurrency limits across multiple dispatch rounds. (#1)
- Consolidate legacy script entrypoints into internal helpers so input normalization, page artifact utilities, and asset cropping are reached through the stable orchestration scripts. (#1)
- Normalize image-based `.pptx` inputs with lightweight OOXML/zip extraction instead of requiring LibreOffice for decks that contain one full-slide image per slide. (#1)
- Document the end-to-end page reconstruction loop, including page classification, source-geometry preservation, chroma-key selection, contact-sheet inspection, and source/preview QA. (#1)

### Fixes

- Reject page manifests that combine a full-slide source raster background with editable text overlays, preventing baked-text overlap from passing validation. (#1)
- Respect per-object `z_index` and round-rectangle previews in PPTX assembly and preview rendering so cleaned backgrounds, native shapes, generated icons, and editable text can be layered independently. (#1)
- Add manifest support for rotated editable text boxes and dashed editable lines for chart axes, gridlines, and timelines. (#1)
- Require page manifests to record font calibration, visual inventory matching, background strategy checks, and shape-corner checks before validation passes. (#1)
- Require source evidence for `roundRect` shapes so straight-corner containers are not silently rebuilt as rounded rectangles. (#1)
- Improve preview font scaling and allow source-derived raster provenance for small non-text visual assets that need higher source consistency. (#1)

### Documentation

- Add the generated codex-ppt and image-to-editable-ppt introduction PDF to the README tips. (#1)
- Add the kidney cancer MDT infographic as a README conversion example. (#1)
- Add Skill community group QR code sections to the Chinese and English READMEs. (#1)
- Add repository README files, contribution guidance, changelog, license, PR template, and lightweight GitHub checks. (#1)
- Add README badges for language switching, GitHub stars, and GitHub forks. (#1)
- Restructure the installable skill docs into a Chinese first-pass stable workflow with focused references, page-worker prompt templates, strict state-machine guidance, and `$imagegen` integration rules. (#1)
- Document mandatory one-subagent-per-page dispatch for multi-image, PDF, and PPT/PPTX conversions, including how to report subagent-dispatch issues. (#1)
- Clarify that dashboard and dense infographic pages require an explicit `image_gen` gate decision, and that style-bearing icons or pictograms must use generated assets. (#1)
- Clarify foreground/background separation for hand-drawn and dense infographic pages so semantic marks are not left only in clean base images. (#1)
- Document that preview-visible crude or placeholder-like icons should trigger targeted `image_gen` asset repair when practical, with unresolved cases recorded as fidelity limits. (#1)
- Remove page readiness status gates from the workflow; subagents must return editable page-level PPTX outputs for assembly and record quality limits separately. (#1)
- Clarify that page subagents are runtime Codex workers dispatched by the parent agent, not named agent types registered by the plugin manifest. (#1)
- Refine the Chinese and English READMEs with clearer positioning, runtime requirements, supported input scope, and reconstruction limits. (#1)
- Clarify source-consistent clean-background generation, including imagegen prompts that preserve original composition, perspective, object placement, color, and lighting. (#1)
- Add README known limitations for Codex-only support, untested third-party API integrations, and model-quality expectations. (#1)
- Add GitHub Release workflow documentation and release zip installation notes. (#1)
- Add a handdrawn project overview image to the Chinese and English README files. (#1)
- Document that reconstructed image elements and text positions may have slight drift and are not guaranteed to be 100% replicas. (#1)
- Add a prominent README pointer to codex-ppt-skill for users who need to generate new PPT decks. (#1)
