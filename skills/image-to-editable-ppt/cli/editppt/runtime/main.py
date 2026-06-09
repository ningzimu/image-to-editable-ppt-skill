#!/usr/bin/env python3
"""Unified CLI for the image-to-editable-ppt skill."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from deck_run_state import (
    dispatch_slots_available,
    dispatchable_pages,
    find_page,
    load_deck,
    load_jobs,
    load_run_state,
    page_dir_for,
    run_dir_from_target,
)
from formula_renderer import (
    FormulaRenderError,
    formula_image_fragment,
    render_latex_asset,
    write_json,
)


RUNTIME_DIR = Path(__file__).resolve().parent
HELP_FORMATTER = argparse.RawDescriptionHelpFormatter


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
            mode="editppt-image-cli",
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
        if len(pages) == 1:
            page = find_page(jobs, dispatchable[0])
            page_id = page.get("page_id")
            page_dir = page_dir_for(run_dir, page)
            payload = {
                "run_dir": str(run_dir),
                "stage": "rebuild_page",
                "page_id": page_id,
                "page_dir": str(page_dir),
                "next_command": f"{cli_prog()} run record {run_dir} --page {page_id} --agent-id main",
                "agent_focus": "Rebuild this single page directly in its page directory, then record the page result.",
            }
            return print_json(payload) if args.json else _print_next_text(payload)

        selected = dispatchable[:slots]
        first_page = find_page(jobs, selected[0])
        prompt_out = page_dir_for(run_dir, first_page) / "worker-prompt.md"
        payload = {
            "run_dir": str(run_dir),
            "stage": "dispatch_pages",
            "dispatch_slots_available": slots,
            "dispatchable_pages": dispatchable,
            "suggested_pages": selected,
            "prompt_file": str(prompt_out),
            "next_command": f"{cli_prog()} run dispatch {run_dir} --page {selected[0]} --agent-id <worker-id> --prompt-file {prompt_out}",
            "agent_focus": "Build the page prompt, spawn the worker, then record dispatch.",
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
            "stage": "wait",
            "active_or_unfinished_pages": unfinished,
            "next_command": f"{cli_prog()} run status {run_dir}",
            "agent_focus": "Wait for dispatched workers, then record completed page results.",
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
    if payload.get("prompt_file"):
        print(f"prompt_file={payload['prompt_file']}")
    if payload.get("page_dir"):
        print(f"page_dir={payload['page_dir']}")
    if payload.get("active_or_unfinished_pages"):
        print(f"active_or_unfinished_pages={', '.join(payload['active_or_unfinished_pages'])}")
    print(f"next_command={payload.get('next_command')}")
    print(f"agent_focus={payload.get('agent_focus')}")
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    argv = [args.run, "--page", args.page, "--agent-id", args.agent_id, "--prompt-file", args.prompt_file]
    if args.agent_nickname:
        argv.extend(["--agent-nickname", args.agent_nickname])
    return run_script("record_page_dispatch.py", argv)


def cmd_record(args: argparse.Namespace) -> int:
    return run_script(
        "record_page_result.py",
        [args.run, "--page", args.page, "--agent-id", args.agent_id, "--page-result", args.page_result],
    )


def cmd_finalize(args: argparse.Namespace) -> int:
    return run_script("finalize_deck_run.py", [args.run])


def cmd_formula_render_latex(args: argparse.Namespace) -> int:
    if args.tex_file:
        tex = Path(args.tex_file).read_text(encoding="utf-8")
    elif args.tex:
        tex = args.tex
    else:
        raise SystemExit("formula render-latex requires --tex or --tex-file")
    preamble = ""
    if args.preamble_file:
        preamble = Path(args.preamble_file).read_text(encoding="utf-8")
    if args.preamble:
        preamble = (preamble + "\n" + args.preamble).strip()
    try:
        rendered = render_latex_asset(
            tex=tex,
            out=args.out,
            page_dir=args.page_dir,
            output_format=args.format,
            engine=args.engine,
            preamble=preamble,
            full_document=args.full_document,
            display=not args.inline,
            dpi=args.dpi,
            timeout=args.timeout,
            shell_escape=args.shell_escape,
            keep_workdir=args.keep_workdir,
        )
        payload = dict(rendered)
        if args.fragment:
            if not args.box:
                raise FormulaRenderError("--fragment requires --box X,Y,W,H")
            fragment = formula_image_fragment(
                formula_id=args.id,
                image_path=rendered["out"],
                tex_source=rendered["tex_source"],
                box_px=args.box,
                page_dir=args.page_dir,
                z_index=args.z_index,
                alt=args.alt,
            )
            write_json(fragment, args.fragment)
            payload["fragment"] = str(Path(args.fragment))
        return print_json(payload)
    except FormulaRenderError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("IMAGE_TO_EDITABLE_PPT_CLI_PROG", "editppt"),
        description="CLI for preparing, rebuilding, validating, and finalizing editable PPTX runs.",
        formatter_class=HELP_FORMATTER,
        epilog="""Command groups:
  - setup/doctor/config manage the local editppt environment and API fallback config.
  - prepare creates a run directory and writes the unified editppt image backend.
  - run manages deterministic workflow state, dispatch records, result records, and finalization.
  - image generates/edits through Codex OAuth first, then API fallback, and processes image files.
  - formula renders LaTeX formulas into PPT image assets and manifest fragments.

