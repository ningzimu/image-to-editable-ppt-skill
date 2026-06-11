#!/usr/bin/env python3
"""Build a page-worker prompt from skill-local prompt templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


def read_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_dir_from_target(target: str) -> Path:
    path = Path(target).expanduser().resolve()
    if path.is_dir():
        return path
    if path.name == "deck_manifest.json":
        return path.parent
    raise SystemExit(f"Expected run directory or deck_manifest.json: {target}")


def load_jobs(run_dir: Path) -> dict:
    return read_json(run_dir / "page_jobs.json")


def find_page(jobs: dict, page_ref: str) -> dict:
    ref = str(page_ref).strip()
    candidates = [ref]
    if ref.isdigit():
        candidates.append(f"page_{int(ref):03d}")
    for page in jobs.get("pages", []):
        if page.get("page_id") in candidates:
            return page
    raise SystemExit(f"Page not found in page_jobs.json: {page_ref}")


def page_dir_for(run_dir: Path, page: dict) -> Path:
    page_dir = Path(str(page.get("page_dir") or ""))
    return page_dir if page_dir.is_absolute() else (run_dir / page_dir).resolve()


def resolve_prompt_out(run_dir: Path, page_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        out = path.resolve()
    elif path.parts[:1] == ("pages",):
        out = (run_dir / path).resolve()
    else:
        out = (page_dir / path).resolve()
    try:
        out.relative_to(page_dir)
    except ValueError as exc:
        raise SystemExit(f"Prompt file must live inside page dir: {out}") from exc
    return out


def page_worker_template() -> str:
    text = (SKILL_ROOT / "prompts" / "page-worker.md").read_text(encoding="utf-8")
    marker = "```text"
    start = text.find(marker)
    if start == -1:
        return text.strip()
    start += len(marker)
    # Use rfind so nested code fences inside the template cannot truncate it.
    end = text.rfind("```")
    if end <= start:
        return text[start:].strip()
    return text[start:end].strip()


def build_prompt(run_dir: Path, page: dict, page_dir: Path) -> str:
    request = read_json(page_dir / "page_request.json")
    page_id = page.get("page_id")
    source_image = request.get("source_image") or str(page_dir / "source.png")
    replacements = {
        "{{RUN_DIR}}": str(run_dir),
        "{{PAGE_ID}}": str(page_id),
        "{{PAGE_DIR}}": str(page_dir),
        "{{SOURCE_IMAGE}}": str(source_image),
        "{{SKILL_ROOT}}": str(SKILL_ROOT),
    }
    prompt = page_worker_template()
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    missing = [p for p in replacements if p in prompt]
    if missing:
        raise SystemExit(f"Unfilled placeholders in worker prompt: {missing}")
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a page-worker prompt from the skill-local page-worker template.",
    )
    parser.add_argument("run", help="Run directory or deck_manifest.json path.")
    parser.add_argument("--page", required=True, help="Page id such as page_001, or page number such as 1.")
    parser.add_argument(
        "--out",
        required=True,
        help="Prompt file to write inside the page directory. Relative names are resolved under the page dir; pages/page_NNN/... is resolved under the run dir.",
    )
    parser.add_argument("--cli", default="editppt", help="CLI command name used in the returned dispatch command template.")
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    jobs = load_jobs(run_dir)
    page = find_page(jobs, args.page)
    page_id = page.get("page_id")
    page_dir = page_dir_for(run_dir, page)
    out = resolve_prompt_out(run_dir, page_dir, args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_prompt(run_dir, page, page_dir).strip() + "\n", encoding="utf-8")

    payload = {
        "prompt_file": str(out),
        "page_id": page_id,
        "page_dir": str(page_dir),
        "run_dir": str(run_dir),
        "dispatch_command_template": f"{args.cli} run dispatch {run_dir} --page {page_id} --agent-id <worker-id> --prompt-file {out}",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
