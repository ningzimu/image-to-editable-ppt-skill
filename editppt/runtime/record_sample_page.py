#!/usr/bin/env python3
import argparse
import json

from deck_run_state import (
    find_page,
    inside_or_missing,
    load_deck,
    load_jobs,
    now_iso,
    page_dir_for,
    read_json,
    rel_to_run,
    run_dir_from_target,
    save_deck,
    save_jobs,
    sha256_file,
    update_jobs_run_status,
    write_json,
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
    return inside_or_missing(page_dir, result.get(key) or default)


def main():
    parser = argparse.ArgumentParser(description="Record a main-agent sample page result.")
    parser.add_argument("run")
    parser.add_argument("--page", required=True)
    parser.add_argument("--page-result", default="page_result.json")
    parser.add_argument("--feedback", action="append", default=[])
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    jobs = load_jobs(run_dir)
    page = find_page(jobs, args.page)
    if page.get("status") not in {"pending", "recorded"}:
        raise SystemExit(f"{page['page_id']} must be pending or recorded for sample recording; got {page.get('status')}")

    page_dir = page_dir_for(run_dir, page)
    page_result_path = inside_or_missing(page_dir, args.page_result)
    result = read_json(page_result_path)
    paths = {key: output_path(page_dir, result, key, default) for key, default in REQUIRED_OUTPUTS.items()}

    validation = read_json(paths["validation"])
    if validation.get("passed") is not True:
        raise SystemExit(f"{page['page_id']} validation must pass before sample approval")

    hashes = {key: sha256_file(path) for key, path in paths.items()}
    page["result"] = {
        "agent_id": "main-agent",
        "recorded_at": now_iso(),
        "outputs": {key: rel_to_run(run_dir, path) for key, path in paths.items()},
        "hashes": hashes,
        "validation_passed": True,
        "qa_note": result.get("qa_note"),
        "known_limits": result.get("known_limits", []),
    }
    page["status"] = "recorded"
    page["sample_page_approved"] = True
    page["sample_page_approved_at"] = now_iso()

    feedback = deck.setdefault("user_requirements_and_feedback", [])
    for item in args.feedback:
        text = str(item).strip()
        if text and text not in feedback:
            feedback.append(text)

    for other in jobs.get("pages", []):
        if other.get("page_id") == page.get("page_id"):
            continue
        request_path = run_dir / other["page_request"]
        request = read_json(request_path)
        request["user_requirements_and_feedback"] = list(feedback)
        if deck.get("image_backend"):
            request["image_backend"] = deck["image_backend"]
        write_json(request_path, request)

    update_jobs_run_status(jobs)
    save_jobs(run_dir, jobs)
    save_deck(run_dir, deck)
    print(json.dumps({"page_id": page["page_id"], "status": "recorded", "sample_page_approved": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
