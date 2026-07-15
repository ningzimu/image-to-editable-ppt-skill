#!/usr/bin/env python3
import argparse
import json
import os
import importlib.util
import sys
import stat
from pathlib import Path


DEFAULT_CONFIG_HOME = "~/.editppt"
DEFAULT_CODEX_AUTH_FILE = "~/.codex/auth.json"
CODEX_PPT_RUNTIME_HOME = "~/.codex-ppt-skill"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
ENV_FIELDS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL", "PADDLE_OCR_TOKEN")
PADDLE_TOKEN_APPLY_URL = "https://aistudio.baidu.com/account/accessToken"
CODEX_PPT_ENV_MAP = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "OPENAI_BASE_URL": "OPENAI_BASE_URL",
    "CODEX_PPT_IMAGE_MODEL": "IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL",
}


def cli_reinstall_hint():
    return "`pipx install --force --editable <path-to-image-to-editable-ppt>/cli`"


def runtime_home():
    return Path(os.getenv("EDITPPT_CONFIG_HOME", DEFAULT_CONFIG_HOME)).expanduser()


def config_path(home=None):
    return (home or runtime_home()) / "config.yaml"


def parse_env_file(path):
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_config_file(path):
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            f"PyYAML is required to read editppt config. Reinstall with {cli_reinstall_hint()}."
        ) from exc
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid config file: {path}")
    return data


def write_config_file(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            f"PyYAML is required to write editppt config. Reinstall with {cli_reinstall_hint()}."
        ) from exc
    data = {key: values[key] for key in ENV_FIELDS if values.get(key)}
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=True)
    except OSError:
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=True)
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def mask_secret(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def codex_auth_file():
    return Path(os.getenv("CODEX_AUTH_FILE", DEFAULT_CODEX_AUTH_FILE)).expanduser()


def codex_oauth_ready():
    path = codex_auth_file()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    tokens = data.get("tokens")
    return isinstance(tokens, dict) and bool(str(tokens.get("access_token") or "").strip())


def import_codex_ppt_values(values):
    codex_ppt_env = Path(os.getenv("CODEX_PPT_HOME", CODEX_PPT_RUNTIME_HOME)).expanduser() / ".env"
    source = parse_env_file(codex_ppt_env)
    changed = False
    for source_key, target_key in CODEX_PPT_ENV_MAP.items():
        if not values.get(target_key) and source.get(source_key):
            values[target_key] = source[source_key]
            changed = True
    return changed, codex_ppt_env


def config(args):
    home = runtime_home()
    values = read_config_file(config_path(home))
    before = dict(values)
    imported = False
    import_path = None
    if args.import_codex_ppt:
        imported, import_path = import_codex_ppt_values(values)
    if args.api_key:
        values["OPENAI_API_KEY"] = args.api_key
    if args.base_url is not None:
        values["OPENAI_BASE_URL"] = args.base_url.strip()
    if args.clear_base_url:
        values.pop("OPENAI_BASE_URL", None)
    if args.model is not None:
        values["IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL"] = args.model.strip()
    if getattr(args, "paddle_ocr_token", None):
        values["PADDLE_OCR_TOKEN"] = args.paddle_ocr_token.strip()
    changed = sorted(key for key in ENV_FIELDS if before.get(key) != values.get(key))
    if changed or not config_path(home).exists():
        write_config_file(config_path(home), values)
        state = "updated" if before else "created"
    else:
        state = "unchanged"
    print(f"config={state} path={config_path(home)}")
    if import_path:
        print(f"import_codex_ppt={'yes' if imported else 'no'} source={import_path}")
    if changed:
        print(f"changed={', '.join(changed)}")
    else:
        print("changed=<none>")
    for key in ENV_FIELDS:
        value = values.get(key, "")
        if key in ("OPENAI_API_KEY", "PADDLE_OCR_TOKEN"):
            value = mask_secret(value)
        print(f"{key}={value or '<unset>'}")
    return 0


def current_python_has_module(module):
    return importlib.util.find_spec(module) is not None


def collect_status(check_api=False):
    home = runtime_home()
    values = read_config_file(config_path(home))
    config_values = dict(values)
    for key in ENV_FIELDS:
        if os.getenv(key):
            values[key] = os.environ[key]
    imported_codex_ppt = False
    if not values.get("OPENAI_API_KEY"):
        imported_codex_ppt, _ = import_codex_ppt_values(values)

    dependencies = {
        module: current_python_has_module(module)
        for module in ("fitz", "PIL", "openai", "yaml", "numpy", "requests")
    }
    api_key = values.get("OPENAI_API_KEY", "")
    api_ready = bool(api_key)
    codex_ready = codex_oauth_ready()
    cli_fallback_ready = codex_ready or api_ready
    ok = all(dependencies.values()) and (cli_fallback_ready if check_api else True)
    return {
        "ok": ok,
        "config_home": str(home),
        "config_file": str(config_path(home)),
        "config_exists": config_path(home).exists(),
        "cli_python": sys.executable,
        "dependencies": dependencies,
        "config_keys": sorted(key for key in ENV_FIELDS if config_values.get(key)),
        "api_fallback": {
            "ready": api_ready,
            "OPENAI_API_KEY": "set" if api_key else "unset",
            "OPENAI_BASE_URL": values.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL": values.get(
                "IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL",
                DEFAULT_IMAGE_MODEL,
            ),
            "imported_codex_ppt": imported_codex_ppt,
        },
        "codex_oauth": {
            "ready": codex_ready,
            "auth_file": str(codex_auth_file()),
        },
        "agent_builtin_imagegen": {
            "checked": False,
            "ready": None,
            "tool_name": "image_gen.imagegen",
            "reason": "CLI doctor cannot detect Agent tool availability",
        },
        "image_backend": {
            "scope": "cli-fallback-only",
            "ready": cli_fallback_ready,
            "selection": "codex-oauth" if codex_ready else ("openai-compatible-api" if api_ready else "missing"),
        },
        "text_hints": {
            "selection": "paddleocr-vl" if values.get("PADDLE_OCR_TOKEN") else "builtin-ink",
            "paddle_token": "set" if values.get("PADDLE_OCR_TOKEN") else "unset",
            "apply_url": PADDLE_TOKEN_APPLY_URL,
            "configure_command": "editppt config --paddle-ocr-token <token>",
        },
        "network_approval": {
            "commands": [
                "editppt prepare / editppt run hints when PADDLE_OCR_TOKEN is set",
                "editppt image generate/edit",
            ],
            "justification": (
                "User-requested image-to-editable-ppt conversion; uploads are limited to "
                "task-local page images, prompts, masks, and references required by OCR/image backends."
            ),
            "paddle_rejection_guidance": (
                "If PaddleOCR approval is rejected, ask the user to authorize OCR explicitly; "
                "explain that OCR corrects text boxes, font sizes, and size groups so reconstructed "
                "PPT text sizing stays stable."
            ),
        },
        "next": "no action needed" if ok else (
            "configure CLI fallback with `codex login` or `editppt config --api-key <key>`"
            if check_api and not cli_fallback_ready
            else cli_reinstall_hint().strip("`")
        ),
    }


