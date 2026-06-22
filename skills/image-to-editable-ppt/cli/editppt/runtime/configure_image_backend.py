#!/usr/bin/env python3
import argparse
import json

from deck_run_state import load_deck, load_jobs, read_json, run_dir_from_target, save_deck, write_json


def backend_contract(args):
    requires_api_key = args.backend_id == "openai-compatible-api"
    return {
        "backend_id": args.backend_id,
        "tool_name": args.tool_name,
        "tool_call": args.tool_call,
        "fallback_command": args.fallback_command,
        "runtime_home": args.runtime_home,
        "model": args.model,
        "requires_openai_api_key": requires_api_key,
        "mode_policy": "generate-or-edit-per-asset",
        "chroma_key_helper": "editppt image process-sheet",
        "input_context_policy": args.input_context_policy,
        "save_path_policy": "write outputs directly to page dir or copy selected outputs before manifest references them",
        "handoff_rule": "call editppt image generate/edit serially; the CLI selects Codex OAuth first and OpenAI-compatible API fallback second",
    }


def main():
    parser = argparse.ArgumentParser(description="Record the run-level image backend contract.")
    parser.add_argument("run")
    parser.add_argument("--backend-id", default="editppt-image-cli", choices=["editppt-image-cli", "openai-compatible-api"])
    parser.add_argument("--tool-name")
    parser.add_argument("--tool-call")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--fallback-command")
    parser.add_argument("--runtime-home", default="~/.editppt")
    parser.add_argument("--input-context-policy", default="pass edit targets and strict visual references via editppt image edit --image")
    args = parser.parse_args()

    if args.tool_name is None:
        args.tool_name = "editppt image"
    if args.tool_call is None:
        args.tool_call = "editppt image generate/edit"
    if args.fallback_command is None:
        args.fallback_command = "editppt image"

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    contract = backend_contract(args)
    deck["image_backend"] = contract
    save_deck(run_dir, deck)

    jobs = load_jobs(run_dir)
    for page in jobs.get("pages", []):
        request_path = run_dir / page["page_request"]
        request = read_json(request_path)
        request["image_backend"] = contract
        write_json(request_path, request)
    print(json.dumps({"image_backend": contract}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
