#!/usr/bin/env python3
import argparse
import json

from deck_run_state import (
    find_page,
    inside_or_missing,
    load_jobs,
    now_iso,
    page_dir_for,
    read_json,
    rel_to_run,
    run_dir_from_target,
    save_jobs,
    set_run_status,
    sha256_file,
    update_jobs_run_status,
)


REQUIRED_OUTPUTS = {
    "page_manifest": "manifest.json",
    "imagegen_jobs": "imagegen-jobs.json",
    "page_pptx": "page.pptx",
    "preview": "preview.png",
    "contact_sheet": "split_assets_contact.png",
    "validation": "validation.json",
    "page_result": "page_result.json",
}


def output_path(page_dir, result, key, default):
    value = result.get(key) or default
    return inside_or_missing(page_dir, value)


def main():
    parser = argparse.ArgumentParser(description="Record and verify a page worker result.")
    parser.add_argument("run", help="Run directory or deck_manifest.json")
    parser.add_argument("--page", required=True, help="page_001 or 1")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--page-result", default="page_result.json")
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    jobs = load_jobs(run_dir)
    page = find_page(jobs, args.page)
    if page.get("status") not in {"dispatched", "repair_dispatched"}:
        raise SystemExit(f"{page['page_id']} must be dispatched before result recording; got {page.get('status')}")
    dispatch = page.get("dispatch") or {}
    if dispatch.get("agent_id") != args.agent_id:
        raise SystemExit(
            f"Agent id mismatch for {page['page_id']}: dispatch={dispatch.get('agent_id')} result={args.agent_id}"
        )

    page_dir = page_dir_for(run_dir, page)
    page_result_path = inside_or_missing(page_dir, args.page_result)
    result = read_json(page_result_path)
    paths = {key: output_path(page_dir, result, key, default) for key, default in REQUIRED_OUTPUTS.items()}

    validation = read_json(paths["validation"])
    validation_passed = validation.get("passed") is True
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    page["result"] = {
        "agent_id": args.agent_id,
        "recorded_at": now_iso(),
        "outputs": {key: rel_to_run(run_dir, path) for key, path in paths.items()},
        "hashes": hashes,
        "validation_passed": validation_passed,
        "qa_note": result.get("qa_note"),
        "known_limits": result.get("known_limits", []),
    }
    page["status"] = "recorded"
    update_jobs_run_status(jobs)
    save_jobs(run_dir, jobs)
    if jobs.get("run_status") == "pages_recorded":
        set_run_status(run_dir, "pages_recorded", "all pages recorded")
    print(json.dumps({"page_id": page["page_id"], "status": "recorded", "validation_passed": validation_passed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