def doctor(args):
    status = collect_status(check_api=args.check_api)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["ok"] else 1

    api = status["api_fallback"]
    codex = status["codex_oauth"]
    builtin = status["agent_builtin_imagegen"]
    image_backend = status["image_backend"]
    print(f"config home: {status['config_home']}")
    print(f"cli python: {status['cli_python']}")
    print(f"config file: {status['config_file']} ({'exists' if status['config_exists'] else 'missing'})")
    print(f"OPENAI_API_KEY={'set (' + mask_secret(os.getenv('OPENAI_API_KEY', '')) + ')' if os.getenv('OPENAI_API_KEY') else api['OPENAI_API_KEY']}")
    print(f"OPENAI_BASE_URL={api['OPENAI_BASE_URL']}")
    print(f"IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL={api['IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL']}")
    print(f"Codex OAuth={'ready' if codex['ready'] else 'missing'} ({codex['auth_file']})")
    print(f"built-in image backend=not checked ({builtin['tool_name']} is an Agent tool unavailable to CLI doctor)")
    print(f"CLI fallback image backend={image_backend['selection']}")
    hints = status["text_hints"]
    print(f"text hints={hints['selection']} (PADDLE_OCR_TOKEN {hints['paddle_token']})")
    print(
        "network approval: in restricted agents, request approval up front for OCR/image backend "
        "commands; conversion uploads are limited to task-local page images, prompts, masks, "
        "and references."
    )
    print(
        "paddle approval rejection: ask the user to authorize OCR and explain that it corrects "
        "text boxes, font sizes, and size groups so reconstructed PPT text sizing stays stable."
    )
    if hints["paddle_token"] == "unset":
        print(
            "text hints: ASK THE USER once — a free PaddleOCR token makes text hints content-aware "
            "(recognized text + cleaner blocks, noticeably better text fidelity). The free personal "
            "quota is currently more than enough for this skill, so applying is risk-free with no "
            "extra cost. They can apply at "
            "{url} and you run `{cmd}`; or they can choose to continue with the offline detector. "
            "Wait for their choice before reconstructing pages, then do not ask again.".format(
                url=hints["apply_url"], cmd=hints["configure_command"]
            )
        )
    for module, module_ok in status["dependencies"].items():
        print(f"python import {module}: {'ok' if module_ok else 'missing'}")
    if not all(status["dependencies"].values()):
        print(f"dependency install hint: run {cli_reinstall_hint()}.")
    if args.check_api:
        if image_backend["ready"]:
            print("CLI fallback image backend check: configured (network probe not performed by doctor)")
        else:
            print("CLI fallback image backend check: Codex OAuth and OPENAI_API_KEY are both missing")
    print(f"next: {status['next']}")
    return 0 if status["ok"] else 1


def main():
    parser = argparse.ArgumentParser(
        prog="editppt",
        description="Manage editppt API fallback configuration",
    )
    sub = parser.add_subparsers(required=True)
    doc = sub.add_parser("doctor", help="Check Python dependencies and fallback config")
    doc.add_argument(
        "--check-api",
        action="store_true",
        help="Require Codex OAuth or OpenAI-compatible API credentials for the CLI fallback.",
    )
    doc.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    doc.add_argument("--timeout", type=int, default=30, help="Reserved timeout value for future network probes.")
    doc.set_defaults(func=doctor)
    cfg = sub.add_parser("config", help="Write or update ~/.editppt/config.yaml")
    cfg.add_argument("--api-key", help="OpenAI or OpenAI-compatible API key to store.")
    cfg.add_argument("--base-url", help="OpenAI-compatible base URL, for example https://api.openai.com/v1.")
    cfg.add_argument("--clear-base-url", action="store_true", help="Remove OPENAI_BASE_URL from the config file.")
    cfg.add_argument("--model", help="Default image model for API fallback.")
    cfg.add_argument("--paddle-ocr-token", help=f"PaddleOCR-VL token for content-aware text hints. Apply at {PADDLE_TOKEN_APPLY_URL}.")
    cfg.add_argument("--import-codex-ppt", action="store_true", help="Import compatible values from ~/.codex-ppt-skill/.env when present.")
    cfg.set_defaults(func=config)
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