Examples:
  editppt setup
  editppt prepare deck.pdf
  editppt run next <run> --json
  editppt run finalize <run>
  editppt formula render-latex pages/page_001 --tex "\\frac{a}{b}" --out assets/formula.svg --box 100,100,300,80 --fragment formula-fragment.json

Use '<command> --help' for exact arguments:
  editppt prepare --help
  editppt run --help
  editppt image --help
  editppt formula render-latex --help
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

    doctor = sub.add_parser(
        "doctor",
        help="Check CLI dependencies and config status.",
        description="""Check the local editppt environment.

Doctor reports the CLI Python path, importable dependencies, config home/file,
and API fallback readiness when --check-api is passed. It does not
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
extracts note metadata when applicable, and records the default editppt image
CLI backend. The normal path does not require a separate backend command.
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
    prepare.add_argument("--max-concurrent-pages", type=int, metavar="N", help="Maximum concurrent page dispatch slots. Default: 6.")
    prepare.set_defaults(func=cmd_prepare)

    run = sub.add_parser(
        "run",
        help="Manage run state, dispatch records, result records, and finalization.",
        description="""Deterministic state commands for a prepared run.

Use these commands after editppt prepare. They inspect and update run/page state,
record dispatch/result events, and assemble the final deck.
""",
        formatter_class=HELP_FORMATTER,
    )
    run_sub = run.add_subparsers(dest="run_command", metavar="run-command", required=True)

    run_next = run_sub.add_parser(
        "next",
        help="Print the next workflow action.",
        description="Inspect run state and print the next suggested action.",
        formatter_class=HELP_FORMATTER,
    )
    run_next.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    run_next.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    run_next.set_defaults(func=cmd_next)

    status = run_sub.add_parser(
        "status",
        help="Show page dispatch status.",
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

Normally editppt prepare records the unified editppt image CLI backend automatically.
Use this only when forcing OpenAI-compatible API metadata or a custom image backend.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt run backend <run>
  editppt run backend <run> --mode openai-compatible-api --model openai/gpt-image-2
""",
    )
    backend.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    backend.add_argument("--mode", choices=["editppt-image-cli", "openai-compatible-api"], default="editppt-image-cli", help="Image backend mode. Defaults to the unified editppt image CLI contract.")
    backend.add_argument("--tool-name", metavar="NAME", help="Override backend tool name recorded in the contract.")
    backend.add_argument("--tool-call", metavar="CALL", help="Override backend tool call recorded in the contract.")
    backend.add_argument("--model", metavar="MODEL", help="Image model label for API/CLI fallback.")
    backend.add_argument("--fallback-command", metavar="CMD", help="Command shown to workers for API/CLI fallback.")
    backend.add_argument("--runtime-home", metavar="DIR", help="Shared config home. Defaults to ~/.editppt.")
    backend.add_argument("--input-context-policy", metavar="TEXT", help="Policy note for how image inputs must be inspected or passed.")
    backend.set_defaults(func=cmd_backend)

    dispatch = run_sub.add_parser(
        "dispatch",
        help="Record page dispatch.",
        description="Mark a page as dispatched after a worker/thread has been created.",
        formatter_class=HELP_FORMATTER,
    )
    dispatch.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    dispatch.add_argument("--page", required=True, metavar="PAGE", help="Page id such as page_001, or page number such as 1.")
    dispatch.add_argument("--agent-id", required=True, metavar="ID", help="Runtime worker/thread id.")
    dispatch.add_argument("--prompt-file", required=True, metavar="FILE", help="Prompt file used to spawn the worker. It must resolve inside the page directory.")
    dispatch.add_argument("--agent-nickname", metavar="NAME", help="Optional human-readable worker label.")
    dispatch.set_defaults(func=cmd_dispatch)

    record = run_sub.add_parser(
        "record",
        help="Record and verify a page result.",
        description="Validate required page outputs, record hashes, and mark the page recorded. Single-page direct rebuilds can be recorded from pending status with --agent-id main.",
        formatter_class=HELP_FORMATTER,
    )
    record.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    record.add_argument("--page", required=True, metavar="PAGE", help="Page id such as page_001, or page number such as 1.")
    record.add_argument("--agent-id", required=True, metavar="ID", help="Runtime worker/thread id that produced the result.")
    record.add_argument("--page-result", default="page_result.json", metavar="FILE", help="Result file relative to the page directory.")
    record.set_defaults(func=cmd_record)

    finalize = run_sub.add_parser(
        "finalize",
        help="Build and validate the final deck.",
        description="Build final/<origin>_edited.pptx from recorded page manifests and write validation outputs.",
        formatter_class=HELP_FORMATTER,
    )
    finalize.add_argument("run", metavar="RUN", help="Run directory or deck_manifest.json path.")
    finalize.set_defaults(func=cmd_finalize)

    formula = sub.add_parser(
        "formula",
        help="Render LaTeX formulas into PPT image assets.",
        description="""Render LaTeX formulas into image assets for page manifests.

Use this when formula fidelity matters more than formula editability. Provide
the source formula as LaTeX; this command renders it to SVG, PNG, or PDF and
can write a manifest image fragment.
""",
        formatter_class=HELP_FORMATTER,
    )
    formula_sub = formula.add_subparsers(dest="formula_command", metavar="formula-command", required=True)

    formula_render = formula_sub.add_parser(
        "render-latex",
        help="Render one LaTeX formula to SVG, PNG, or PDF.",
        description="""Render one LaTeX formula into an image asset.

This is the high-fidelity formula path. It relies on a local TeX engine
(xelatex, lualatex, or pdflatex). SVG output additionally requires dvisvgm or
pdf2svg; PNG output requires ImageMagick. The rendered formula is an image in
PowerPoint, not an editable equation object.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Examples:
  editppt formula render-latex pages/page_001 --tex "\\frac{a}{b}" --out assets/f1.svg --box 100,100,300,80 --fragment formula-fragment.json
  editppt formula render-latex pages/page_001 --tex-file formula.tex --out assets/f1.png --format png --dpi 300 --box 100,100,300,80 --fragment formula-fragment.json
  editppt formula render-latex --tex "\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}" --out /tmp/matrix.svg
""",
    )
    formula_render.add_argument("page_dir", nargs="?", metavar="PAGE_DIR", help="Optional page directory. Relative --out paths are resolved under it.")
    formula_render.add_argument("--tex", metavar="TEXT", help="LaTeX formula body. Wrapped in display math unless --inline or --full-document is used.")
    formula_render.add_argument("--tex-file", metavar="FILE", help="Read LaTeX formula body or full document from a file.")
    formula_render.add_argument("--out", required=True, metavar="FILE", help="Rendered output path. Relative paths use PAGE_DIR when provided.")
    formula_render.add_argument("--format", choices=["svg", "png", "pdf"], metavar="FMT", help="Output format. Defaults to --out suffix or svg.")
    formula_render.add_argument("--engine", default="auto", metavar="ENGINE", help="LaTeX engine: auto, xelatex, lualatex, pdflatex, or an executable path.")
    formula_render.add_argument("--inline", action="store_true", help="Wrap --tex in inline math instead of display math.")
    formula_render.add_argument("--full-document", action="store_true", help="Treat --tex/--tex-file as a complete LaTeX document.")
    formula_render.add_argument("--preamble", metavar="TEXT", help="Extra LaTeX preamble inserted into the default wrapper.")
    formula_render.add_argument("--preamble-file", metavar="FILE", help="Read extra LaTeX preamble from a file.")
    formula_render.add_argument("--dpi", type=int, default=300, metavar="N", help="PNG rasterization DPI.")
    formula_render.add_argument("--timeout", type=int, default=120, metavar="SEC", help="Render/conversion timeout in seconds.")
    formula_render.add_argument("--shell-escape", action="store_true", help="Allow LaTeX shell escape. Keep off unless the formula package requires it.")
    formula_render.add_argument("--keep-workdir", metavar="DIR", help="Copy the temporary TeX workdir here for debugging.")
    formula_render.add_argument("--fragment", metavar="FILE", help="Write a manifest image fragment for this formula.")
    formula_render.add_argument("--box", metavar="X,Y,W,H", help="Source-pixel placement box for --fragment.")
    formula_render.add_argument("--id", default="formula", metavar="ID", help="Formula/image id used in the manifest fragment.")
    formula_render.add_argument("--alt", metavar="TEXT", help="Alt text for the formula image in the manifest fragment.")
    formula_render.add_argument("--z-index", type=int, default=220, metavar="N", help="Image z_index in the manifest fragment.")
    formula_render.set_defaults(func=cmd_formula_render_latex)

    image = sub.add_parser(
        "image",
        help="Generate/edit images and process image assets.",
        description="""Unified image generation/editing and deterministic image-file handling.

Use generate/edit/batch for Codex OAuth first, with OpenAI-compatible API fallback
when local Codex auth is unavailable. Use process-sheet for deterministic
asset-sheet splitting inside page directories.
""",
        formatter_class=HELP_FORMATTER,
        epilog="""Backend selection:
  Codex OAuth uses ~/.codex/auth.json or CODEX_AUTH_FILE.
  API fallback uses ~/.editppt/config.yaml or OPENAI_API_KEY, OPENAI_BASE_URL,
  and IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL.

Setup:
  codex login
  editppt config --api-key "your-api-key" --model gpt-image-2
  editppt config --api-key "your-api-key" --base-url https://example.test/v1 --model openai/gpt-image-2

Patterns:
  editppt image edit --image pages/page_001/source.png --prompt-file clean-base.prompt.txt --out pages/page_001/assets/clean-base.png
  editppt image edit --image pages/page_001/source.png --prompt-file asset-sheet.prompt.txt --out pages/page_001/assets/asset-sheet.png
  editppt image batch --input jobs.jsonl --out-dir pages/page_001/assets --concurrency 6
""",
    )
    image_sub = image.add_subparsers(dest="image_command", metavar="image-command", required=True)

    for name, help_text in (
        ("generate", "Create a new image through the unified image backend."),
        ("edit", "Edit one or more images through the unified image backend."),
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

    return parser


def main() -> int:
    raw_argv = sys.argv[1:]
    if len(raw_argv) >= 2 and raw_argv[0] == "image" and raw_argv[1] in {"generate", "edit", "batch"}:
        return run_script("image_gen.py", [raw_argv[1], *raw_argv[2:]])

    parser = build_parser()
    args, extra = parser.parse_known_args()
    for attr in ("image_args", "process_args", "record_image_args"):
        if hasattr(args, attr):
            getattr(args, attr).extend(extra)
            extra = []
            break
    if extra:
        parser.error("unrecognized arguments: " + " ".join(extra))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
