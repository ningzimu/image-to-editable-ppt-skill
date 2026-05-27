# Changelog

Release notes are generated from this file. Keep changelog entries in English.

## Unreleased

### Features

- Expand the image-to-editable-ppt skill to normalize images, PDFs, and PPT/PPTX inputs into page jobs, assemble deck manifests into multi-page PPTX files, and preserve PPT/PPTX speaker notes.
- Add skill-local runtime management scripts and dependencies for input preparation, deck assembly, and validation.
- Add page-local artifact helpers for chroma cleanup, asset splitting, PPTX building, validation, and visual QA artifacts.

### Improvements

- Add deterministic run-state scripts for deck preparation, page status inspection, subagent dispatch/result recording, repair queueing, imagegen result recording, asset-sheet processing, contact-sheet generation, and final deck validation.
- Add batch-dispatch metadata so the parent agent can respect runtime subagent concurrency limits across multiple dispatch rounds.
- Consolidate legacy script entrypoints into internal helpers so input normalization, page artifact utilities, and asset cropping are reached through the stable orchestration scripts.
- Normalize image-based `.pptx` inputs with lightweight OOXML/zip extraction instead of requiring LibreOffice for decks that contain one full-slide image per slide.
- Document the end-to-end page reconstruction loop, including page classification, source-geometry preservation, chroma-key selection, contact-sheet inspection, and source/preview QA.

### Fixes

- Reject page manifests that combine a full-slide source raster background with editable text overlays, preventing baked-text overlap from passing validation.
- Respect per-object `z_index` and round-rectangle previews in PPTX assembly and preview rendering so cleaned backgrounds, native shapes, generated icons, and editable text can be layered independently.
- Add manifest support for rotated editable text boxes and dashed editable lines for chart axes, gridlines, and timelines.
- Require page manifests to record font calibration, visual inventory matching, background strategy checks, and shape-corner checks before validation passes.
- Require source evidence for `roundRect` shapes so straight-corner containers are not silently rebuilt as rounded rectangles.
- Improve preview font scaling and allow source-derived raster provenance for small non-text visual assets that need higher source consistency.

### Documentation

- Add the generated codex-ppt and image-to-editable-ppt introduction PDF to the README tips.
- Add the kidney cancer MDT infographic as a README conversion example.
- Add Skill community group QR code sections to the Chinese and English READMEs.
- Add repository README files, contribution guidance, changelog, license, PR template, and lightweight GitHub checks.
- Add README badges for language switching, GitHub stars, and GitHub forks.
- Restructure the installable skill docs into a Chinese first-pass stable workflow with focused references, page-worker prompt templates, strict state-machine guidance, and `$imagegen` integration rules.
- Document mandatory one-subagent-per-page dispatch for multi-image, PDF, and PPT/PPTX conversions, including how to report subagent-dispatch issues.
- Clarify that dashboard and dense infographic pages require an explicit `image_gen` gate decision, and that style-bearing icons or pictograms must use generated assets.
- Clarify foreground/background separation for hand-drawn and dense infographic pages so semantic marks are not left only in clean base images.
- Document that preview-visible crude or placeholder-like icons should trigger targeted `image_gen` asset repair when practical, with unresolved cases recorded as fidelity limits.
- Remove page readiness status gates from the workflow; subagents must return editable page-level PPTX outputs for assembly and record quality limits separately.
- Clarify that page subagents are runtime Codex workers dispatched by the parent agent, not named agent types registered by the plugin manifest.
- Refine the Chinese and English READMEs with clearer positioning, runtime requirements, supported input scope, and reconstruction limits.
- Clarify source-consistent clean-background generation, including imagegen prompts that preserve original composition, perspective, object placement, color, and lighting.
- Add README known limitations for Codex-only support, untested third-party API integrations, and model-quality expectations.
- Add GitHub Release workflow documentation and release zip installation notes.
- Add a handdrawn project overview image to the Chinese and English README files.
- Document that reconstructed image elements and text positions may have slight drift and are not guaranteed to be 100% replicas.
- Add a prominent README pointer to codex-ppt-skill for users who need to generate new PPT decks.
