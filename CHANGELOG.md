# Changelog

Release notes are generated from this file. Keep changelog entries in English.

## Unreleased

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
