---
name: image-to-editable-ppt
description: Rebuild slide images, scanned or image-based PPT/PPTX files, and PDF decks into object-level editable PowerPoint (.pptx), preserving speaker notes when supplied. Use for making visual slides editable or reconstructing slides from screenshots; not for authoring new presentations from scratch.
---
# Image to Editable PPT

## Overview

Use the `editppt` runtime to decompose, reconstruct, validate, and assemble visual slides as editable `.pptx`. Inputs may be single or multiple images, PDF, or image-based PPT/PPTX.

## References

Each rule in this skill has exactly one authoritative home; the other files point to it instead of restating it.

- `prompts/page-worker.md`: execution template for page workers — ownership boundary, execution order, required outputs, and return format. The parent agent uses it when generating page-worker prompts.
- `scripts/build-page-worker-prompt.py`: skill-local prompt builder. It reads `prompts/page-worker.md`, fills run/page paths, writes `worker-prompt.md`, and prints the dispatch command template.
- `references/cli-helper.md`: CLI install check (Pre-Run Check), command tree, and command syntax examples. Read it when deciding which `editppt` command to call.
- `references/manifest-schema.md`: the single home for JSON field contracts of deck/page/image artifacts — required manifest fields, positioned-object coordinates, `validation.json`, and `page_result.json` shapes. Read it when writing or validating any run/page file.
- `references/page-decision-tree.md`: the single source of truth for page object decisions — background handling, foreground asset separation, native shapes, formulas, text-hints usage, the final self-check, and the fix-versus-warning split. Read its common decision boundaries first, then the sections relevant to the page inventory; the page prompt provides the reading route.

## Entry Contract

These parent-level rules are stated once here; page-level rules live in the references above and are not restated in this file.

