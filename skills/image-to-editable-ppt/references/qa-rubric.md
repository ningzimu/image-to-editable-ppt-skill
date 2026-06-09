# QA Rubric

Deterministic validation is necessary but not sufficient. Whoever reconstructs a page is responsible for checking that page's preview and contact sheet once. The parent agent does not repeat page-level visual QA when recording page worker results.

## Structural QA

- The PPTX is a valid zip/package.
- Slide count matches the input page count.
- PDF/PPTX page mapping is correct.
- Media relationships are complete.
- All asset files referenced by the manifest exist.
- Media hashes match manifest provenance.
- Speaker notes hashes match.
- There is no invalid full-slide source raster plus editable text overlay pattern.

## Text QA

- `text_inventory` covers all readable text.
- Every editable text item is a real visible native PPT text box.
- There is no hidden text, transparent text, 1 pt text, or off-canvas text.
- The preview has no obvious clipping, incorrect wrapping, or text overflow from containers.
- Chinese previews must not show boxes or mojibake; use a stable CJK font when needed.
- Font sizes and positions must be calibrated against the source; do not enlarge titles, body text, or labels by default.
- If same-level text in the preview is visibly larger, heavier, more crowded, or wraps more than in the source, it must be fixed in the current page.

## Asset QA

- `visual_inventory` covers all required non-text visual objects.
- Every required non-text visual object has an independent representation unless it is explicitly recorded as background.
- The source decision for every non-text visual object must follow `page-decision-tree.md`. QA does not define another page object classification rule; it only checks whether the manifest, asset provenance, preview, and contact sheet follow that decision tree.
- Asset-sheet splitting results have no fused objects, missing edges, wrong names, fragments, or cross-object shadows.
- Alpha edges have no obvious chroma-key remnants.
- Every final raster asset has provenance.
- Assets that `page-decision-tree.md` marks as requiring source-faithful separation must not be missing, must not be replaced with a similar but different symbol, and must not use a source type forbidden by the decision tree.
- Source-derived raster assets must satisfy the exception conditions in `page-decision-tree.md` and record the source region.

## Background QA

- The clean base contains no readable text.
- The clean base contains no foreground object that will be rebuilt later.
- Repaired background regions have no obvious ghosts, blur blocks, smear patches, or pseudo-text.
- Solid-color and regular backgrounds should not waste image backend calls.
- A complex-background clean base must be the same background as the source: composition, perspective, main object positions, colors, lighting, and key details must not visibly drift.
- If the image backend generates a related theme but different background, the current page must be fixed even if deterministic validation passes.

## Shape QA

- If the source is a straight-corner rectangle, table outline, or square panel, the manifest must use `rect`.
- Use `roundRect` only when the source clearly has rounded corners, and record `source_corner_radius_px`.
- Reconstructed corner radius must be close to the source; a slight corner radius must not become a pill.
- Do not convert ordinary rectangles into rounded rectangles because of design preference.
- Do not redraw text strokes as decorative lines. If an extra horizontal line, dot, or symbol appears, inspect the source to determine whether it is a text stroke or an independent decoration, then fix the current page.

## Visual QA

- `preview.png` must exist.
- `split_assets_contact.png` must exist and show an origin-versus-preview comparison.
- Visual drift, missing labels, low-quality placeholders, and any object-source decision that violates `page-decision-tree.md` must be fixed in the current page.
- Large container corner geometry, table borders, and card borders must align with the source. Corner misclassification is a current-page fix, not a low-risk warning.

## Check Results

Must be fixed in the current page:

- Input cannot be normalized.
- Final PPTX cannot be opened.
- Page is missing a buildable manifest/page.pptx.
- Required visual objects are missing.
- Object-source decisions violate `page-decision-tree.md`.
- Complex-background clean base is visibly distorted or has become a different background.
- A straight-corner source rectangle was rebuilt as a rounded rectangle without evidence that the source had rounded corners.
- Text font size or position visibly deviates from the source and causes crowding, overflow, or occlusion.

Warnings:

- Minor visual drift in non-icon, non-critical decorations.
- Minor line-width, antialiasing, proportion, shadow, or detail differences in icons.
- Some non-critical decorations are not perfectly identical.
- Recorded low-risk font differences.

Warnings can be delivered with the current PPT.
