---
name: image-to-editable-ppt
description: Use this skill when the user provides one or more slide images, image-based PPT/PPTX files, or PDFs and asks to convert them into editable PowerPoint/PPTX, reconstruct slide objects, preserve speaker notes, or create an editable recreation.
---
# Image to Editable PPT

## Overview

This skill rebuilds visual slide inputs into object-level editable PowerPoint `.pptx` files.

Inputs can be a single image, multiple images, a PDF, or an image-based PPT/PPTX. The output is always `.pptx`. The goal is not to wrap a full-slide screenshot inside PowerPoint; the goal is to use the `editppt` runtime and page-level prompts to decompose, reconstruct, validate, and assemble editable slides.

## References

```text
skills/image-to-editable-ppt/
|-- SKILL.md
|-- prompts/
|   `-- page-worker.md
|-- scripts/
|   `-- build-page-worker-prompt.py
`-- references/
    |-- cli-helper.md
    |-- manifest-schema.md
    |-- page-decision-tree.md
    `-- qa-rubric.md
```

- `prompts/page-worker.md`: execution template for page workers. The parent agent uses it when generating page-worker prompts.
- `scripts/build-page-worker-prompt.py`: skill-local prompt builder. It reads `prompts/page-worker.md`, fills run/page paths, writes `worker-prompt.md`, and prints the dispatch command template.
- `references/cli-helper.md`: CLI command manual, command tree, and common command examples. Read it when deciding which `editppt` command to call.
- `references/manifest-schema.md`: JSON schemas and artifact contracts for deck/page/image jobs. Read it when writing manifests, writing `page_result.json`, or understanding run/page files.
- `references/page-decision-tree.md`: the single source of truth for page object decisions. Read it before reconstructing any page.
- `references/qa-rubric.md`: structural, text, asset, background, and visual QA standards. Read it before a page returns and before final delivery.

## Entry Contract

- First run `editppt prepare <input...>` to create a run directory. After that, all key state transitions must be advanced only through `editppt` commands.
- After `prepare`, read the run information and determine the actual page count. The parent agent may directly rebuild the page only when the actual page count is 1.
- When the actual page count is greater than 1, the parent agent only orchestrates: run `editppt run next`, generate worker prompts with `scripts/build-page-worker-prompt.py`, spawn subagents/page workers, record dispatches, wait for and record results, then finalize.
- Multi-page inputs must be truly dispatched to subagents/page workers. If no subagent capability is available, stop and report this to the user; do not degrade into serial parent-agent page reconstruction.
- All image generation, image editing, background repair, transparent bitmap assets, and asset sheets must use `editppt image generate/edit/batch`.
- Page-level reconstruction strategy must follow the References.
- Foreground visual objects, including foreground photos, screenshots, illustrations, icons, pictograms, symbols, logo-like marks, semantic badges, and trend/status icons, must use image-backend source-faithful asset-sheet separation unless the page-decision tree explicitly classifies them as native structural shapes.
- `manifest.json` is the authoritative page build source for both page-level validation and final deck assembly. `page.pptx` must be generated from that manifest; a visually acceptable page PPTX produced by separate page-local code is not enough.
- Positioned manifest objects must carry source-pixel coordinates: `text_boxes[]` and `images[]` require `box_px`, non-line `shapes[]` require `box_px`, and line shapes require `points_px`. Missing coordinates are record/finalize failures.
- Text boxes should start with deterministic runtime fitting enabled. `text_boxes[].box_px` must track the source text bounds plus modest padding so the builder can clamp oversized first-draft fonts before preview.
- Page workers use `prompts/page-worker.md`.
- A full-slide `source.png` with editable text overlaid on top is not an acceptable fallback. The final output must be a currently openable, structurally valid `.pptx`.

## Roles

The parent agent owns orchestration and user interaction:

- Run `editppt prepare`.
- In the normal path, no extra backend configuration command is required; `editppt image` automatically chooses Codex OAuth or API fallback.
- For a single-page input, directly rebuild that page and record the result with `editppt run record --agent-id main`.
- For a multi-page input, do not write any page reconstruction artifacts inside `pages/page_NNN/`; use only `editppt run next` to obtain pages that need dispatch.
- Generate prompts for pages that need work with `scripts/build-page-worker-prompt.py`, spawn page workers, and record dispatches with `editppt run dispatch`.
- Record page worker results with `editppt run record`.
- Assemble and validate the final PPTX with `editppt run finalize`. Final assembly reads the recorded page manifests in page order and rebuilds the final deck from those manifests.
- Report progress, final path, and validation result to the user.

The parent agent must not create or modify page-local reconstruction outputs in multi-page runs, must not repeat page-level visual QA already completed by page workers, and must not hand-write key state JSON.

Each page worker owns one `pages/page_NNN/` directory:

- Read only its own `page_request.json`, `source.png`, and relevant references.
- Write only its own page directory.
- Use `page_request.json.image_backend`.
- Analyze text, structure, background, and foreground visual objects.
- Use the page decision tree to choose native text, native shapes, LaTeX-rendered formula assets, clean bases, and asset sheets.
- Use `editppt image generate/edit/batch` to generate or edit required bitmaps.
- Use `editppt formula render-latex` to render formula image assets.
- Use `editppt image import` and `editppt image process-sheet` to record and process generated asset sheets.
- Write `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, and `page_result.json`.
- Build `page.pptx` and `preview.png` from `manifest.json`; do not use a separate page-local PPTX script that bypasses the manifest.
- As the page reconstructor, self-check `preview.png`, `split_assets_contact.png`, and `validation.json`; if a page-local issue is found, fix it inside the current page before returning.

Page workers must not edit `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, the final PPTX, the original input, or any other page directory.

