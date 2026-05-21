#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_box(value):
    parts = [int(round(float(part.strip()))) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--box must contain four comma-separated numbers")
    left, top, right, bottom = parts
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("--box must be left,top,right,bottom")
    return left, top, right, bottom


def append_provenance(manifest_path, asset_path, source_path, source_type, provenance_note, approval_note):
    manifest_file = Path(manifest_path)
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    else:
        manifest = {}
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
    entries.append(entry)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Crop one raster asset and optionally append manifest provenance.")
    parser.add_argument("--input", required=True, help="Source image path. Use this for imagegen asset sheets, not original slide crops.")
    parser.add_argument("--out", required=True, help="Output asset path.")
    parser.add_argument("--box", required=True, type=parse_box, help="Crop box as left,top,right,bottom pixels.")
    parser.add_argument("--manifest", help="Manifest JSON to update with asset_provenance.")
    parser.add_argument(
        "--source-type",
        default="imagegen",
        choices=["imagegen", "user-provided", "user-approved-rasterization"],
    )
    parser.add_argument("--provenance-note", default="Cropped asset visually inspected.")
    parser.add_argument("--qa-note", help=argparse.SUPPRESS)
    parser.add_argument("--approval-note")
    args = parser.parse_args()

    try:
        from PIL import Image
    except Exception as exc:
        raise SystemExit(f"Pillow is required for cropping assets: {exc}")

    source = Path(args.input)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(source)
    cropped = image.crop(args.box)
    cropped.save(out)

    if args.manifest:
        manifest_base = Path(args.manifest).resolve().parent
        asset_path = out
        source_path = source
        try:
            asset_path = out.resolve().relative_to(manifest_base)
        except ValueError:
            pass
        try:
            source_path = source.resolve().relative_to(manifest_base)
        except ValueError:
            pass
        append_provenance(
            args.manifest,
            asset_path,
            source_path,
            args.source_type,
            args.provenance_note or args.qa_note,
            args.approval_note,
        )

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
