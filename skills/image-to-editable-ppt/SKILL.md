---
name: image-to-editable-ppt
description: Rebuild slide images, image-based or scanned PPT/PPTX files, and PDF decks into object-level editable PowerPoint (.pptx). Use whenever the user provides any visual slide source and wants slides they can edit — "make this PPT editable", "把图片/截图转成可编辑 PPT", "this PDF is a scanned deck, restore it", recreating slides from screenshots, reconstructing slide objects, or preserving speaker notes — even if they do not say "convert". Not for authoring new presentations from scratch.
---
# Image to Editable PPT

## Overview

This skill rebuilds visual slide inputs into object-level editable PowerPoint `.pptx` files.

Inputs can be a single image, multiple images, a PDF, or an image-based PPT/PPTX. The output is always `.pptx`. The goal is not to wrap a full-slide screenshot inside PowerPoint; the goal is to use the `editppt` runtime and page-level prompts to decompose, reconstruct, validate, and assemble editable slides.

## References

Each rule in this skill has exactly one authoritative home; the other files point to it instead of restating it.

- `prompts/page-worker.md`: execution template for page workers — ownership boundary, execution order, required outputs, and return format. The parent agent uses it when generating page-worker prompts.
- `scripts/build-page-worker-prompt.py`: skill-local prompt builder. It reads `prompts/page-worker.md`, fills run/page paths, writes `worker-prompt.md`, and prints the dispatch command template.
- `references/cli-helper.md`: CLI install check (Pre-Run Check), command tree, and command syntax examples. Read it when deciding which `editppt` command to call.
- `references/manifest-schema.md`: the single home for JSON field contracts of deck/page/image artifacts — required manifest fields, positioned-object coordinates, `validation.json`, and `page_result.json` shapes. Read it when writing or validating any run/page file.
- `references/page-decision-tree.md`: the single source of truth for page object decisions — background handling, foreground asset separation, native shapes, formulas, text-hints usage, the final self-check, and the fix-versus-warning split. Read it before reconstructing any page.

## Entry Contract

These parent-level rules are stated once here; page-level rules live in the references above and are not restated in this file.

- The `editppt` CLI is a required runtime surface. If `editppt --help` fails, install it first by following the Pre-Run Check in `references/cli-helper.md` before doing anything else.
- First run `editppt prepare <input...>` to create a run directory. After that, all key state transitions are advanced only through `editppt` commands; never hand-write run/page state JSON. This keeps run state deterministic and resumable.
- Every page — including the only page of a single-page input — is rebuilt by a dispatched page worker. The parent agent only orchestrates and never rebuilds pages itself. If no subagent capability is available, stop and report this to the user; do not degrade into parent-agent page reconstruction.
- The parent agent must not write any page reconstruction artifact — `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, or `page_result.json`. These files may only be produced by the page worker that owns the page directory.
- All image generation, image editing, background repair, transparent bitmap assets, and asset sheets go through `editppt image generate/edit/batch`.
- All page object decisions follow `references/page-decision-tree.md`, including its no-fallback rule for foreground visual objects and its rule that deterministic validation is a structure gate that never waives an object-source decision.
- `manifest.json` is the authoritative page build source: `editppt run record` validates `page.pptx` against it, and `editppt run finalize` rebuilds the final deck from recorded page manifests. Required fields and coordinate contracts are defined in `references/manifest-schema.md`.
- `editppt prepare` writes per-page text measurements (`text_hints.json`/`text_hints.png`). How page workers consume them is defined in `references/page-decision-tree.md` section 3.1.
- Page workers are driven by prompts generated from `prompts/page-worker.md`.

## Roles

The parent agent owns orchestration and user interaction:

- Run `editppt prepare`. The image backend is chosen automatically (Codex OAuth first, then API fallback), so the normal path needs no extra backend configuration command.
- Drive the run with `editppt run next` through dispatch → record → finalize, exactly as the Workflow phases below describe. Single-page inputs follow the same path: one page means one dispatched worker.
- Report progress, the final PPTX path, and the validation result to the user.
- Do not repeat page-level visual QA that page workers already completed; `record` and `finalize` re-validate deterministically.

Each page worker owns exactly one `pages/page_NNN/` directory. Its full contract — ownership boundary, decision order, required outputs, and return format — is the prompt generated from `prompts/page-worker.md`; the rules it follows live in `references/page-decision-tree.md` and `references/manifest-schema.md`.

## Workflow

### Phase 1: Prepare

Read the prepare examples in `references/cli-helper.md` and the run/page file descriptions in `references/manifest-schema.md`.

```bash
editppt prepare <input...>
```

After this completes, there must be a run directory, `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, and each page must have `source.png` plus `page_request.json`.

Prepare also writes per-page text hints. Whenever `editppt doctor` or prepare reports that no PaddleOCR token is configured (offline fallback), ask the user once before dispatching any page: a free token from https://aistudio.baidu.com/account/accessToken stored via `editppt config --paddle-ocr-token <token>` makes the hints content-aware and noticeably improves text fidelity, and `editppt run hints <run>` regenerates the current run's hints in place. Tell the user the free personal quota is currently more than enough for this skill — applying is risk-free with no extra cost. Wait for their choice; if they decline or want to proceed, continue with the offline hints and do not ask again.

