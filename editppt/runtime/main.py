#!/usr/bin/env python3
"""Unified CLI for the image-to-editable-ppt skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from deck_run_state import (
    dispatch_slots_available,
    dispatchable_pages,
    load_deck,
    load_jobs,
    load_run_state,
    run_dir_from_target,
)


RUNTIME_DIR = Path(__file__).resolve().parent
HELP_FORMATTER = argparse.RawDescriptionHelpFormatter
SKILL_REPO = "ningzimu/image-to-editable-ppt-skill"
SKILL_NAME = "image-to-editable-ppt"
PACKAGE_NAME = "image-to-editable-ppt"


def skill_root() -> Path:
    env_root = os.environ.get("IMAGE_TO_EDITABLE_PPT_SKILL_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    packaged = RUNTIME_DIR.parent / "skill"
    if packaged.exists():
        return packaged.resolve()
    source = RUNTIME_DIR.parents[1] / "skills" / "image-to-editable-ppt"
    if source.exists():
        return source.resolve()
    raise RuntimeError("Could not locate image-to-editable-ppt skill resources.")


SKILL_ROOT = skill_root()


def run_script(script_name: str, argv: list[str]) -> int:
    command = [sys.executable, str(RUNTIME_DIR / script_name), *[str(item) for item in argv]]
    return subprocess.run(command).returncode


def cli_prog() -> str:
    return os.environ.get("IMAGE_TO_EDITABLE_PPT_CLI_PROG", "editppt")


def print_json(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    argv = ["doctor"]
    if args.check_api:
        argv.append("--check-api")
    if args.json:
        argv.append("--json")
    if args.timeout is not None:
        argv.extend(["--timeout", str(args.timeout)])
    return run_script("runtime_env.py", argv)


def cmd_config(args: argparse.Namespace) -> int:
    argv = ["config"]
    if args.api_key:
        argv.extend(["--api-key", args.api_key])
    if args.base_url:
        argv.extend(["--base-url", args.base_url])
    if args.clear_base_url:
        argv.append("--clear-base-url")
    if args.model:
        argv.extend(["--model", args.model])
    if args.import_codex_ppt:
        argv.append("--import-codex-ppt")
    return run_script("runtime_env.py", argv)


def cmd_setup(args: argparse.Namespace) -> int:
    config = subprocess.run(
        [sys.executable, str(RUNTIME_DIR / "runtime_env.py"), "config"],
        text=True,
        capture_output=True,
    )
    doctor_args = ["doctor", "--json"]
    if args.check_api:
        doctor_args.append("--check-api")
    doctor = subprocess.run(
        [sys.executable, str(RUNTIME_DIR / "runtime_env.py"), *doctor_args],
        text=True,
        capture_output=True,
    )
    try:
        doctor_payload = json.loads(doctor.stdout)
    except json.JSONDecodeError:
        doctor_payload = {
            "ok": False,
            "stdout": doctor.stdout,
            "stderr": doctor.stderr,
        }
    payload = {
        "setup": "ok" if config.returncode == 0 and doctor.returncode == 0 else "needs_attention",
        "config": {
            "ok": config.returncode == 0,
            "stdout": config.stdout,
            "stderr": config.stderr,
        },
        "doctor": doctor_payload,
    }
    return print_json(payload)


def _strip_remainder(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _print_or_run_external(command: list[str], dry_run: bool) -> int:
    if dry_run:
        print(" ".join(command))
        return 0
    return subprocess.run(command).returncode


def _skills_command(action: str, args: argparse.Namespace) -> list[str]:
    command = [
        "npx",
        "-y",
        "skills@latest",
        action,
        SKILL_REPO,
        "--skill",
        SKILL_NAME,
        "--agent",
        args.agent,
    ]
    if getattr(args, "global_install", True):
        command.append("--global")
    command.extend(_strip_remainder(getattr(args, "extra_args", [])))
    return command


def cmd_install(args: argparse.Namespace) -> int:
    return _print_or_run_external(_skills_command("add", args), args.dry_run)


def cmd_uninstall(args: argparse.Namespace) -> int:
    return _print_or_run_external(_skills_command("remove", args), args.dry_run)


def _editable_source() -> str | None:
    try:
        from importlib import metadata
    except ImportError:
        return None
    try:
        dist = metadata.distribution(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return None
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return None
    if not payload.get("dir_info", {}).get("editable"):
        return None
    url = payload.get("url", "")
    if url.startswith("file://"):
        return url.removeprefix("file://")
    return url or None


def _pipx_upgrade_command() -> list[str]:
    pipx = shutil.which("pipx") or "pipx"
    return [pipx, "upgrade", PACKAGE_NAME]


def cmd_update(args: argparse.Namespace) -> int:
    if args.cli_only and args.skill_only:
        print("--cli-only and --skill-only cannot be used together", file=sys.stderr)
        return 2
    if args.skill_only and not args.agent:
        print("--skill-only requires --agent", file=sys.stderr)
        return 2

    update_cli = not args.skill_only
    update_skill = bool(args.agent) and not args.cli_only
    results = []

    if update_cli:
        editable = _editable_source()
        if editable:
            message = f"cli=editable source={editable} action=update-source-repo"
            print(message)
            results.append(0)
        else:
            results.append(_print_or_run_external(_pipx_upgrade_command(), args.dry_run))

    if update_skill:
        results.append(_print_or_run_external(_skills_command("add", args), args.dry_run))

    return 0 if all(code == 0 for code in results) else 1


def cmd_prepare(args: argparse.Namespace) -> int:
    argv = []
    if args.out_root:
        argv.extend(["--out-root", args.out_root])
    if args.job_dir:
        argv.extend(["--job-dir", args.job_dir])
    if args.dpi:
        argv.extend(["--dpi", str(args.dpi)])
    if args.max_concurrent_pages:
        argv.extend(["--max-concurrent-pages", str(args.max_concurrent_pages)])
    argv.extend(args.inputs)
    command = [sys.executable, str(RUNTIME_DIR / "prepare_deck_run.py"), *[str(item) for item in argv]]
    prepared = subprocess.run(command, text=True, capture_output=True)
    if prepared.stdout:
        print(prepared.stdout, end="")
    if prepared.stderr:
        print(prepared.stderr, end="", file=sys.stderr)
    if prepared.returncode != 0:
        return prepared.returncode
    lines = [line.strip() for line in prepared.stdout.splitlines() if line.strip()]
    if not lines:
        print("prepare did not report a deck_manifest.json path", file=sys.stderr)
        return 1
    deck_path = Path(lines[0])
    if not deck_path.exists():
        print(f"prepare reported a missing deck_manifest.json path: {deck_path}", file=sys.stderr)
        return 1
    return cmd_backend(
        argparse.Namespace(
            run=str(deck_path.parent),
            mode="built-in-image-tool",
            tool_name=None,
            tool_call=None,
            model=None,
            fallback_command=None,
            runtime_home=None,
            input_context_policy=None,
        )
    )


def cmd_backend(args: argparse.Namespace) -> int:
    argv = [args.run]
    if args.mode:
        argv.extend(["--backend-id", args.mode])
    if args.tool_name:
        argv.extend(["--tool-name", args.tool_name])
    if args.tool_call:
        argv.extend(["--tool-call", args.tool_call])
    if args.model:
        argv.extend(["--model", args.model])
    if args.fallback_command:
        argv.extend(["--fallback-command", args.fallback_command])
    if args.runtime_home:
        argv.extend(["--runtime-home", args.runtime_home])
    if args.input_context_policy:
        argv.extend(["--input-context-policy", args.input_context_policy])
    return run_script("configure_image_backend.py", argv)


def cmd_image_api(args: argparse.Namespace) -> int:
    return run_script("image_gen.py", [args.image_command, *args.image_args])


def cmd_process_asset_sheet(args: argparse.Namespace) -> int:
    return run_script("process_asset_sheet.py", args.process_args)


def cmd_record_image(args: argparse.Namespace) -> int:
    return run_script("record_imagegen_result.py", args.record_image_args)


def cmd_crop_image(args: argparse.Namespace) -> int:
    argv = [
        args.page_dir,
        "--skip-chroma",
        "--skip-split",
        "--crop-source",
        args.source,
        "--crop-box",
        args.box,
        "--crop-out",
        args.out,
    ]
    if args.job_id:
        argv.extend(["--job-id", args.job_id])
    if args.padding:
        argv.extend(["--crop-padding", str(args.padding)])
    if args.remove_border_bg:
        argv.append("--crop-remove-border-bg")
    if args.manifest:
        argv.extend(["--manifest", args.manifest])
    if args.source_type:
        argv.extend(["--source-type", args.source_type])
    if args.provenance_note:
        argv.extend(["--provenance-note", args.provenance_note])
    if args.approval_note:
        argv.extend(["--approval-note", args.approval_note])
    return run_script("process_asset_sheet.py", argv)


def cmd_queue_repairs(args: argparse.Namespace) -> int:
    return run_script("queue_page_repairs.py", args.repair_args)


def cmd_status(args: argparse.Namespace) -> int:
    argv = [args.run]
    if args.json:
        argv.append("--json")
    return run_script("page_job_status.py", argv)


def cmd_next(args: argparse.Namespace) -> int:
    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    jobs = load_jobs(run_dir)
    state = load_run_state(run_dir)
    backend = deck.get("image_backend")
    dispatchable = [page.get("page_id") for page in dispatchable_pages(jobs)]
    slots = dispatch_slots_available(jobs)
    pages = jobs.get("pages", [])

    if not backend:
        payload = {
            "run_dir": str(run_dir),
            "stage": "configure_backend",
            "next_command": f"{cli_prog()} run backend {run_dir}",
            "reason": "deck_manifest.json.image_backend is missing",
            "agent_focus": "No page reconstruction yet. Confirm the image backend first.",
        }
        return print_json(payload) if args.json else _print_next_text(payload)

    if dispatchable and slots > 0:
        selected = dispatchable[:slots]
        prompt_out = Path(tempfile.gettempdir()) / f"{selected[0]}_prompt.md"
        payload = {
            "run_dir": str(run_dir),
            "stage": "dispatch_pages",
            "dispatch_slots_available": slots,
            "dispatchable_pages": dispatchable,
            "suggested_pages": selected,
            "next_command": f"{cli_prog()} run prompt {run_dir} --page {selected[0]} --out {prompt_out}",
            "agent_focus": "Generate page-worker prompts, spawn workers, then record dispatch.",
        }
        return print_json(payload) if args.json else _print_next_text(payload)

    unfinished = [
        f"{page.get('page_id')}:{page.get('status')}"
        for page in pages
        if page.get("status") not in {"recorded", "accepted"}
    ]
    if unfinished:
        payload = {
            "run_dir": str(run_dir),
            "stage": "wait_or_repair",
            "active_or_unfinished_pages": unfinished,
            "next_command": f"{cli_prog()} run status {run_dir}",
            "agent_focus": "Wait for dispatched workers, record results, or queue repairs.",
        }
        return print_json(payload) if args.json else _print_next_text(payload)

    payload = {
        "run_dir": str(run_dir),
        "stage": "finalize",
        "run_status": state.get("status"),
        "next_command": f"{cli_prog()} run finalize {run_dir}",
        "agent_focus": "All pages are recorded. Build and validate the final PPTX.",
    }
    return print_json(payload) if args.json else _print_next_text(payload)


def _print_next_text(payload: dict) -> int:
    print(f"stage={payload.get('stage')}")
    print(f"run_dir={payload.get('run_dir')}")
    if payload.get("reason"):
        print(f"reason={payload['reason']}")
    if payload.get("dispatchable_pages"):
        print(f"dispatchable_pages={', '.join(payload['dispatchable_pages'])}")
    if payload.get("suggested_pages"):
        print(f"suggested_pages={', '.join(payload['suggested_pages'])}")
    if payload.get("active_or_unfinished_pages"):
        print(f"active_or_unfinished_pages={', '.join(payload['active_or_unfinished_pages'])}")
    print(f"next_command={payload.get('next_command')}")
    print(f"agent_focus={payload.get('agent_focus')}")
    return 0


def cmd_prompt_page(args: argparse.Namespace) -> int:
    run_dir = run_dir_from_target(args.run)
    page_id = args.page if str(args.page).startswith("page_") else f"page_{int(args.page):03d}"
    content = f"""Rebuild {page_id} for image-to-editable-ppt.

