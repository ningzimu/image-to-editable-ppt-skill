#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_pptx_from_manifest as ppt_builder  # noqa: E402


def split_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def run(command):
    print("+ " + " ".join(str(part) for part in command))
    subprocess.run([str(part) for part in command], check=True)


def resolve_under_page(page_dir, value):
    path = Path(value)
    if path.is_absolute():
        return path
    return page_dir / path


def imagegen_chroma_helper():
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    helper = codex_home / "skills/.system/imagegen/scripts/remove_chroma_key.py"
    if not helper.exists():
        raise SystemExit(f"Missing imagegen chroma helper: {helper}")
    return helper


def process_asset_sheet(args, page_dir):
    chroma = resolve_under_page(page_dir, args.chroma)
    alpha = resolve_under_page(page_dir, args.alpha)
    if not args.asset_sheet_source and not chroma.exists() and not alpha.exists():
        return
    if not args.asset_sheet_source and args.skip_chroma and args.skip_split:
        return

    if args.asset_sheet_source:
        source = Path(args.asset_sheet_source).expanduser()
        if not source.exists():
            raise SystemExit(f"Asset sheet source does not exist: {source}")
        chroma.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, chroma)
        print(f"Wrote {chroma}")

    if not args.skip_chroma:
        if not chroma.exists():
            raise SystemExit(f"Chroma input does not exist: {chroma}")
        chroma_command = [
            sys.executable,
            imagegen_chroma_helper(),
            "--input",
            chroma,
            "--out",
            alpha,
            "--auto-key",
            "border",
            "--soft-matte",
            "--transparent-threshold",
            args.transparent_threshold,
            "--opaque-threshold",
            args.opaque_threshold,
        ]
        if args.despill:
            chroma_command.append("--despill")
        if args.force_chroma:
            chroma_command.append("--force")
        run(chroma_command)

    if args.skip_split:
        return
    if not alpha.exists():
        raise SystemExit(f"Alpha sheet does not exist: {alpha}")

    assets_dir = resolve_under_page(page_dir, args.assets_dir)
    split_command = [
        sys.executable,
        SCRIPT_DIR / "split_alpha_components.py",
        "--input",
        alpha,
        "--out-dir",
        assets_dir,
        "--sort",
        args.split_sort,
        "--min-area",
        args.split_min_area,
        "--merge-gap",
        args.split_merge_gap,
        "--merge-union-growth",
        args.split_merge_union_growth,
        "--manifest",
        resolve_under_page(page_dir, args.split_manifest),
    ]
    if args.square_assets:
        split_command.append("--square")
    if args.asset_names:
        split_command.extend(["--names", args.asset_names])
    run(split_command)


def load_manifest(manifest_path, preview_scale):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if preview_scale:
        manifest["preview_scale"] = int(preview_scale)
    return manifest


def build_and_validate(args, page_dir, preview_path):
    manifest_path = resolve_under_page(page_dir, args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Manifest does not exist: {manifest_path}")

    pptx_path = resolve_under_page(page_dir, args.out)
    validation_path = resolve_under_page(page_dir, args.validation)

    manifest = load_manifest(manifest_path, args.preview_scale)
    ppt_builder.write_pptx(manifest, pptx_path, manifest_path)
    ppt_builder.render_preview(manifest, manifest_path, preview_path)
    print(f"Wrote {pptx_path}")

    run(
        [
            sys.executable,
            SCRIPT_DIR / "validate_pptx.py",
            pptx_path,
            "--manifest",
            manifest_path,
            "--report",
            validation_path,
        ]
    )

    return preview_path


def fit_image(image, size):
    if image.size == size:
        return image
    return image.resize(size)


def write_pair(source_path, preview_path, out_path):
    from PIL import Image, ImageDraw

    source = Image.open(source_path).convert("RGB")
    rebuilt = Image.open(preview_path).convert("RGB")
    source = fit_image(source, rebuilt.size)

    label_h = 32
    gap = 18
    width, height = rebuilt.size
    canvas = Image.new("RGB", (width * 2 + gap, height + label_h), "#f5f7fb")
    canvas.paste(source, (0, label_h))
    canvas.paste(rebuilt, (width + gap, label_h))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 9), "origin", fill="black")
    draw.text((width + gap + 10, 9), "preview", fill="black")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Wrote {out_path}")


def write_qa(args, page_dir, preview_path):
    source_path = resolve_under_page(page_dir, args.source)
    if not source_path.exists():
        print(f"Skipping QA pair because source is missing: {source_path}", file=sys.stderr)
        return
    pair_path = resolve_under_page(page_dir, args.contact_sheet)
    write_pair(source_path, preview_path, pair_path)


def main():
    parser = argparse.ArgumentParser(
        description="Run the repeatable local page experiment loop: optional chroma/split, build, validate, and origin/preview contact-sheet QA."
    )
    parser.add_argument("page_dir", help="Page folder containing source.png and manifest.json")
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--source", default="source.png")
    parser.add_argument("--out", default="page.pptx")
    parser.add_argument("--validation", default="validation.json")
    parser.add_argument("--preview-scale", type=int, default=72, help="Low-resolution preview scale for tuning; use 144+ for final checks")

    parser.add_argument("--asset-sheet-source", help="Generated chroma-key asset sheet to copy into the page folder")
    parser.add_argument("--chroma", default="imagegen_asset_sheet_chroma.png")
    parser.add_argument("--alpha", default="imagegen_asset_sheet_alpha.png")
    parser.add_argument("--skip-chroma", action="store_true", help="Use an existing alpha sheet instead of removing chroma")
    parser.add_argument("--force-chroma", action="store_true", help="Overwrite the alpha output if it already exists")
    parser.add_argument("--despill", action="store_true", help="Apply chroma despill; inspect colors because it can damage same-hue assets")
    parser.add_argument("--skip-split", action="store_true", help="Do not split the alpha sheet")
    parser.add_argument("--transparent-threshold", default="12")
    parser.add_argument("--opaque-threshold", default="220")
    parser.add_argument("--assets-dir", default="assets")
    parser.add_argument("--asset-names", help="Comma-separated split asset filenames")
    parser.add_argument("--split-sort", choices=["x", "y", "area"], default="x")
    parser.add_argument("--split-min-area", default="1000")
    parser.add_argument("--split-merge-gap", default="18")
    parser.add_argument("--split-merge-union-growth", default="2.4")
    parser.add_argument("--square-assets", action="store_true")
    parser.add_argument("--contact-sheet", default="split_assets_contact.png", help="Origin/preview QA image written by this script")
    parser.add_argument("--split-manifest", default="split_assets.json")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    if not page_dir.exists():
        raise SystemExit(f"Page folder does not exist: {page_dir}")

    process_asset_sheet(args, page_dir)
    with tempfile.TemporaryDirectory() as tmp:
        preview_path = Path(tmp) / "rendered-page.png"
        build_and_validate(args, page_dir, preview_path)
        write_qa(args, page_dir, preview_path)


if __name__ == "__main__":
    main()