- The `editppt` CLI is a required runtime surface. If `editppt --help` fails, install it first by following the Pre-Run Check in `references/cli-helper.md` before doing anything else.
- First run `editppt prepare <input...>` to create a run directory. After that, all key state transitions are advanced only through `editppt` commands; never hand-write run/page state JSON. This keeps run state deterministic and resumable.
- Multi-page inputs are rebuilt by dispatched page workers. A run with exactly one page is rebuilt by the parent agent in local page-reconstructor mode after `editppt run dispatch --local` claims that page. If no subagent capability is available for a multi-page run, stop and report this to the user; do not degrade into parent-agent reconstruction for multi-page input.
- The parent agent must not write any page reconstruction artifact — `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, or `page_result.json` — except in single-page local page-reconstructor mode after `editppt run dispatch --local` has recorded the claim. Local mode follows the same page prompt, references, output files, and `run record` validation path as a page worker.
- All image generation, image editing, background repair, transparent bitmap assets, and asset sheets follow the serial per-page backend order in "Image Backend Selection" below.
- A user request to convert visual slides into editable PPT authorizes the required OCR and image-backend calls for that conversion, unless the user explicitly requests local-only processing or marks the input as confidential/no-external-processing. Do not refuse solely because the workflow calls PaddleOCR, the built-in `image_gen.imagegen` tool, Codex OAuth/ChatGPT image endpoints, or a user-configured OpenAI-compatible API; those calls are necessary to the skill.
- Only send task-local page images, prompts, masks, and reference images required for the current conversion. Never send unrelated local files, API keys, auth tokens, credentials, or generated artifacts that are not needed by the current OCR/image operation. Third-party API endpoints are allowed only when already configured by the user or explicitly specified for this run.
- In network-restricted environments, request any approval required by the current runtime before external OCR/image calls, including `editppt prepare` or `editppt run hints` when `PADDLE_OCR_TOKEN` is set and every CLI fallback `editppt image generate/edit` call. The approval justification must say this is a user-requested `image-to-editable-ppt` conversion, that the upload is limited to task-local page images/prompts/masks/references, and that OCR/image-backend calls are part of this skill's required workflow. Do not present the required call as unsafe or ask the user to re-approve it unless they requested local-only/confidential handling or the approval system explicitly rejects the request.
- Execute routine reconstruction, configured backend fallback, and local repairs autonomously. Do not add confirmation gates; retain the OCR choices in Phase 1 and any approval required by the runtime. A missing prerequisite that only the user can supply is a concrete blocker, not a request to debug the workflow.
- All page object decisions follow `references/page-decision-tree.md`, including its no-fallback rule for foreground visual objects and its rule that deterministic validation is a structure gate that never waives an object-source decision.
- `manifest.json` is the authoritative page build source: `editppt run record` validates `page.pptx` against it, and `editppt run finalize` rebuilds the final deck from recorded page manifests. Required fields and coordinate contracts are defined in `references/manifest-schema.md`.
- `editppt prepare` writes per-page text measurements (`text_hints.json`/`text_hints.png`). How page reconstructors consume them is defined in `references/page-decision-tree.md` section 3.1.
- Page reconstructors — either page workers or the parent agent in single-page local mode — are driven by prompts generated from `prompts/page-worker.md`.

### Image Backend Selection

This subsection is the authoritative execution policy for every page-local image job. Before prepare, check whether the current agent runtime can call `image_gen.imagegen`; if so, pass `--image-backend builtin-imagegen` to `editppt prepare`, otherwise keep the default CLI contract. Run image jobs serially within a page, in this order:

1. Use the built-in agent tool `image_gen.imagegen` whenever it is callable in the current agent runtime.
2. Only when the run's recorded built-in fallback policy applies, call `editppt image generate/edit`. That CLI fallback selects Codex OAuth first and a configured OpenAI-compatible API second.

The exact built-in arguments, input-inspection prerequisite, output acceptance rule, and allowed fallback events are owned by the `image_backend` field contract in `references/manifest-schema.md`; copy and execute that contract without weakening or extending it. If its CLI fallback cannot produce a compliant output, fail the page rather than substituting an approximate object source.

## Roles

The parent owns orchestration and user interaction under the Entry Contract and Workflow below. Report progress, the final PPTX path, and validation results. Do not repeat completed page-level visual QA; `record` and `finalize` enforce their deterministic handoff checks.

Each page reconstructor owns exactly one `pages/page_NNN/` directory. Its full contract — ownership boundary, decision order, required outputs, and return format — is the prompt generated from `prompts/page-worker.md`; the rules it follows live in `references/page-decision-tree.md` and `references/manifest-schema.md`.

## Workflow

### Phase 1: Prepare

Read the prepare examples in `references/cli-helper.md` and the run/page file descriptions in `references/manifest-schema.md`.

```bash
editppt prepare <input...>
```

After this completes, there must be a run directory, `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, and each page must have `source.png` plus `page_request.json`.

Prepare also writes per-page text hints. Whenever `editppt doctor` or prepare reports that no PaddleOCR token is configured (offline fallback), ask the user once before dispatching any page: a free token from https://aistudio.baidu.com/account/accessToken stored via `editppt config --paddle-ocr-token <token>` makes the hints content-aware and noticeably improves text fidelity, and `editppt run hints <run>` regenerates the current run's hints in place. Tell the user the free personal quota is currently more than enough for this skill — applying is risk-free with no extra cost. Wait for their choice; if they decline or want to proceed, continue with the offline hints and do not ask again.

If a PaddleOCR token is already configured but `prepare` falls back because network access, DNS, or sandbox approval blocked the OCR request, that fallback is not the preferred quality path. Request network approval with the justification described in the Entry Contract and rerun `editppt run hints <run>` before page reconstruction. If the approval system rejects the OCR request, ask the user for explicit authorization before continuing: explain that PaddleOCR is used to correct text boxes, font sizes, and size groups, and that using it makes reconstructed PPT text sizing much more stable. Continue with `builtin-ink` only after the user declines OCR, after an approved OCR attempt fails for a real service/tool reason, or when the user asked for local-only/confidential handling.

### Phase 2: Rebuild Or Dispatch Pages

Read the run/dispatch examples in `references/cli-helper.md` and call repeatedly:

