# Changelog

Release notes are generated from this file. Keep changelog entries in English.

## Unreleased

### Features

- Expand the image-to-editable-ppt skill to normalize images, PDFs, and PPT/PPTX inputs into page jobs, assemble deck manifests into multi-page PPTX files, and preserve PPT/PPTX speaker notes.
- Add skill-local runtime management scripts and dependencies for input preparation, deck assembly, and validation.

### Fixes

- Reject page manifests that combine a full-slide source raster background with editable text overlays, preventing baked-text overlap from passing validation.
- Respect per-object `z_index` and round-rectangle previews in PPTX assembly and preview rendering so cleaned backgrounds, native shapes, generated icons, and editable text can be layered independently.
- Add manifest support for rotated editable text boxes and dashed editable lines for chart axes, gridlines, and timelines.

### Documentation

- Add repository README files, contribution guidance, changelog, license, PR template, and lightweight GitHub checks.
- Add README badges for language switching, GitHub stars, and GitHub forks.
- Document mandatory one-subagent-per-page dispatch for multi-image, PDF, and PPT/PPTX conversions, including the required blocker behavior when subagents are unavailable.
- Clarify that dashboard and dense infographic pages require an explicit `$imagegen` gate decision, and that style-bearing icons or pictograms must use `$imagegen` assets.
- Document that preview-visible crude or placeholder-like icons are blockers that require targeted `$imagegen` asset repair before reporting completion.
- Require page manifests to declare `completion_status` and block assembly when required `$imagegen` clean visual layers or assets are unavailable.
