#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

from deck_run_state import now_iso, read_json, resolve_inside, sha256_file, write_json


def main():
    parser = argparse.ArgumentParser(description="Copy a selected $imagegen output into a page directory and record provenance.")
    parser.add_argument("page_dir")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--dest", required=True, help="Destination path relative to page_dir")
    parser.add_argument("--role", default="asset", help="clean_base, asset_sheet, repair_asset, etc.")
    parser.add_argument("--prompt-file")
    parser.add_argument("--note")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    if not page_dir.exists():
        raise SystemExit(f"Page dir does not exist: {page_dir}")
    source = Path(args.source_image).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Generated image does not exist: {source}")
    dest = resolve_inside(page_dir, args.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source != dest:
        shutil.copy2(source, dest)

    jobs_path = page_dir / "imagegen-jobs.json"
    jobs = read_json(jobs_path, default={"schema_version": 1, "jobs": []})
    existing = None
    for item in jobs.get("jobs", []):
        if item.get("job_id") == args.job_id:
            existing = item
            break
    if existing is None:
        existing = {"job_id": args.job_id}
        jobs.setdefault("jobs", []).append(existing)
    existing.update(
        {
            "role": args.role,
            "status": "recorded",
            "source_image": str(source),
            "output": dest.relative_to(page_dir).as_posix(),
            "output_sha256": sha256_file(dest),
            "prompt_file": args.prompt_file,
            "note": args.note,
            "recorded_at": now_iso(),
        }
    )
    jobs["updated_at"] = now_iso()
    write_json(jobs_path, jobs)
    print(dest)


if __name__ == "__main__":
    main()
