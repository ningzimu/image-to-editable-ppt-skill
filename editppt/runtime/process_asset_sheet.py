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
    parser = argparse.ArgumentParser(
        prog="editppt image process-sheet",
        description="Remove chroma key, split, and optionally crop an imagegen asset sheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  editppt image process-sheet <page_dir> --job-id icon-sheet-1 --asset-sheet-source assets/sheet.png --asset-names icon-a,icon-b
  editppt image process-sheet <page_dir> --skip-chroma --crop-source source.png --crop-box 120,80,240,180 --crop-out assets/icon.png --source-type source-derived-rasterization
""",
    )
    parser.add_argument("page_dir", help="Page directory that owns imagegen-jobs.json, manifest.json, and the assets folder.")
    parser.add_argument("--job-id", help="Image generation job id to mark as processed after splitting or cropping.")
    parser.add_argument("--asset-sheet-source", help="Generated sheet image to process. Defaults to the imported asset sheet recorded for --job-id when available.")
    parser.add_argument("--chroma", default="imagegen_asset_sheet_chroma.png", help="Intermediate chroma-key output path relative to page_dir.")
    parser.add_argument("--alpha", default="imagegen_asset_sheet_alpha.png", help="Transparent sheet output path relative to page_dir.")
    parser.add_argument("--skip-chroma", action="store_true", help="Skip chroma-key removal; useful when only cropping source.png or an already-transparent image.")
    parser.add_argument("--force-chroma", action="store_true", help="Run chroma-key removal even if the alpha output already exists.")
    parser.add_argument("--despill", action="store_true", help="Reduce remaining chroma color around extracted asset edges.")
    parser.add_argument("--skip-split", action="store_true", help="Do not auto-split connected alpha components; useful for manual crop-only calls.")
    parser.add_argument("--transparent-threshold", default="12", help="RGB distance threshold treated as fully transparent during chroma removal.")
    parser.add_argument("--opaque-threshold", default="220", help="RGB distance threshold treated as fully opaque during chroma removal.")
    parser.add_argument("--assets-dir", default="assets", help="Output directory for split or cropped assets, relative to page_dir.")
    parser.add_argument("--asset-names", help="Comma-separated names assigned to split assets in visual order.")
    parser.add_argument("--split-sort", choices=["x", "y", "area"], default="x", help="Sort extracted alpha components by x position, y position, or area.")
    parser.add_argument("--split-min-area", default="1000", help="Minimum connected-component pixel area to keep as an extracted asset.")
    parser.add_argument("--split-merge-gap", default="18", help="Merge nearby components separated by at most this many pixels.")
    parser.add_argument("--split-merge-union-growth", default="2.4", help="Maximum bounding-box growth ratio allowed when merging nearby components.")
    parser.add_argument("--square-assets", action="store_true", help="Pad split assets to square canvases.")
    parser.add_argument("--split-manifest", default="split_assets.json", help="JSON file that records split asset paths and bounding boxes.")
    parser.add_argument("--crop-box", type=parse_box, help="Manual crop box as left,top,right,bottom pixels in --crop-source coordinates.")
    parser.add_argument("--crop-source", default="imagegen_asset_sheet_alpha.png", help="Image to crop, relative to page_dir unless absolute.")
    parser.add_argument("--crop-out", help="Output path for --crop-box, relative to page_dir unless absolute.")
    parser.add_argument("--crop-padding", type=int, default=0, help="Extra pixels to include around --crop-box.")
    parser.add_argument("--crop-remove-border-bg", action="store_true", help="Remove a plain matte/background from the cropped asset edges.")
    parser.add_argument("--crop-matte-threshold", default="52", help="Color-distance threshold for detecting removable crop matte.")
    parser.add_argument("--crop-matte-soften", default="0.45", help="Softening factor for matte removal alpha edges.")
    parser.add_argument("--manifest", default="manifest.json", help="Manifest to update with crop provenance when using --crop-box.")
    parser.add_argument(
        "--source-type",
        default="imagegen",
        choices=["imagegen", "user-provided", "user-approved-rasterization", "source-derived-rasterization"],
        help="Provenance source type recorded in manifest when using --crop-box.",
    )
    parser.add_argument("--provenance-note", default="Cropped asset visually inspected.", help="Provenance note written to manifest for cropped assets.")
    parser.add_argument("--approval-note", help="Optional user or agent approval note written to manifest for cropped assets.")
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