## Workflow

### Phase 1: Prepare

Read the prepare examples in `references/cli-helper.md` and the run/page file descriptions in `references/manifest-schema.md`.

```bash
editppt prepare <input...>
```

After this completes, there must be a run directory, `deck_manifest.json`, `page_jobs.json`, `notes_manifest.json`, and each page must have `source.png` plus `page_request.json`. The normal flow does not require an extra `editppt run backend` command.

### Phase 2: Dispatch Pages

First determine the actual page count from `deck_manifest.json` or from `editppt run next <run> --json`.

When the actual page count is 1, the parent agent completes page outputs in `pages/page_001/`, then proceeds to Phase 3.

When the actual page count is greater than 1, the parent agent must not write any page reconstruction artifacts, including `manifest.json`, `page.pptx`, `preview.png`, `split_assets_contact.png`, `validation.json`, or `page_result.json`. These files may only be produced by the corresponding page worker.

Read the run/dispatch examples in `references/cli-helper.md`. Before spawning page workers, generate each worker prompt with `scripts/build-page-worker-prompt.py`.

Call repeatedly:

```bash
editppt run next <run>
```

When a multi-page input returns the dispatch stage, the following steps are mandatory:

1. `python <skill-root>/scripts/build-page-worker-prompt.py <run> --page <page_id> --out <absolute-run-dir>/pages/<page_id>/worker-prompt.md`
2. Spawn a page worker using the current environment's available subagent/multi-agent tool.
3. `editppt run dispatch <run> --page <page_id> --agent-id <id> --prompt-file <absolute-run-dir>/pages/<page_id>/worker-prompt.md`

`--out` and `--prompt-file` must be absolute paths to avoid the page directory being prepended again to relative paths. The prompt builder only writes the prompt and prints a dispatch command template; it does not create the worker. Run `editppt run dispatch` only after a real spawn succeeds. If the current environment has no available subagent capability, stop and report this, then wait for the user to decide the next step.

Concurrency slots come from `page_jobs.json.max_concurrent_pages`; the default is 6. `editppt run status` is only for debugging or manual inspection. In the normal parent flow, prefer `editppt run next`.

### Phase 3: Record

Read the record examples in `references/cli-helper.md` and the `page_result.json` description in `references/manifest-schema.md`.

After a worker returns, run:

```bash
editppt run record <run> --page <page_id> --agent-id <id>
```

This command validates `page.pptx` against `manifest.json` before recording. It must fail if positioned text, image, or shape objects are missing source-pixel coordinates or if the manifest cannot independently rebuild the page.

For a directly rebuilt single-page input, use:

```bash
editppt run record <run> --page page_001 --agent-id main
```

### Phase 4: Finalize

Read the finalize examples in `references/cli-helper.md` and the deck-level QA points in `references/qa-rubric.md`.

`editppt run finalize` treats each recorded `pages/page_NNN/manifest.json` as the authoritative source for final assembly. It rebuilds the final deck from page manifests in page order, then validates the resulting PPTX. `page.pptx` remains a page-level deliverability artifact for record-time checks.

When `editppt run next <run>` returns the finalize stage:

```bash
editppt run finalize <run>
```

The final reply must report the final PPTX path and validation result.

## State Principles

Run/page state is advanced by `editppt run` commands. Agents continue only from file facts and `editppt run next`.

Required states:

- `pending`: created by `editppt prepare`.
- `dispatched`: `editppt run dispatch` records a real spawned worker.
- `recorded`: `editppt run record` validates required outputs and writes the result; direct single-page reconstruction is also recorded through this command.
- `accepted` / `complete`: written by `editppt run finalize`.

`imagegen-jobs.json` is the page-local provenance/job record. Only these forced file states are kept:

- `recorded`: `editppt image import` has copied the selected output and written hash/metadata.
- `processed`: `editppt image process-sheet` has completed background removal and splitting.

## Delivery Principles

- Each page is self-checked once by the page reconstructor; the evidence is written into structured fields in `manifest.json` and into `validation.json`.
- If a page-local issue is found, the current page author fixes it directly.
- The final output must be a currently openable, structurally valid `.pptx`.
- A full-slide `source.png` with editable text overlaid on top is not an acceptable fallback.
- Minor drift in icons, bitmap assets, fonts, positions, shapes, and similar details may be delivered as warnings only after the object-source decision follows the page decision tree. Missing asset edges, forbidden source types for foreground assets, or replacing required asset-sheet separation with a direct source-image snippet are current-page failures, not warnings.

## Update Skill

To update this skill, reinstall the same skill through the installation channel:

```bash
npx -y skills@latest add ningzimu/image-to-editable-ppt-skill \
  --skill image-to-editable-ppt \
  --agent <agent-id> \
  --global
```

Replace `<agent-id>` with the target agent id; for example, use `codex` for Codex.

The CLI lives in this skill's `cli/` directory and is a required runtime surface. After updating the skill, refresh the global CLI from the updated skill directory:

```bash
pipx install --force --editable <skill-root>/cli
```

After updating, restart the corresponding agent session and run:

```bash
editppt --help
editppt doctor
```