```bash
editppt run next <run>
```

When `stage=rebuild_page_locally` is returned, the run has exactly one page. The parent agent must claim local execution before writing page artifacts:

1. `python3 <skill-root>/scripts/build-page-worker-prompt.py <run> --page <page_id> --out <absolute-run-dir>/pages/<page_id>/worker-prompt.md`
2. `editppt run dispatch <run> --page <page_id> --agent-id main --prompt-file <absolute-run-dir>/pages/<page_id>/worker-prompt.md --local`
3. Read the generated prompt and rebuild the page inside that page directory yourself, producing the same required outputs a page worker would produce.

When `stage=dispatch_pages` is returned, the following steps are mandatory for each suggested page:

1. `python3 <skill-root>/scripts/build-page-worker-prompt.py <run> --page <page_id> --out <absolute-run-dir>/pages/<page_id>/worker-prompt.md`
2. Spawn a page worker using the current environment's available subagent/multi-agent tool.
3. `editppt run dispatch <run> --page <page_id> --agent-id <id> --prompt-file <absolute-run-dir>/pages/<page_id>/worker-prompt.md`

`--out` and `--prompt-file` must be absolute paths to avoid the page directory being prepended again to relative paths. The prompt builder only writes the prompt and prints a dispatch command template; it does not create the worker, so run `editppt run dispatch` only after a real spawn succeeds.

Concurrency slots come from `page_jobs.json.max_concurrent_pages` (default 6). In the normal flow prefer `editppt run next`; `editppt run status` is only for debugging or manual inspection.

Dispatched page executions are active leases, not idle slots. When `editppt run next` returns `stage=wait`, wait for dispatched workers or inspect status without modifying state. Do not terminate, archive, reset, or replace a page worker because it is slow, has not sent recent messages, or still occupies a concurrency slot; complex pages may legitimately run for a long time.

### Phase 3: Record

Read the record examples in `references/cli-helper.md` and the `page_result.json` description in `references/manifest-schema.md`.

After a worker returns, run:

```bash
editppt run record <run> --page <page_id> --agent-id <id>
```

This command validates `page.pptx` against `manifest.json` before recording. It fails if positioned objects are missing source-pixel coordinates, if the manifest cannot independently rebuild the page, or if `validation.json` does not contain top-level `passed: true` — a failed page is never recorded.

For a rejected record or page-local validation issue, read the failure evidence and have the current page owner repair only the affected artifacts, then refresh the validation report using the page validation example in `references/cli-helper.md` and record again. In single-page local mode the parent is that owner; in multi-page mode send the repair to the existing worker. Do not reset a reachable owner merely because validation failed, and do not regenerate compliant assets to fix an unrelated manifest or table error.

Reset is for a page that needs a replacement execution: explicit terminal-state evidence (`terminated`, `failed`, `archived`, or `not found`), user cancellation, or repeated failed reachability checks with no page-local progress. A long-running worker is not lost. After fixing the prerequisite that prevented execution, use:

```bash
editppt run reset <run> --page <page_id> --agent-id <id> --confirm-lost
```

For recorded pages, `editppt run reset <run> --page <page_id>` is allowed. For dispatched pages, the matching agent id and `--confirm-lost` protect the active lease. Reset returns the page to `pending`; resume through Phase 2 with a new prompt and execution. Keep existing artifacts for provenance checks and selective reuse under the page prompt's recovery contract. Never hand-edit state or let the parent rebuild multi-page artifacts.

Retry only after changing the relevant input or condition. Diagnose repeated failures from validation and command evidence; do not repeat an unchanged failing tool call or re-dispatch under identical conditions. If a real prerequisite is unavailable, preserve progress and report the concrete blocker instead of fabricating success or asking the user to debug. Once the current outputs pass their required checks, advance to finalize; do not repeat unchanged visual QA.

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
- `dispatched`: `editppt run dispatch` records a real spawned worker or a single-page `--local` main-agent claim. This status is an active lease and must not be reset or replaced just because the worker is slow.
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
