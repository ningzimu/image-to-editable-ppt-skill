# Example Prompts

The following prompts use Codex's `$` syntax. In other agents, use the corresponding syntax for selecting a skill. You can paste or attach images, PDFs, and `.pptx` files in the conversation, or provide local paths.

## Convert One Image into an Editable PowerPoint

```text
$image-to-editable-ppt Convert this image into an editable PowerPoint presentation.
```

## Convert Multiple Images into One PowerPoint

```text
$image-to-editable-ppt Convert these images into one editable PowerPoint presentation, with the slides in the order provided.
```

## Convert a PDF into an Editable PowerPoint

```text
$image-to-editable-ppt Convert <path-to-deck.pdf> into an editable PowerPoint presentation.
```

## Convert an Image-Based PowerPoint into an Editable PowerPoint

```text
$image-to-editable-ppt Convert <path-to-image-based.pptx> into an editable PowerPoint presentation and preserve the speaker notes on every slide.
```

## Configure an OCR Token

```text
Here is my Baidu AI Studio Access Token: <token>. Configure it in editppt for text correction.
```

## Configure a Third-Party Image API Fallback

```text
I need to configure a third-party image API. The base URL is <https://xxx/v1>, the model is <model-name>, and the API key is <key>. Save it to editppt's user-level configuration.
```

## Check Conversion Quality

```text
Compare each source image with the converted slide, check for missing text, misalignment, or missing assets, and summarize the validation results.
```

## Continue an Unfinished Task

```text
The previous conversion was interrupted. Check the most recent task under output/image-to-editable-ppt/, inspect its run state, and finish the remaining pages.
```