Run directory: {run_dir}
Page id: {page_id}

Read:
- pages/{page_id}/page_request.json
- pages/{page_id}/source.png
- references/page-decision-tree.md
- references/image-backend-integration.md
- references/workflow-contract.md
- references/manifest-schema.md
- references/qa-rubric.md
- prompts/page-worker.md

Only write inside pages/{page_id}/.
Use page_request.json.image_backend exactly. If it is unavailable, return a blocker.
Required outputs: manifest.json, imagegen-jobs.json, page.pptx, preview.png,
split_assets_contact.png, validation.json, page_result.json.
"""
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return print_json({"prompt": str(out), "page_id": page_id, "run_dir": str(run_dir)})


def cmd_dispatch(args: argparse.Namespace) -> int:
    argv = [args.run, "--page", args.page, "--agent-id", args.agent_id, "--prompt-file", args.prompt_file]
    if args.agent_nickname:
        argv.extend(["--agent-nickname", args.agent_nickname])
    if args.repair_item_id:
        argv.extend(["--repair-item-id", args.repair_item_id])
    return run_script("record_page_dispatch.py", argv)


def cmd_record(args: argparse.Namespace) -> int:
    return run_script(
        "record_page_result.py",
        [args.run, "--page", args.page, "--agent-id", args.agent_id, "--page-result", args.page_result],
    )


def cmd_sample(args: argparse.Namespace) -> int:
    argv = [args.run, "--page", args.page]
    if args.feedback:
        argv.extend(["--feedback", args.feedback])
    return run_script("record_sample_page.py", argv)


def cmd_finalize(args: argparse.Namespace) -> int:
    return run_script("finalize_deck_run.py", [args.run])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("IMAGE_TO_EDITABLE_PPT_CLI_PROG", "editppt"),
        description="Agent-friendly CLI for converting visual slide inputs into editable PPTX runs.",
        formatter_class=HELP_FORMATTER,
        epilog="""What this CLI does:
  - setup/doctor/config manage the local editppt environment and API fallback config.
  - install/uninstall/update delegate Skill installation to npx skills@latest.
  - prepare creates a run directory and writes the default built-in image backend.
  - run manages deterministic workflow state, prompts, dispatch records, and finalization.
  - image handles third-party API image fallback and deterministic image file processing.

