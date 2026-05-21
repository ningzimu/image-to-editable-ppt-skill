#!/usr/bin/env python3
import argparse
from pathlib import Path

from deck_run_state import now_iso, read_json, write_json
from _page_artifacts import crop_asset, parse_box, process_asset_sheet as process_sheet


def mark_processed(page_dir, args, crop_output=None):
    if not args.job_id:
        return
    jobs_path = page_dir / "imagegen-jobs.json"
    jobs = read_json(jobs_path, default={"schema_version": 1, "jobs": []})
    for item in jobs.get("jobs", []):
        if item.get("job_id") == args.job_id:
            item.update(
                {
                    "status": "processed",
                    "processed_at": now_iso(),
                    "alpha": args.alpha,
                    "assets_dir": args.assets_dir,
                    "split_manifest": args.split_manifest,
                    "crop_output": crop_output,
                }
            )
            break
    else:
        jobs.setdefault("jobs", []).append(
            {
                "job_id": args.job_id,
                "role": "asset_sheet",
                "status": "processed",
                "processed_at": now_iso(),
                "alpha": args.alpha,
                "assets_dir": args.assets_dir,
                "split_manifest": args.split_manifest,
                "crop_output": crop_output,
            }
        )
    jobs["updated_at"] = now_iso()
    write_json(jobs_path, jobs)


def main():
    parser = argparse.ArgumentParser(description="Remove chroma key, split, and optionally crop an imagegen asset sheet.")
    parser.add_argument("page_dir")
    parser.add_argument("--job-id")
    parser.add_argument("--asset-sheet-source")
    parser.add_argument("--chroma", default="imagegen_asset_sheet_chroma.png")
    parser.add_argument("--alpha", default="imagegen_asset_sheet_alpha.png")
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--force-chroma", action="store_true")
    parser.add_argument("--despill", action="store_true")
    parser.add_argument("--skip-split", action="store_true")
    parser.add_argument("--transparent-threshold", default="12")
    parser.add_argument("--opaque-threshold", default="220")
    parser.add_argument("--assets-dir", default="assets")
    parser.add_argument("--asset-names")
    parser.add_argument("--split-sort", choices=["x", "y", "area"], default="x")
    parser.add_argument("--split-min-area", default="1000")
    parser.add_argument("--split-merge-gap", default="18")
    parser.add_argument("--split-merge-union-growth", default="2.4")
    parser.add_argument("--square-assets", action="store_true")
    parser.add_argument("--split-manifest", default="split_assets.json")
    parser.add_argument("--crop-box", type=parse_box, help="Optional manual crop box as left,top,right,bottom pixels")
    parser.add_argument("--crop-source", default="imagegen_asset_sheet_alpha.png")
    parser.add_argument("--crop-out", help="Output path for --crop-box, relative to page_dir unless absolute")
    parser.add_argument("--crop-padding", type=int, default=0)
    parser.add_argument("--crop-remove-border-bg", action="store_true")
    parser.add_argument("--crop-matte-threshold", default="52")
    parser.add_argument("--crop-matte-soften", default="0.45")
    parser.add_argument("--manifest", default="manifest.json", help="Manifest to update when using --crop-box")
    parser.add_argument(
        "--source-type",
        default="imagegen",
        choices=["imagegen", "user-provided", "user-approved-rasterization", "source-derived-rasterization"],
    )
    parser.add_argument("--provenance-note", default="Cropped asset visually inspected.")
    parser.add_argument("--approval-note")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    if not page_dir.exists():
        raise SystemExit(f"Page folder does not exist: {page_dir}")
    process_sheet(args, page_dir)
    crop_output = None
    if args.crop_box:
        if not args.crop_out:
            raise SystemExit("--crop-out is required with --crop-box")
        crop_output = str(
            crop_asset(
                page_dir,
                args.crop_source,
                args.crop_out,
                args.crop_box,
                manifest=args.manifest,
                source_type=args.source_type,
                provenance_note=args.provenance_note,
                approval_note=args.approval_note,
                crop_padding=args.crop_padding,
                remove_border_bg=args.crop_remove_border_bg,
                matte_threshold=args.crop_matte_threshold,
                matte_soften=args.crop_matte_soften,
            )
        )
    mark_processed(page_dir, args, crop_output=crop_output)


if __name__ == "__main__":
    main()
