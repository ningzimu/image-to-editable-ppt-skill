#!/usr/bin/env python3
"""Generate text hints for every page of a prepared run.

Runs as part of `editppt prepare`, after page directories exist: each
`pages/page_NNN/` receives canonical `text_hints.json` and `text_hints.png`
files so page workers find their text measurements already in place.

Backend selection per run:
- With a PaddleOCR token (PADDLE_OCR_TOKEN env var, or PADDLE_OCR_TOKEN in
  ~/.editppt/config.yaml): PDF inputs are submitted to the OCR service as ONE
  job covering all pages; image/PPTX inputs submit each page's source.png.
  OCR coordinates are rescaled to each page's actual source.png resolution
  and re-measured locally with the ink metrics.
- Without a token, or when the service fails: the built-in offline detector
  (`text_hints.py`) runs per page, so every page still gets hints.

Hint generation is best-effort: a page that fails is reported and skipped,
and the page worker can regenerate with `editppt page hints <page_dir>`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image

from deck_run_state import load_deck, load_jobs, page_dir_for, run_dir_from_target
from text_hints import draw_overlay, page_text_hints

HINTS_JSON = "text_hints.json"
HINTS_PNG = "text_hints.png"


def paddle_token() -> str:
    token = os.environ.get("PADDLE_OCR_TOKEN", "").strip()
    if token:
        return token
    try:
        from runtime_env import config_path, read_config_file

        return str(read_config_file(config_path()).get("PADDLE_OCR_TOKEN", "")).strip()
    except Exception:
        return ""


def write_hints(page_dir: Path, hints: dict, overlay: bool) -> None:
    (page_dir / HINTS_JSON).write_text(json.dumps(hints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if overlay:
        draw_overlay(Image.open(page_dir / "source.png"), hints["lines"], page_dir / HINTS_PNG)


def builtin_page(page_dir: Path) -> dict:
    hints = page_text_hints(page_dir)
    hints["backend"] = "builtin-ink"
    return hints


def synthesize_pdf(page_dirs: list[Path], out_path: Path) -> None:
    """Bundle the per-page source images into one PDF (one page per image).

    Lets every input type — single image, multiple images, image-based PPTX —
    reach the OCR service as a single batch job instead of one job per page.
    Page size is the image's pixel size in points; build_page_hints rescales
    the OCR coordinates back to each source.png regardless of the resolution
    the service rendered at.
    """
    import fitz

    document = fitz.open()
    for page_dir in page_dirs:
        with Image.open(page_dir / "source.png") as image:
            width, height = image.size
        page = document.new_page(width=width, height=height)
        page.insert_image(fitz.Rect(0, 0, width, height), filename=str(page_dir / "source.png"))
    document.save(out_path)
    document.close()


def paddle_pages(run_dir: Path, deck: dict, page_dirs: list[Path], token: str, timeout: int) -> dict[Path, dict]:
    """Fetch OCR results for all pages in ONE job; returns {page_dir: hints}."""
    import tempfile

    from paddle_text_hints import DEFAULT_MODEL, build_page_hints, submit_and_fetch

    original = None
    if str(deck.get("input_type", "")) == "pdf":
        input_dir = run_dir / "input"
        candidates = sorted(input_dir.glob("*.pdf")) if input_dir.exists() else []
        original = candidates[0] if candidates else None

    synthesized = None
    try:
        if original is None:
            handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            handle.close()
            synthesized = Path(handle.name)
            synthesize_pdf(page_dirs, synthesized)
            original = synthesized
        pages = submit_and_fetch(original, token, DEFAULT_MODEL, timeout)
    finally:
        if synthesized is not None:
            synthesized.unlink(missing_ok=True)
    if len(pages) != len(page_dirs):
        raise RuntimeError(f"OCR returned {len(pages)} pages for {len(page_dirs)} page dirs")
    return {page_dir: build_page_hints(page_dir, pruned) for page_dir, pruned in zip(page_dirs, pages)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-page text hints for a prepared run.")
    parser.add_argument("run", help="Run directory or deck_manifest.json path.")
    parser.add_argument("--timeout", type=int, default=300, help="OCR job timeout in seconds.")
    parser.add_argument("--no-overlay", action="store_true", help="Skip the labeled overlay images.")
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    jobs = load_jobs(run_dir)
    page_dirs = [page_dir_for(run_dir, page) for page in jobs.get("pages", [])]
    page_dirs = [d for d in page_dirs if (d / "source.png").exists()]
    if not page_dirs:
        print("text-hints: no pages with source.png; skipped", file=sys.stderr)
        return 0

    token = paddle_token()
    results: dict[Path, dict] = {}
    backend = "builtin-ink"
    if not token:
        print(
            "text-hints: no PaddleOCR token configured; falling back to the built-in offline "
            "detector (geometry only — it measures where text is and how large, but cannot read "
            "it). A free PaddleOCR-VL token adds recognized text content and cleaner block "
            "boundaries, noticeably improving text fidelity in the final PPT. The free personal quota "
            "is currently more than enough for this skill, so applying is risk-free with no extra "
            "cost. ASK THE USER once "
            "before reconstructing pages: configure a token now (apply at "
            "https://aistudio.baidu.com/account/accessToken, then `editppt config "
            "--paddle-ocr-token <token>` and `editppt run hints <run>` to regenerate this run's "
            "hints), or continue with the offline result. Respect their choice and do not ask again.",
            file=sys.stderr,
        )
    if token:
        try:
            results = paddle_pages(run_dir, deck, page_dirs, token, args.timeout)
            backend = "paddleocr-vl"
        except Exception as exc:
            print(f"text-hints: PaddleOCR failed ({exc}); falling back to built-in detector", file=sys.stderr)
            results = {}

    written = 0
    for page_dir in page_dirs:
        try:
            hints = results.get(page_dir) or builtin_page(page_dir)
            # Dense diagrams can defeat the OCR layout model entirely (the
            # whole figure is classified as an image and only a headline
            # survives). When OCR found almost nothing but the offline
            # detector finds plenty, the geometric hints are more useful.
            if hints.get("backend") == "paddleocr-vl" and len(hints["lines"]) <= 2:
                offline = builtin_page(page_dir)
                if len(offline["lines"]) >= 6:
                    print(
                        f"text-hints: {page_dir.name}: OCR found {len(hints['lines'])} text lines but the "
                        f"offline detector found {len(offline['lines'])}; using the offline result for this page",
                        file=sys.stderr,
                    )
                    hints = offline
            write_hints(page_dir, hints, overlay=not args.no_overlay)
            written += 1
        except Exception as exc:
            print(f"text-hints: {page_dir.name} failed ({exc}); worker can run `editppt page hints` itself", file=sys.stderr)
    print(f"text-hints: wrote {written}/{len(page_dirs)} pages (backend={backend})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
