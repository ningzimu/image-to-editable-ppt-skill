import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command):
    print("+ " + " ".join(str(part) for part in command), flush=True)
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
        command = [
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
            command.append("--despill")
        if args.force_chroma:
            command.append("--force")
        run(command)

    if args.skip_split:
        return
    if not alpha.exists():
        raise SystemExit(f"Alpha sheet does not exist: {alpha}")

    command = [
        sys.executable,
        SCRIPT_DIR / "split_alpha_components.py",
        "--input",
        alpha,
        "--out-dir",
        resolve_under_page(page_dir, args.assets_dir),
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
        command.append("--square")
    if args.asset_names:
        command.extend(["--names", args.asset_names])
    run(command)


def parse_box(value):
    parts = [int(round(float(part.strip()))) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop box must contain four comma-separated numbers")
    left, top, right, bottom = parts
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("crop box must be left,top,right,bottom")
    return left, top, right, bottom


def append_provenance(
    manifest_path,
    asset_path,
    source_path,
    source_type,
    provenance_note,
    approval_note,
    source_region_px=None,
):
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    entries = manifest.setdefault("asset_provenance", [])
    asset_key = Path(asset_path).as_posix()
    entries[:] = [entry for entry in entries if Path(entry.get("path", "")).as_posix() != asset_key]
    entry = {
        "path": asset_key,
        "source": str(source_path),
        "source_type": source_type,
        "provenance_note": provenance_note,
    }
    if approval_note:
        entry["approval_note"] = approval_note
    if source_region_px:
        entry["source_region_px"] = list(source_region_px)
    entries.append(entry)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def padded_box(box, padding, image_size):
    left, top, right, bottom = box
    width, height = image_size
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(width, right + padding),
        min(height, bottom + padding),
    )


def remove_border_background(image, threshold=52, soften=0.45):
    from PIL import ImageFilter

    crop = image.convert("RGBA")
    pixels = crop.load()
    width, height = crop.size
    if width <= 0 or height <= 0:
        return crop

    border_samples = []
    for px in range(width):
        border_samples.append(crop.getpixel((px, 0))[:3])
        border_samples.append(crop.getpixel((px, height - 1))[:3])
    for py in range(height):
        border_samples.append(crop.getpixel((0, py))[:3])
        border_samples.append(crop.getpixel((width - 1, py))[:3])
    bg = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*border_samples))

    for py in range(height):
        for px in range(width):
            r, g, b, _a = pixels[px, py]
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            brightness = (r + g + b) / 3
            alpha = 0 if dist < threshold and brightness > 140 else 255
            if alpha and dist < threshold + 18 and brightness > 165:
                alpha = int(max(0, min(255, (dist - threshold) / 18 * 255)))
            pixels[px, py] = (r, g, b, alpha)

    if soften:
        alpha = crop.getchannel("A").filter(ImageFilter.GaussianBlur(soften))
        crop.putalpha(alpha)
    return crop


def crop_asset(
    page_dir,
    source,
    out,
    box,
    manifest=None,
    source_type="imagegen",
    provenance_note=None,
    approval_note=None,
    crop_padding=0,
    remove_border_bg=False,
    matte_threshold=52,
    matte_soften=0.45,
):
    from PIL import Image

    source_path = resolve_under_page(page_dir, source)
    out_path = resolve_under_page(page_dir, out)
    if not source_path.exists():
        raise SystemExit(f"Crop source does not exist: {source_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    source_image = Image.open(source_path)
    crop_box = padded_box(box, int(crop_padding or 0), source_image.size)
    cropped = source_image.crop(crop_box)
    if remove_border_bg:
        cropped = remove_border_background(cropped, threshold=float(matte_threshold), soften=float(matte_soften))
    cropped.save(out_path)

    if manifest:
        manifest_path = resolve_under_page(page_dir, manifest)
        manifest_base = manifest_path.resolve().parent
        asset_ref = out_path
        source_ref = source_path
        try:
            asset_ref = out_path.resolve().relative_to(manifest_base)
        except ValueError:
            pass
        try:
            source_ref = source_path.resolve().relative_to(manifest_base)
        except ValueError:
            pass
        append_provenance(
            manifest_path,
            asset_ref,
            source_ref,
            source_type,
            provenance_note or "Cropped asset visually inspected.",
            approval_note,
            source_region_px=(crop_box[0], crop_box[1], crop_box[2] - crop_box[0], crop_box[3] - crop_box[1]),
        )
    print(f"Wrote {out_path}")
    return out_path


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