### Phase 2: Dispatch Pages

Every prepared page is dispatched to a page worker, single-page inputs included. Read the run/dispatch examples in `references/cli-helper.md` and call repeatedly:

```bash
editppt run next <run>
```

When the dispatch stage is returned, the following steps are mandatory for each suggested page:

1. `python <skill-root>/scripts/build-page-worker-prompt.py <run> --page <page_id> --out <absolute-run-dir>/pages/<page_id>/worker-prompt.md`
2. Spawn a page worker using the current environment's available subagent/multi-agent tool.
3. `editppt run dispatch <run> --page <page_id> --agent-id <id> --prompt-file <absolute-run-dir>/pages/<page_id>/worker-prompt.md`

`--out` and `--prompt-file` must be absolute paths to avoid the page directory being prepended again to relative paths. The prompt builder only writes the prompt and prints a dispatch command template; it does not create the worker, so run `editppt run dispatch` only after a real spawn succeeds.

Concurrency slots come from `page_jobs.json.max_concurrent_pages` (default 6). In the normal flow prefer `editppt run next`; `editppt run status` is only for debugging or manual inspection.

### Phase 3: Record

Read the record examples in `references/cli-helper.md` and the `page_result.json` description in `references/manifest-schema.md`.

After a worker returns, run:

```bash
editppt run record <run> --page <page_id> --agent-id <id>
```

This command validates `page.pptx` against `manifest.json` before recording. It fails if positioned objects are missing source-pixel coordinates, if the manifest cannot independently rebuild the page, or if `validation.json` does not contain top-level `passed: true` — a failed page is never recorded.

Handling a failed page: when a worker returns a failure (`passed: false`), when `run record` rejects the outputs, or when a dispatched worker is lost and will not return, do not hand-edit state files and do not rebuild the page yourself. Read the page's `validation.json` for the failure reason, fix the root cause (for example a missing image-backend login reported by the worker), then run:

```bash
editppt run reset <run> --page <page_id>
```

This returns the page to `pending`. Then rebuild the worker prompt and dispatch a new worker through the normal Phase 2 steps. Never re-dispatch without changing something first: a worker re-run under identical conditions fails identically. When the same page fails twice on the same root cause, the diagnosis is yours, not the user's — read the failed attempt's `validation.json` and artifacts, reproduce the failing command yourself if needed, and fix the underlying cause (backend login, missing tools, broken assets) before resetting again. Only surface a problem to the user when it genuinely requires something only the user has (credentials, a paid account decision, the original file); phrase it as the concrete action needed, never as a debugging question.

### Phase 4: Finalize

Read the finalize examples in `references/cli-helper.md`.

When `editppt run next <run>` returns the finalize stage:

```bash
editppt run finalize <run>
```

`finalize` treats each recorded `pages/page_NNN/manifest.json` as the authoritative source: it rebuilds the final deck from page manifests in page order, then validates the resulting PPTX. `page.pptx` remains a page-level deliverability artifact for record-time checks.

Deck-level structural QA at this stage:

- The PPTX is a valid zip/package.
- Slide count matches the input page count.
- PDF/PPTX page mapping is correct.
- Media relationships are complete.
- All asset files referenced by the manifests exist.
- Media hashes match manifest provenance.
- Speaker notes hashes match.
- There is no invalid full-slide source raster plus editable text overlay pattern.

The final reply must report the final PPTX path and validation result.

## State Principles

Agents continue only from file facts and `editppt run next`. Required states:

- `pending`: created by `editppt prepare`; restored by `editppt run reset` when a page must be re-dispatched.
- `dispatched`: `editppt run dispatch` records a real spawned worker.
- `recorded`: `editppt run record` validates required outputs and writes the result; only deliverable pages (`validation.json` top-level `passed: true`) reach this state.
- `accepted` / `complete`: written by `editppt run finalize`.

`imagegen-jobs.json` is the page-local provenance/job record. Only these forced file states are kept:

- `recorded`: `editppt image import` has copied the selected output and written hash/metadata.
- `processed`: `editppt image process-sheet` has completed background removal and splitting.

## Delivery Principles

- Each page is self-checked once by the page reconstructor; the evidence is written into structured fields in `manifest.json` and into `validation.json`.
- The final output must be a currently openable, structurally valid `.pptx`. A full-slide `source.png` with editable text overlaid on top is not an acceptable fallback.
- Whether an imperfection must be fixed inside its page or may ship as a recorded warning is governed by the "Fix versus Warning" section of `references/page-decision-tree.md`. A warning may never replace a missing required workflow step.

## Updating This Skill

Reinstall through the installation channel, refresh the CLI from the updated skill directory, then restart the agent session and verify:

```bash
npx -y skills@latest add ningzimu/image-to-editable-ppt-skill \
  --skill image-to-editable-ppt \
  --agent <agent-id> \
  --global
pipx install --force --editable <skill-root>/cli
editppt doctor
```