Typical workflow:
  editppt setup
  editppt install --agent codex
  editppt prepare deck.pdf
  editppt run next <run>
  editppt run finalize <run>

Use '<command> --help' for exact arguments. For example:
  editppt install --help
  editppt prepare --help
  editppt run --help
  editppt image --help
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command", required=True)

    setup = sub.add_parser(
        "setup",
        help="Initialize local config and run doctor.",
        description="""Initialize the local editppt environment without installing the Skill.

Use this after installing the CLI, or when checking whether the local runtime can run.
It creates/checks ~/.editppt/config.yaml, preserves existing values, and runs doctor.
It does not call npx, does not install the Skill, and does not require API credentials
unless --check-api is passed.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt setup
  editppt setup --check-api
""",
    )
    setup.add_argument("--check-api", action="store_true", help="Require API fallback credentials in doctor.")
    setup.set_defaults(func=cmd_setup)

    install = sub.add_parser(
        "install",
        help="Install the Skill through npx skills@latest.",
        description="""Install image-to-editable-ppt for any agent supported by skills@latest.

editppt does not keep an agent allowlist. The --agent value is passed through to
`npx -y skills@latest add`. Extra args after `--` are appended unchanged.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt install --agent codex
  editppt install --agent claude-code -- --local
  editppt install --agent opencode --dry-run
""",
    )
    install.add_argument("--agent", required=True, metavar="AGENT", help="Agent id passed to npx skills@latest, for example codex, claude-code, or opencode.")
    install.add_argument("--dry-run", action="store_true", help="Print the npx command without executing it.")
    install.add_argument("--no-global", dest="global_install", action="store_false", help="Do not add --global to the npx skills command.")
    install.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args after -- are passed through to npx skills@latest.")
    install.set_defaults(global_install=True)
    install.set_defaults(func=cmd_install)

    uninstall = sub.add_parser(
        "uninstall",
        help="Uninstall the Skill through npx skills@latest.",
        description="""Uninstall/remove image-to-editable-ppt for an agent via skills@latest.

editppt does not delete agent-specific directories itself. It delegates to
`npx -y skills@latest remove` and surfaces that command's result.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt uninstall --agent codex --dry-run
  editppt uninstall --agent claude-code -- --local
""",
    )
    uninstall.add_argument("--agent", required=True, metavar="AGENT", help="Agent id passed to npx skills@latest.")
    uninstall.add_argument("--dry-run", action="store_true", help="Print the npx command without executing it.")
    uninstall.add_argument("--no-global", dest="global_install", action="store_false", help="Do not add --global to the npx skills command.")
    uninstall.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args after -- are passed through to npx skills@latest.")
    uninstall.set_defaults(global_install=True)
    uninstall.set_defaults(func=cmd_uninstall)

    update = sub.add_parser(
        "update",
        help="Update the CLI and optionally the installed Skill.",
        description="""Update editppt itself and/or the installed Skill.

Without --agent, update checks the CLI only. With --agent, editppt updates the CLI
and delegates Skill update/install to npx skills@latest. In editable installs,
editppt reports the source path instead of running pipx upgrade.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt update --dry-run
  editppt update --agent codex --dry-run
  editppt update --skill-only --agent claude-code -- --local
""",
    )
    update.add_argument("--agent", metavar="AGENT", help="Agent id passed to npx skills@latest for Skill update.")
    update.add_argument("--cli-only", action="store_true", help="Update/check only the CLI package.")
    update.add_argument("--skill-only", action="store_true", help="Update/install only the Skill. Requires --agent.")
    update.add_argument("--dry-run", action="store_true", help="Print planned external commands without executing them.")
    update.add_argument("--no-global", dest="global_install", action="store_false", help="Do not add --global to the npx skills command.")
    update.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args after -- are passed through to npx skills@latest.")
    update.set_defaults(global_install=True)
    update.set_defaults(func=cmd_update)

    doctor = sub.add_parser(
        "doctor",
        help="Check CLI dependencies and config status.",
        description="""Check the local editppt environment.

Doctor reports the CLI Python path, importable dependencies, Skill root, config
home/file, and API fallback readiness when --check-api is passed. It does not
perform a network API probe by default.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt doctor
  editppt doctor --json
  editppt doctor --check-api
""",
    )
    doctor.add_argument("--check-api", action="store_true", help="Require API fallback credentials to be configured.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    doctor.add_argument("--timeout", type=int, help="Reserved timeout value for future network probes.")
    doctor.set_defaults(func=cmd_doctor)

    config = sub.add_parser(
        "config",
        help="Write or update ~/.editppt/config.yaml.",
        description="""Configure API fallback values used by editppt image commands.

Values are written to ~/.editppt/config.yaml. Environment variables still win at
runtime. API keys are masked in command output.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt config --api-key "your-api-key" --model gpt-image-2
  editppt config --api-key "your-api-key" --base-url https://example.test/v1 --model openai/gpt-image-2
  editppt config --clear-base-url
""",
    )
    config.add_argument("--api-key", help="OpenAI or OpenAI-compatible API key to store.")
    config.add_argument("--base-url", help="OpenAI-compatible base URL, for example https://api.openai.com/v1.")
    config.add_argument("--clear-base-url", action="store_true", help="Remove OPENAI_BASE_URL from the config file.")
    config.add_argument("--model", help="Default image model for API fallback.")
    config.add_argument("--import-codex-ppt", action="store_true", help="Import compatible values from ~/.codex-ppt-skill/.env when present.")
    config.set_defaults(func=cmd_config)

    prepare = sub.add_parser(
        "prepare",
        help="Prepare a run directory from image/PDF/PPTX input.",
        description="""Normalize input into an editable-PPT reconstruction run.

This command creates the run directory, copies inputs, writes deck/page manifests,
extracts note metadata when applicable, and records the default built-in image
backend. The normal path does not require a separate backend command.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt prepare slide.png
  editppt prepare deck.pdf --max-concurrent-pages 3
  editppt prepare a.png b.png --out-root output/image-to-editable-ppt
""",
    )
    prepare.add_argument("inputs", nargs="+", metavar="INPUT", help="Input image, PDF, PPT, or PPTX path. Repeat for multiple images.")
    prepare.add_argument("--out-root", metavar="DIR", help="Directory that will contain generated run folders.")
    prepare.add_argument("--job-dir", metavar="DIR", help="Use an explicit run directory instead of auto-generating one.")
    prepare.add_argument("--dpi", type=int, metavar="N", help="Rasterization DPI for PDF/PPT inputs.")
    prepare.add_argument("--max-concurrent-pages", type=int, metavar="N", help="Maximum page workers the parent agent may dispatch at once.")
    prepare.set_defaults(func=cmd_prepare)

    run = sub.add_parser(
        "run",
        help="Manage run state, worker prompts, dispatch records, and finalization.",
        description="""Deterministic workflow commands for a prepared run.

Use these commands after editppt prepare. They inspect and update run/page state,
generate worker prompts, record worker lifecycle events, queue repairs, and
assemble the final deck.
""",
        formatter_class=HELP_FORMATTER,
    )
    run_sub = run.add_subparsers(dest="run_command", metavar="run-command", required=True)

    run_next = run_sub.add_parser(
        "next",
        help="Print the next workflow action.",
        description="Inspect run state and print the next command the parent agent should run.",
        formatter_class=HELP_FORMATTER,
    )
    run_next.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    run_next.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    run_next.set_defaults(func=cmd_next)

    status = run_sub.add_parser(
        "status",
        help="Show page dispatch and repair status.",
        description="Read page_jobs.json and print active, pending, blocked, and dispatchable pages without modifying state.",
        formatter_class=HELP_FORMATTER,
    )
    status.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    status.set_defaults(func=cmd_status)

    backend = run_sub.add_parser(
        "backend",
        help="Override the run image backend contract.",
        description="""Configure deck_manifest.json.image_backend and copy it into page requests.

Normally editppt prepare records the built-in image backend automatically. Use
this only when switching to API fallback or a custom image backend.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt run backend <run>
  editppt run backend <run> --mode cli-api-fallback --model gpt-image-2
""",
    )
    backend.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    backend.add_argument("--mode", choices=["built-in-image-tool", "cli-api-fallback"], default="built-in-image-tool", help="Image backend mode. Defaults to the Codex built-in image tool contract.")
    backend.add_argument("--tool-name", metavar="NAME", help="Override backend tool name recorded in the contract.")
    backend.add_argument("--tool-call", metavar="CALL", help="Override backend tool call recorded in the contract.")
    backend.add_argument("--model", metavar="MODEL", help="Image model label for API/CLI fallback.")
    backend.add_argument("--fallback-command", metavar="CMD", help="Command shown to workers for API/CLI fallback.")
    backend.add_argument("--runtime-home", metavar="DIR", help="Shared config home. Defaults to ~/.editppt.")
    backend.add_argument("--input-context-policy", metavar="TEXT", help="Policy note for how image inputs must be inspected or passed.")
    backend.set_defaults(func=cmd_backend)

    sample = run_sub.add_parser(
        "sample",
        help="Record the approved sample page.",
        description="Record the main agent's approved sample page and propagate user feedback to remaining pages.",
        formatter_class=HELP_FORMATTER,
    )
    sample.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    sample.add_argument("--page", required=True, metavar="PAGE", help="Approved sample page id or number.")
    sample.add_argument("--feedback", metavar="TEXT", help="User feedback or requirements to propagate to remaining pages.")
    sample.set_defaults(func=cmd_sample)

    prompt_page = run_sub.add_parser(
        "prompt",
        help="Generate a page-worker prompt.",
        description="""Write a self-contained prompt for one page worker.

The agent must use the prompt to spawn a worker, then call `editppt run dispatch`
with the real worker/thread id. Prompt generation and dispatch recording remain
separate because the CLI cannot spawn the worker itself.
""",
        formatter_class=HELP_FORMATTER,
    )
    prompt_page.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    prompt_page.add_argument("--page", required=True, metavar="PAGE", help="Page id such as page_001, or page number such as 1.")
    prompt_page.add_argument("--out", required=True, metavar="FILE", help="Prompt file to write.")
    prompt_page.set_defaults(func=cmd_prompt_page)

    dispatch = run_sub.add_parser(
        "dispatch",
        help="Record page dispatch after spawning a worker.",
        description="Mark a page as dispatched after the parent agent has actually spawned the worker.",
        formatter_class=HELP_FORMATTER,
    )
    dispatch.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    dispatch.add_argument("--page", required=True, metavar="PAGE", help="Page id such as page_001, or page number such as 1.")
    dispatch.add_argument("--agent-id", required=True, metavar="ID", help="Runtime worker/thread id.")
    dispatch.add_argument("--prompt-file", required=True, metavar="FILE", help="Prompt file used to spawn the worker.")
    dispatch.add_argument("--agent-nickname", metavar="NAME", help="Optional human-readable worker label.")
    dispatch.add_argument("--repair-item-id", metavar="ID", help="Repair item id when dispatching a repair worker.")
    dispatch.set_defaults(func=cmd_dispatch)

    record = run_sub.add_parser(
        "record",
        help="Record and verify a page-worker result.",
        description="Validate required page outputs, record hashes, and mark the page recorded.",
        formatter_class=HELP_FORMATTER,
    )
    record.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    record.add_argument("--page", required=True, metavar="PAGE", help="Page id such as page_001, or page number such as 1.")
    record.add_argument("--agent-id", required=True, metavar="ID", help="Runtime worker/thread id that produced the result.")
    record.add_argument("--page-result", default="page_result.json", metavar="FILE", help="Result file relative to the page directory.")
    record.set_defaults(func=cmd_record)

    repair = run_sub.add_parser("repair", help="Queue page repair items.", add_help=False)
    repair.add_argument("repair_args", nargs=argparse.REMAINDER)
    repair.set_defaults(func=cmd_queue_repairs)

    finalize = run_sub.add_parser(
        "finalize",
        help="Build and validate the final deck.",
        description="Assemble recorded pages into final/<origin>_edited.pptx and write validation outputs.",
        formatter_class=HELP_FORMATTER,
    )
    finalize.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    finalize.set_defaults(func=cmd_finalize)

    image = sub.add_parser(
        "image",
        help="Generate/edit images through API fallback and process image assets.",
        description="""Image API fallback and deterministic image-file handling.

Use generate/edit/batch for third-party OpenAI-compatible image APIs. Use import
to record images produced by built-in tools. Use process-sheet and crop for
deterministic asset extraction inside page directories.
""",
        formatter_class=HELP_FORMATTER,
    )
    image_sub = image.add_subparsers(dest="image_command", metavar="image-command", required=True)

    for name, help_text in (
        ("generate", "Create a new image through the configured API fallback."),
        ("edit", "Edit one or more images through the configured API fallback."),
        ("batch", "Generate multiple images from JSONL input."),
    ):
        image_api = image_sub.add_parser(name, help=help_text, add_help=False)
        image_api.add_argument("image_args", nargs=argparse.REMAINDER)
        image_api.set_defaults(func=cmd_image_api)

    image_import = image_sub.add_parser(
        "import",
        help="Copy and record an existing generated image.",
        add_help=False,
    )
    image_import.add_argument("record_image_args", nargs=argparse.REMAINDER)
    image_import.set_defaults(func=cmd_record_image)

    process_sheet = image_sub.add_parser(
        "process-sheet",
        help="Remove chroma key and split a generated asset sheet.",
        add_help=False,
    )
    process_sheet.add_argument("process_args", nargs=argparse.REMAINDER)
    process_sheet.set_defaults(func=cmd_process_asset_sheet)

    crop = image_sub.add_parser(
        "crop",
        help="Crop a source or generated image into a page asset.",
        description="Crop a region, optionally remove border background, and update manifest provenance.",
        formatter_class=HELP_FORMATTER,
    )
    crop.add_argument("page_dir", metavar="PAGE_DIR", help="Page directory that owns the output asset.")
    crop.add_argument("--source", required=True, metavar="FILE", help="Source image path, relative to page dir unless absolute.")
    crop.add_argument("--box", required=True, metavar="L,T,R,B", help="Crop box in source pixels: left,top,right,bottom.")
    crop.add_argument("--out", required=True, metavar="FILE", help="Output asset path, relative to page dir unless absolute.")
    crop.add_argument("--job-id", metavar="ID", help="Optional imagegen job id to mark processed.")
    crop.add_argument("--padding", type=int, default=0, metavar="PX", help="Optional crop padding in pixels.")
    crop.add_argument("--remove-border-bg", action="store_true", help="Remove plain border background from the cropped asset.")
    crop.add_argument("--manifest", default="manifest.json", metavar="FILE", help="Manifest to update with provenance.")
    crop.add_argument(
        "--source-type",
        default="source-derived-rasterization",
        choices=["imagegen", "user-provided", "user-approved-rasterization", "source-derived-rasterization"],
        help="Provenance source type recorded in the manifest.",
    )
    crop.add_argument("--provenance-note", metavar="TEXT", help="Provenance note written to manifest.")
    crop.add_argument("--approval-note", metavar="TEXT", help="Optional approval note written to manifest.")
    crop.set_defaults(func=cmd_crop_image)

    return parser


def main() -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args()
    for attr in ("image_args", "process_args", "record_image_args", "repair_args"):
        if hasattr(args, attr):
            getattr(args, attr).extend(extra)
            extra = []
            break
    if extra:
        parser.error("unrecognized arguments: " + " ".join(extra))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
