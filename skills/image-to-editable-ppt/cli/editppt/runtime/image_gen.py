#!/usr/bin/env python3
"""Unified CLI for image-to-editable-ppt image generation or editing.

The CLI prefers local Codex OAuth auth when ~/.codex/auth.json is available.
If Codex auth is missing, it falls back to OpenAI-compatible API credentials
from the environment or ~/.editppt/config.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import concurrent.futures
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import error, request

from io import BytesIO

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "2560x1440"
DEFAULT_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_CONCURRENCY = 5
DEFAULT_DOWNSCALE_SUFFIX = "-web"
DEFAULT_OUTPUT_PATH = "output/imagegen/output.png"
GPT_IMAGE_MODEL_PREFIX = "gpt-image-"

ALLOWED_LEGACY_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
ALLOWED_QUALITIES = {"low", "medium", "high", "auto"}
ALLOWED_BACKGROUNDS = {"transparent", "opaque", "auto", None}

GPT_IMAGE_2_MODEL = "gpt-image-2"
GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_RATIO = 3.0

MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_BATCH_JOBS = 500
DEFAULT_CONFIG_HOME = "~/.editppt"
DEFAULT_CODEX_AUTH_FILE = "~/.codex/auth.json"
DEFAULT_CODEX_RESPONSES_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_CODEX_RESPONSES_MODEL = "gpt-5.5"
ENV_FIELDS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL")
MAX_CODEX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_CODEX_BASE64_CHARS = 64 * 1024 * 1024

BATCH_HELP_EPILOG = """\
Backend:
  editppt image chooses Codex OAuth first when ~/.codex/auth.json or
  CODEX_AUTH_FILE is available. Otherwise it uses OPENAI_API_KEY,
  OPENAI_BASE_URL, and IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL from the environment
  or ~/.editppt/config.yaml.

JSONL input:
  Each non-empty line is one job. Comment lines starting with # are ignored.
  A plain text line is treated as {"prompt": "<line>"}.
  A JSON object must include "prompt".

Job routing:
  No image/images field -> generate job (/v1/images/generations).
  image: "source.png" -> edit job with one input image (/v1/images/edits).
  images: ["source.png", "style.png"] -> edit job with multiple input images.
  mask: "mask.png" is supported for API edit jobs only.

Per-job fields:
  prompt, image, images, mask, out, n, size, quality, background,
  output_format, output_compression, moderation, fields.

Prompt fields:
  Use either a nested fields object or flat keys:
  use_case, scene, subject, style, composition, lighting, palette,
  materials, text, constraints, negative.

Output:
  --out-dir is required. If a job has "out", that filename is written under
  --out-dir. Otherwise the CLI creates a stable numbered slug from the prompt.
  Duplicate output paths fail before requests are sent.

Examples:
  {"prompt":"Create a clean blue cloud icon","out":"cloud.png","text":"no text"}
  {"prompt":"Extract the foreground icon exactly; do not redraw","image":"slide.png","out":"icon.png","constraints":"preserve source shape, color, stroke geometry"}
  {"prompt":"Use source as target and style as reference","images":["source.png","style.png"],"out":"asset.png"}
"""

IMAGE_HELP_EPILOG = """\
Backend selection:
  Codex OAuth: uses ~/.codex/auth.json or CODEX_AUTH_FILE.
  API fallback: uses OPENAI_API_KEY, OPENAI_BASE_URL, and
  IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL from the environment or ~/.editppt/config.yaml.

Setup:
  codex login
  editppt config --api-key "your-api-key" --model gpt-image-2
  editppt config --api-key "your-api-key" --base-url https://example.test/v1 --model openai/gpt-image-2

Input image rules:
  generate creates a new image from prompt only.
  edit passes each --image as an edit target, visual reference, or supporting input.
  batch reads JSONL; jobs with image/images are edit jobs, jobs without them are generate jobs.

Slide reconstruction patterns:
  Clean base: use edit --image <source.png>; preserve source composition,
  perspective, object positions, colors, lighting, material, and background identity.
  Asset sheet: use edit --image <source.png>; separate exact existing foreground
  bitmap objects on a flat chroma-key background with generous spacing. Choose
  a key color absent from the assets and far from their main fills, strokes,
  highlights, and shadows; cyan, green, magenta, red, or orange are examples,
  not fixed defaults.
  Formula assets: use editppt formula render-latex, not editppt image.

Output:
  Write outputs under the page directory when used in a deck run. Record selected
  images with editppt image import, then use process-sheet when asset-sheet splitting is needed.
"""

GENERATE_HELP_EPILOG = """\
Backend:
  Uses Codex OAuth when available, otherwise API fallback from ~/.editppt/config.yaml
  or environment variables.

Use for:
  New supporting images that do not need to preserve an existing slide object.

Prompt fields:
  --use-case, --scene, --subject, --style, --composition, --lighting, --palette,
  --materials, --text, --constraints, and --negative are appended when
  --augment is enabled.

Examples:
  editppt image generate --prompt "flat blue cloud icon" --text "no text" --out pages/page_001/assets/cloud.png
  editppt image generate --prompt-file prompt.txt --size 1536x1024 --quality high --out output.png
"""

EDIT_HELP_EPILOG = """\
Backend:
  Uses Codex OAuth when available, otherwise API fallback from ~/.editppt/config.yaml
  or environment variables.

Use for:
  Background cleanup, clean base creation, foreground icon extraction, and
  source-faithful asset sheets. Pass the original slide through --image so the
  model receives it as the edit target and strict visual reference.

Prompt patterns:
  Clean base: preserve source canvas ratio, composition, perspective, object
  positions, colors, lighting, texture, and background identity; remove the
  foreground text/objects that will be rebuilt.
  Asset sheet: extract exact existing non-text foreground objects from the
  source into a sparse chroma-key sheet; preserve shape, stroke geometry, color,
  proportions, internal cutouts, and visual identity. Choose a key color absent
  from the target objects and far from their main fills, strokes, highlights,
  and shadows; cyan, green, magenta, red, or orange are examples, not fixed
  defaults.

Examples:
  editppt image edit --image pages/page_001/source.png --prompt-file clean-base.prompt.txt --out pages/page_001/assets/clean-base.png
  editppt image edit --image pages/page_001/source.png --prompt-file asset-sheet.prompt.txt --out pages/page_001/assets/asset-sheet.png
  editppt image edit --image source.png --image style.png --prompt "Use source as target and style as supporting reference" --out out.png
"""


def _die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def _runtime_home() -> Path:
    return Path(os.getenv("EDITPPT_CONFIG_HOME", DEFAULT_CONFIG_HOME)).expanduser()


def _runtime_env_path() -> Path:
    return _runtime_home() / "config.yaml"


def _load_runtime_env() -> None:
    path = _runtime_env_path()
    if not path.exists():
        return
    try:
        import yaml
    except ImportError as exc:
        _die(
            "PyYAML is required to read ~/.editppt/config.yaml. "
            "Reinstall editppt with pipx so package dependencies are installed."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        _die(f"Invalid config file: {path}")
    for key, value in data.items():
        if key not in ENV_FIELDS or os.getenv(key):
            continue
        os.environ[key] = str(value)


def _default_model() -> str:
    return os.getenv("IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL", DEFAULT_MODEL)


def _api_base_url() -> Optional[str]:
    return os.getenv("OPENAI_BASE_URL") or None


def _api_target_label() -> str:
    base_url = _api_base_url()
    if base_url:
        return f"OpenAI-compatible proxy (OPENAI_BASE_URL={base_url})"
    return "official OpenAI API (OPENAI_BASE_URL unset)"


def _codex_auth_file() -> Path:
    return Path(os.getenv("CODEX_AUTH_FILE", DEFAULT_CODEX_AUTH_FILE)).expanduser()


def _load_codex_access_token() -> Optional[str]:
    path = _codex_auth_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        return None
    token = tokens.get("access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _codex_available() -> bool:
    return _load_codex_access_token() is not None


def _codex_base_url() -> str:
    raw = os.getenv("CODEX_RESPONSES_BASE_URL", DEFAULT_CODEX_RESPONSES_BASE_URL).strip()
    if not raw:
        return DEFAULT_CODEX_RESPONSES_BASE_URL
    if re.fullmatch(r"https?://chatgpt\.com/backend-api(?:/codex)?(?:/v1)?/?", raw, re.I):
        return DEFAULT_CODEX_RESPONSES_BASE_URL
    return raw.rstrip("/")


def _codex_responses_url() -> str:
    return f"{_codex_base_url()}/responses"


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("image/"):
        return mime
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _image_to_data_url(path: Path) -> str:
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{_guess_mime(path)};base64,{encoded}"


def _codex_content(prompt: str, image_paths: List[Path]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for path in image_paths:
        content.append(
            {
                "type": "input_image",
                "image_url": _image_to_data_url(path),
                "detail": "auto",
            }
        )
    return content


def _codex_body(
    *,
    prompt: str,
    image_paths: List[Path],
    model: str,
    responses_model: str,
    size: str,
    quality: str,
    output_format: str,
    background: Optional[str],
) -> Dict[str, Any]:
    tool: Dict[str, Any] = {
        "type": "image_generation",
        "model": model,
        "size": size,
        "quality": quality,
    }
    if output_format:
        tool["output_format"] = output_format
    if background:
        tool["background"] = background
    return {
        "model": responses_model,
        "input": [{"role": "user", "content": _codex_content(prompt, image_paths)}],
        "instructions": "You are an image generation assistant.",
        "tools": [tool],
        "tool_choice": {"type": "image_generation"},
        "stream": True,
        "store": False,
    }


def _post_codex_sse(body: Dict[str, Any], timeout: int) -> str:
    token = _load_codex_access_token()
    if not token:
        _die(f"Codex OAuth auth is missing. Expected {_codex_auth_file()}.")
    req = request.Request(
        _codex_responses_url(),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "editppt-image-cli/0.1.0",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            chunks: List[bytes] = []
            total = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_CODEX_RESPONSE_BYTES:
                    _die("Codex image response exceeded size limit.")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"Codex Responses request failed (HTTP {exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Codex Responses request failed: {exc.reason}") from exc


def _parse_codex_sse_events(body: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _extract_codex_image_payloads(body: str) -> List[str]:
    events = _parse_codex_sse_events(body)
    for event in events:
        if event.get("type") in {"response.failed", "error"}:
            error_obj = event.get("error")
            if isinstance(error_obj, dict):
                message = error_obj.get("message") or error_obj.get("code")
            else:
                message = event.get("message")
            raise RuntimeError(str(message or "Codex image generation failed."))

    payloads: List[str] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "response.output_item.done"
            and isinstance(item, dict)
            and item.get("type") == "image_generation_call"
            and isinstance(item.get("result"), str)
        ):
            payloads.append(item["result"])

    if payloads:
        return payloads

    for event in events:
        if event.get("type") != "response.completed":
            continue
        response_obj = event.get("response")
        output = response_obj.get("output") if isinstance(response_obj, dict) else None
        if not isinstance(output, list):
            continue
        for item in output:
            if (
                isinstance(item, dict)
                and item.get("type") == "image_generation_call"
                and isinstance(item.get("result"), str)
            ):
                payloads.append(item["result"])
    if not payloads:
        raise RuntimeError("No image payload found in Codex response.")
    return payloads


def _runtime_python_path() -> str:
    return sys.executable


def _cli_reinstall_hint() -> str:
    return "`pipx install --force --editable <path-to-image-to-editable-ppt>/cli`"


def _dependency_hint(package: str, *, upgrade: bool = False) -> str:
    package_arg = f"-U {package}" if upgrade else package
    runtime_python = _runtime_python_path()
    return (
        "Install image-to-editable-ppt with pipx so CLI dependencies are installed, for example "
        f"{_cli_reinstall_hint()}, "
        f"or install {package} directly in this environment with `{runtime_python} -m pip install {package_arg}`."
    )


def _ensure_api_key(dry_run: bool) -> None:
    if os.getenv("OPENAI_API_KEY"):
        print(f"OPENAI_API_KEY is set. API target: {_api_target_label()}.", file=sys.stderr)
        return
    if dry_run:
        _warn(f"OPENAI_API_KEY is not set; dry-run only. API target: {_api_target_label()}.")
        return
    base_url = _api_base_url()
    model = _default_model()
    if base_url:
        command = (
            'editppt config --api-key "your-api-key" '
            f'--base-url "{base_url}" --model {model}'
        )
        target_hint = f"Detected third-party OpenAI-compatible API via OPENAI_BASE_URL={base_url}."
    else:
        command = f'editppt config --api-key "your-api-key" --model {model}'
        target_hint = "Detected official OpenAI API mode because OPENAI_BASE_URL is not set."
    _die(
        "Neither Codex OAuth nor OPENAI_API_KEY is available for editppt image generation.\n"
        f"{target_hint}\n"
        f"To use Codex OAuth, run `codex login` so {_codex_auth_file()} exists.\n"
        "To use a third-party OpenAI-compatible image API, configure ~/.editppt/config.yaml once:\n"
        f"  {command}\n"
        "To use a third-party proxy, set OPENAI_BASE_URL and the provider's model name."
    )


def _read_prompt(prompt: Optional[str], prompt_file: Optional[str]) -> str:
    if prompt and prompt_file:
        _die("Use --prompt or --prompt-file, not both.")
    if prompt_file:
        if prompt_file == "-":
            return sys.stdin.read().strip()
        path = Path(prompt_file)
        if not path.exists():
            _die(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
    if prompt:
        return prompt.strip()
    _die("Missing prompt. Use --prompt or --prompt-file.")
    return ""  # unreachable


def _check_image_paths(paths: Iterable[str]) -> List[Path]:
    resolved: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            _die(f"Image file not found: {path}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Image exceeds 50MB limit: {path}")
        resolved.append(path)
    return resolved


def _normalize_output_format(fmt: Optional[str]) -> str:
    if not fmt:
        return DEFAULT_OUTPUT_FORMAT
    fmt = fmt.lower()
    if fmt not in {"png", "jpeg", "jpg", "webp"}:
        _die("output-format must be png, jpeg, jpg, or webp.")
    return "jpeg" if fmt == "jpg" else fmt


def _parse_size(size: str) -> Optional[Tuple[int, int]]:
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", size)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _validate_gpt_image_2_size(size: str) -> None:
    if size == "auto":
        return

    parsed = _parse_size(size)
    if parsed is None:
        _die("size must be auto or WIDTHxHEIGHT, for example 1024x1024.")

    width, height = parsed
    max_edge = max(width, height)
    min_edge = min(width, height)
    total_pixels = width * height

    if max_edge > GPT_IMAGE_2_MAX_EDGE:
        _die("gpt-image-2 size maximum edge length must be less than or equal to 3840px.")
    if width % 16 != 0 or height % 16 != 0:
        _die("gpt-image-2 size width and height must be multiples of 16px.")
    if max_edge / min_edge > GPT_IMAGE_2_MAX_RATIO:
        _die("gpt-image-2 size long edge to short edge ratio must not exceed 3:1.")
    if total_pixels < GPT_IMAGE_2_MIN_PIXELS or total_pixels > GPT_IMAGE_2_MAX_PIXELS:
        _die(
            "gpt-image-2 size total pixels must be at least 655,360 and no more than 8,294,400."
        )


def _validate_size(size: str, model: str) -> None:
    if _is_gpt_image_2_model(model):
        _validate_gpt_image_2_size(size)
        return

    if size not in ALLOWED_LEGACY_SIZES:
        _die(
            "size must be one of 1024x1024, 1536x1024, 1024x1536, or auto for this GPT Image model."
        )


def _validate_quality(quality: str) -> None:
    if quality not in ALLOWED_QUALITIES:
        _die("quality must be one of low, medium, high, or auto.")


def _validate_background(background: Optional[str]) -> None:
    if background not in ALLOWED_BACKGROUNDS:
        _die("background must be one of transparent, opaque, or auto.")


def _validate_model(model: str) -> None:
    if GPT_IMAGE_MODEL_PREFIX not in model:
        _die(
            "model must be a GPT Image model name containing 'gpt-image-' "
            "(for example gpt-image-2, openai/gpt-image-2, gpt-image-1.5, "
            "gpt-image-1, or gpt-image-1-mini)."
        )


def _is_gpt_image_2_model(model: str) -> bool:
    return GPT_IMAGE_2_MODEL in model


def _validate_transparency(background: Optional[str], output_format: str) -> None:
    if background == "transparent" and output_format not in {"png", "webp"}:
        _die("transparent background requires output-format png or webp.")


def _validate_model_specific_options(
    *,
    model: str,
    background: Optional[str],
) -> None:
    if not _is_gpt_image_2_model(model):
        return
    if background == "transparent":
        _die(
            "transparent backgrounds are not supported in gpt-image-2, the latest model. "
            "Use --model gpt-image-1.5 --background transparent --output-format png instead."
        )


def _validate_generate_payload(payload: Dict[str, Any]) -> None:
    model = str(payload.get("model", DEFAULT_MODEL))
    _validate_model(model)
    n = int(payload.get("n", 1))
    if n < 1 or n > 10:
        _die("n must be between 1 and 10")
    size = str(payload.get("size", DEFAULT_SIZE))
    quality = str(payload.get("quality", DEFAULT_QUALITY))
    background = payload.get("background")
    _validate_size(size, model)
    _validate_quality(quality)
    _validate_background(background)
    _validate_model_specific_options(model=model, background=background)
    oc = payload.get("output_compression")
    if oc is not None and not (0 <= int(oc) <= 100):
        _die("output_compression must be between 0 and 100")


def _build_output_paths(
    out: str,
    output_format: str,
    count: int,
    out_dir: Optional[str],
) -> List[Path]:
    ext = "." + output_format

    if out_dir:
        out_base = Path(out_dir)
        out_base.mkdir(parents=True, exist_ok=True)
        return [out_base / f"image_{i}{ext}" for i in range(1, count + 1)]

    out_path = Path(out)
    if out_path.exists() and out_path.is_dir():
        out_path.mkdir(parents=True, exist_ok=True)
        return [out_path / f"image_{i}{ext}" for i in range(1, count + 1)]

    if out_path.suffix == "":
        out_path = out_path.with_suffix(ext)
    elif output_format and out_path.suffix.lstrip(".").lower() != output_format:
        _warn(
            f"Output extension {out_path.suffix} does not match output-format {output_format}."
        )

    if count == 1:
        return [out_path]

    return [
        out_path.with_name(f"{out_path.stem}-{i}{out_path.suffix}")
        for i in range(1, count + 1)
    ]


def _augment_prompt(args: argparse.Namespace, prompt: str) -> str:
    fields = _fields_from_args(args)
    return _augment_prompt_fields(args.augment, prompt, fields)


def _augment_prompt_fields(augment: bool, prompt: str, fields: Dict[str, Optional[str]]) -> str:
    if not augment:
        return prompt

    sections: List[str] = []
    if fields.get("use_case"):
        sections.append(f"Use case: {fields['use_case']}")
    sections.append(f"Primary request: {prompt}")
    if fields.get("scene"):
        sections.append(f"Scene/background: {fields['scene']}")
    if fields.get("subject"):
        sections.append(f"Subject: {fields['subject']}")
    if fields.get("style"):
        sections.append(f"Style/medium: {fields['style']}")
    if fields.get("composition"):
        sections.append(f"Composition/framing: {fields['composition']}")
    if fields.get("lighting"):
        sections.append(f"Lighting/mood: {fields['lighting']}")
    if fields.get("palette"):
        sections.append(f"Color palette: {fields['palette']}")
    if fields.get("materials"):
        sections.append(f"Materials/textures: {fields['materials']}")
    if fields.get("text"):
        sections.append(f"Text (verbatim): \"{fields['text']}\"")
    if fields.get("constraints"):
        sections.append(f"Constraints: {fields['constraints']}")
    if fields.get("negative"):
        sections.append(f"Avoid: {fields['negative']}")

    return "\n".join(sections)


def _fields_from_args(args: argparse.Namespace) -> Dict[str, Optional[str]]:
    return {
        "use_case": getattr(args, "use_case", None),
        "scene": getattr(args, "scene", None),
        "subject": getattr(args, "subject", None),
        "style": getattr(args, "style", None),
        "composition": getattr(args, "composition", None),
        "lighting": getattr(args, "lighting", None),
        "palette": getattr(args, "palette", None),
        "materials": getattr(args, "materials", None),
        "text": getattr(args, "text", None),
        "constraints": getattr(args, "constraints", None),
        "negative": getattr(args, "negative", None),
    }


def _print_request(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _decode_and_write(images: List[str], outputs: List[Path], force: bool) -> None:
    for idx, image_b64 in enumerate(images):
        if idx >= len(outputs):
            break
        out_path = outputs[idx]
        if out_path.exists() and not force:
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(image_b64))
        print(f"Wrote {out_path}")


def _derive_downscale_path(path: Path, suffix: str) -> Path:
    if suffix and not suffix.startswith("-") and not suffix.startswith("_"):
        suffix = "-" + suffix
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def _downscale_image_bytes(image_bytes: bytes, *, max_dim: int, output_format: str) -> bytes:
    try:
        from PIL import Image
    except Exception:
        _die(f"Downscaling requires Pillow. {_dependency_hint('pillow')}")

    if max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    with Image.open(BytesIO(image_bytes)) as img:
        img.load()
        w, h = img.size
        scale = min(1.0, float(max_dim) / float(max(w, h)))
        target = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))

        resized = img if target == (w, h) else img.resize(target, Image.Resampling.LANCZOS)

        fmt = output_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"

        if fmt == "jpeg":
            if resized.mode in ("RGBA", "LA") or ("transparency" in getattr(resized, "info", {})):
                bg = Image.new("RGB", resized.size, (255, 255, 255))
                bg.paste(resized.convert("RGBA"), mask=resized.convert("RGBA").split()[-1])
                resized = bg
            else:
                resized = resized.convert("RGB")

        out = BytesIO()
        resized.save(out, format=fmt.upper())
        return out.getvalue()


def _decode_write_and_downscale(
    images: List[str],
    outputs: List[Path],
    *,
    force: bool,
    downscale_max_dim: Optional[int],
    downscale_suffix: str,
    output_format: str,
) -> None:
    for idx, image_b64 in enumerate(images):
        if idx >= len(outputs):
            break
        out_path = outputs[idx]
        if out_path.exists() and not force:
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        raw = base64.b64decode(image_b64)
        out_path.write_bytes(raw)
        print(f"Wrote {out_path}")

        if downscale_max_dim is None:
            continue

        derived = _derive_downscale_path(out_path, downscale_suffix)
        if derived.exists() and not force:
            _die(f"Output already exists: {derived} (use --force to overwrite)")
        derived.parent.mkdir(parents=True, exist_ok=True)
        resized = _downscale_image_bytes(raw, max_dim=downscale_max_dim, output_format=output_format)
        derived.write_bytes(resized)
        print(f"Wrote {derived}")


def _write_codex_payloads_and_downscale(
    payloads: List[str],
    outputs: List[Path],
    *,
    force: bool,
    downscale_max_dim: Optional[int],
    downscale_suffix: str,
    output_format: str,
) -> None:
    for idx, payload in enumerate(payloads):
        if idx >= len(outputs):
            break
        if len(payload) > MAX_CODEX_BASE64_CHARS:
            _die("Codex image payload exceeded size limit.")
        out_path = outputs[idx]
        if out_path.exists() and not force:
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(payload)
        out_path.write_bytes(raw)
        print(f"Wrote {out_path}")

        if downscale_max_dim is None:
            continue
        derived = _derive_downscale_path(out_path, downscale_suffix)
        if derived.exists() and not force:
            _die(f"Output already exists: {derived} (use --force to overwrite)")
        derived.parent.mkdir(parents=True, exist_ok=True)
        resized = _downscale_image_bytes(raw, max_dim=downscale_max_dim, output_format=output_format)
        derived.write_bytes(resized)
        print(f"Wrote {derived}")


def _run_codex_image(
    *,
    prompt: str,
    image_paths: List[Path],
    args: argparse.Namespace,
    output_paths: List[Path],
    output_format: str,
    downscaled: Optional[List[str]],
    endpoint_label: str,
) -> bool:
    if not _codex_available():
        return False
    if getattr(args, "mask", None):
        _warn("Codex OAuth image backend does not support --mask; using API fallback for this request.")
        return False
    if getattr(args, "output_compression", None) is not None or getattr(args, "moderation", None):
        _warn("Codex OAuth image backend does not support API-only compression/moderation options; using API fallback for this request.")
        return False

    responses_model = os.getenv("CODEX_RESPONSES_MODEL", DEFAULT_CODEX_RESPONSES_MODEL)
    body = _codex_body(
        prompt=prompt,
        image_paths=image_paths,
        model=args.model,
        responses_model=responses_model,
        size=args.size,
        quality=args.quality,
        output_format=output_format,
        background=args.background,
    )
    if args.dry_run:
        _print_request(
            {
                "backend": "codex-oauth",
                "endpoint": _codex_responses_url(),
                "operation": endpoint_label,
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                "auth_file": str(_codex_auth_file()),
                "responses_model": responses_model,
                "image_model": args.model,
                "input_images": [str(p) for p in image_paths],
                "size": args.size,
                "quality": args.quality,
                "output_format": output_format,
                "n": args.n,
            }
        )
        return True

    print(
        f"Calling Codex OAuth image backend ({endpoint_label}) with {len(image_paths)} input image(s).",
        file=sys.stderr,
    )
    started = time.time()
    payloads: List[str] = []
    for _ in range(args.n):
        text = _post_codex_sse(body, int(getattr(args, "timeout", 180)))
        payloads.extend(_extract_codex_image_payloads(text))
    elapsed = time.time() - started
    print(f"Codex OAuth image completed in {elapsed:.1f}s.", file=sys.stderr)
    _write_codex_payloads_and_downscale(
        payloads,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
    )
    return True


def _create_client():
    try:
        from openai import OpenAI
    except ImportError:
        _die(f"openai SDK not installed in the active environment. {_dependency_hint('openai')}")
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _create_async_client():
    try:
        from openai import AsyncOpenAI
    except ImportError:
        try:
            import openai as _openai  # noqa: F401
        except ImportError:
            _die(
                f"openai SDK not installed in the active environment. {_dependency_hint('openai')}"
            )
        _die(
            "AsyncOpenAI not available in this openai SDK version. "
            f"{_dependency_hint('openai', upgrade=True)}"
        )
    return AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:60] if value else "job"


def _normalize_job(job: Any, idx: int) -> Dict[str, Any]:
    if isinstance(job, str):
        prompt = job.strip()
        if not prompt:
            _die(f"Empty prompt at job {idx}")
        return {"prompt": prompt}
    if isinstance(job, dict):
        if "prompt" not in job or not str(job["prompt"]).strip():
            _die(f"Missing prompt for job {idx}")
        return job
    _die(f"Invalid job at index {idx}: expected string or object.")
    return {}  # unreachable


def _read_jobs_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        _die(f"Input file not found: {p}")
    jobs: List[Dict[str, Any]] = []
    for line_no, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item: Any
            if line.startswith("{"):
                item = json.loads(line)
            else:
                item = line
            jobs.append(_normalize_job(item, idx=line_no))
        except json.JSONDecodeError as exc:
            _die(f"Invalid JSON on line {line_no}: {exc}")
    if not jobs:
        _die("No jobs found in input file.")
    if len(jobs) > MAX_BATCH_JOBS:
        _die(f"Too many jobs ({len(jobs)}). Max is {MAX_BATCH_JOBS}.")
    return jobs


def _merge_non_null(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(dst)
    for k, v in src.items():
        if v is not None:
            merged[k] = v
    return merged


def _job_output_paths(
    *,
    out_dir: Path,
    output_format: str,
    idx: int,
    prompt: str,
    n: int,
    explicit_out: Optional[str],
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "." + output_format

    if explicit_out:
        base = Path(explicit_out)
        if base.suffix == "":
            base = base.with_suffix(ext)
        elif base.suffix.lstrip(".").lower() != output_format:
            _warn(
                f"Job {idx}: output extension {base.suffix} does not match output-format {output_format}."
            )
        base = out_dir / base.name
    else:
        slug = _slugify(prompt[:80])
        base = out_dir / f"{idx:03d}-{slug}{ext}"

    if n == 1:
        return [base]
    return [
        base.with_name(f"{base.stem}-{i}{base.suffix}")
        for i in range(1, n + 1)
    ]


def _job_image_values(job: Dict[str, Any]) -> List[str]:
    value = job.get("image")
    if value is None:
        value = job.get("images")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    _die("Batch job image/images must be a string path or a list of paths.")
    return []


def _check_mask_path(mask: Optional[str]) -> Optional[Path]:
    if not mask:
        return None
    mask_path = Path(mask)
    if not mask_path.exists():
        _die(f"Mask file not found: {mask_path}")
    if mask_path.suffix.lower() != ".png":
        _warn(f"Mask should be a PNG with an alpha channel: {mask_path}")
    if mask_path.stat().st_size > MAX_IMAGE_BYTES:
        _warn(f"Mask exceeds 50MB limit: {mask_path}")
    return mask_path


def _prepare_batch_job(
    *,
    args: argparse.Namespace,
    job: Dict[str, Any],
    idx: int,
    out_dir: Path,
    base_fields: Dict[str, Optional[str]],
    base_payload: Dict[str, Any],
) -> Dict[str, Any]:
    prompt = str(job["prompt"]).strip()
    fields = _merge_non_null(base_fields, job.get("fields", {}))
    fields = _merge_non_null(fields, {k: job.get(k) for k in base_fields.keys()})
    augmented = _augment_prompt_fields(args.augment, prompt, fields)

    payload = dict(base_payload)
    payload["prompt"] = augmented
    payload = _merge_non_null(payload, {k: job.get(k) for k in base_payload.keys()})
    payload = {k: v for k, v in payload.items() if v is not None}

    _validate_generate_payload(payload)
    output_format = _normalize_output_format(payload.get("output_format"))
    _validate_transparency(payload.get("background"), output_format)
    payload["output_format"] = output_format

    n = int(payload.get("n", 1))
    output_paths = _job_output_paths(
        out_dir=out_dir,
        output_format=output_format,
        idx=idx,
        prompt=prompt,
        n=n,
        explicit_out=job.get("out"),
    )
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    image_paths = _check_image_paths(_job_image_values(job))
    mask_path = _check_mask_path(job.get("mask"))
    if mask_path is not None and not image_paths:
        _die(f"Batch job {idx} has mask but no image/images input.")

    return {
        "idx": idx,
        "job_label": f"[job {idx}]",
        "prompt": prompt,
        "augmented_prompt": augmented,
        "payload": payload,
        "output_format": output_format,
        "output_paths": output_paths,
        "downscaled": downscaled,
        "image_paths": image_paths,
        "mask_path": mask_path,
        "is_edit": bool(image_paths),
    }


def _prepare_batch_jobs(
    *,
    args: argparse.Namespace,
    jobs: List[Dict[str, Any]],
    out_dir: Path,
    base_fields: Dict[str, Optional[str]],
    base_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    prepared = [
        _prepare_batch_job(
            args=args,
            job=job,
            idx=i,
            out_dir=out_dir,
            base_fields=base_fields,
            base_payload=base_payload,
        )
        for i, job in enumerate(jobs, start=1)
    ]

    seen: Dict[Path, int] = {}
    for spec in prepared:
        paths = list(spec["output_paths"])
        if spec["downscaled"]:
            paths.extend(Path(path) for path in spec["downscaled"])
        for path in paths:
            previous = seen.get(path)
            if previous is not None:
                _die(f"Duplicate batch output path: {path} used by jobs {previous} and {spec['idx']}.")
            seen[path] = spec["idx"]
    return prepared


def _extract_retry_after_seconds(exc: Exception) -> Optional[float]:
    # Best-effort: openai SDK errors vary by version. Prefer a conservative fallback.
    for attr in ("retry_after", "retry_after_seconds"):
        val = getattr(exc, attr, None)
        if isinstance(val, (int, float)) and val >= 0:
            return float(val)
    msg = str(exc)
    m = re.search(r"retry[- ]after[:= ]+([0-9]+(?:\\.[0-9]+)?)", msg, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _is_transient_error(exc: Exception) -> bool:
    if _is_rate_limit_error(exc):
        return True
    name = exc.__class__.__name__.lower()
    if "timeout" in name or "timedout" in name or "tempor" in name:
        return True
    msg = str(exc).lower()
    return (
        "timeout" in msg
        or "timed out" in msg
        or "connection reset" in msg
        or "retry your request" in msg
        or "processing your request" in msg
    )


def _run_codex_image_with_retries(
    *,
    attempts: int,
    job_label: str,
    prompt: str,
    image_paths: List[Path],
    args: argparse.Namespace,
    output_paths: List[Path],
    output_format: str,
    downscaled: Optional[List[str]],
    endpoint_label: str,
) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            handled = _run_codex_image(
                prompt=prompt,
                image_paths=image_paths,
                args=args,
                output_paths=output_paths,
                output_format=output_format,
                downscaled=downscaled,
                endpoint_label=endpoint_label,
            )
            if not handled:
                raise RuntimeError("Codex OAuth backend cannot handle this batch job.")
            return
        except Exception as exc:
            last_exc = exc
            if not _is_transient_error(exc) or attempt == attempts:
                raise
            sleep_s = _extract_retry_after_seconds(exc)
            if sleep_s is None:
                sleep_s = min(60.0, 2.0**attempt)
            print(
                f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                file=sys.stderr,
            )
            time.sleep(sleep_s)
    raise last_exc or RuntimeError("unknown error")


async def _generate_one_with_retries(
    client: Any,
    payload: Dict[str, Any],
    *,
    attempts: int,
    job_label: str,
) -> Any:
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await client.images.generate(**payload)
        except Exception as exc:
            last_exc = exc
            if not _is_transient_error(exc):
                raise
            if attempt == attempts:
                raise
            sleep_s = _extract_retry_after_seconds(exc)
            if sleep_s is None:
                sleep_s = min(60.0, 2.0**attempt)
            print(
                f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                file=sys.stderr,
            )
            await asyncio.sleep(sleep_s)
    raise last_exc or RuntimeError("unknown error")


async def _edit_one_with_retries(
    client: Any,
    payload: Dict[str, Any],
    image_paths: List[Path],
    mask_path: Optional[Path],
    *,
    attempts: int,
    job_label: str,
) -> Any:
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            with _open_files(image_paths) as image_files, _open_mask(mask_path) as mask_file:
                request_payload = dict(payload)
                request_payload["image"] = image_files if len(image_files) > 1 else image_files[0]
                if mask_file is not None:
                    request_payload["mask"] = mask_file
                return await client.images.edit(**request_payload)
        except Exception as exc:
            last_exc = exc
            if not _is_transient_error(exc):
                raise
            if attempt == attempts:
                raise
            sleep_s = _extract_retry_after_seconds(exc)
            if sleep_s is None:
                sleep_s = min(60.0, 2.0**attempt)
            print(
                f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                file=sys.stderr,
            )
            await asyncio.sleep(sleep_s)
    raise last_exc or RuntimeError("unknown error")


async def _run_generate_batch(args: argparse.Namespace) -> int:
    jobs = _read_jobs_jsonl(args.input)
    out_dir = Path(args.out_dir)

    base_fields = _fields_from_args(args)
    base_payload = {
        "model": args.model,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }
    prepared_jobs = _prepare_batch_jobs(
        args=args,
        jobs=jobs,
        out_dir=out_dir,
        base_fields=base_fields,
        base_payload=base_payload,
    )

    if _codex_available():
        any_failed = False

        def run_codex_job(spec: Dict[str, Any]) -> Tuple[int, Optional[str]]:
            job_args = argparse.Namespace(**vars(args))
            for key, value in spec["payload"].items():
                if key != "prompt":
                    setattr(job_args, key, value)
            try:
                if spec["mask_path"] is not None:
                    raise RuntimeError("Codex OAuth batch does not support mask jobs; use API credentials for masked edits.")
                _run_codex_image_with_retries(
                    attempts=args.max_attempts,
                    job_label=spec["job_label"],
                    prompt=spec["augmented_prompt"],
                    image_paths=spec["image_paths"],
                    args=job_args,
                    output_paths=spec["output_paths"],
                    output_format=spec["output_format"],
                    downscaled=spec["downscaled"],
                    endpoint_label="batch",
                )
                return spec["idx"], None
            except Exception as exc:
                return spec["idx"], str(exc)

        if args.dry_run:
            for spec in prepared_jobs:
                idx, error_message = run_codex_job(spec)
                if error_message is None:
                    continue
                any_failed = True
                print(f"[job {idx}/{len(prepared_jobs)}] failed: {error_message}", file=sys.stderr)
                if args.fail_fast:
                    raise RuntimeError(error_message)
            return 1 if any_failed else 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(run_codex_job, spec) for spec in prepared_jobs]
            for future in concurrent.futures.as_completed(futures):
                idx, error_message = future.result()
                if error_message is None:
                    continue
                any_failed = True
                print(f"[job {idx}/{len(prepared_jobs)}] failed: {error_message}", file=sys.stderr)
                if args.fail_fast:
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
                    raise RuntimeError(error_message)
        return 1 if any_failed else 0

    if args.dry_run:
        for spec in prepared_jobs:
            payload_preview = dict(spec["payload"])
            if spec["is_edit"]:
                payload_preview["image"] = [str(p) for p in spec["image_paths"]]
                if spec["mask_path"]:
                    payload_preview["mask"] = str(spec["mask_path"])
            _print_request(
                {
                    "backend": "openai-compatible-api",
                    "endpoint": "/v1/images/edits" if spec["is_edit"] else "/v1/images/generations",
                    "operation": "edit" if spec["is_edit"] else "generate",
                    "job": spec["idx"],
                    "outputs": [str(p) for p in spec["output_paths"]],
                    "outputs_downscaled": spec["downscaled"],
                    **payload_preview,
                }
            )
        return 0

    client = _create_async_client()
    sem = asyncio.Semaphore(args.concurrency)

    any_failed = False

    async def run_job(i: int, job: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        nonlocal any_failed
        spec = job
        job_label = f"[job {i}/{len(prepared_jobs)}]"
        try:
            async with sem:
                print(f"{job_label} starting", file=sys.stderr)
                started = time.time()
                if spec["is_edit"]:
                    result = await _edit_one_with_retries(
                        client,
                        spec["payload"],
                        spec["image_paths"],
                        spec["mask_path"],
                        attempts=args.max_attempts,
                        job_label=job_label,
                    )
                else:
                    result = await _generate_one_with_retries(
                        client,
                        spec["payload"],
                        attempts=args.max_attempts,
                        job_label=job_label,
                    )
                elapsed = time.time() - started
                print(f"{job_label} completed in {elapsed:.1f}s", file=sys.stderr)
            images = [item.b64_json for item in result.data]
            _decode_write_and_downscale(
                images,
                spec["output_paths"],
                force=args.force,
                downscale_max_dim=args.downscale_max_dim,
                downscale_suffix=args.downscale_suffix,
                output_format=spec["output_format"],
            )
            return i, None
        except Exception as exc:
            any_failed = True
            print(f"{job_label} failed: {exc}", file=sys.stderr)
            if args.fail_fast:
                raise
            return i, str(exc)

    tasks = [asyncio.create_task(run_job(i, spec)) for i, spec in enumerate(prepared_jobs, start=1)]

    try:
        await asyncio.gather(*tasks)
    except Exception:
        for t in tasks:
            if not t.done():
                t.cancel()
        raise

    return 1 if any_failed else 0


def _generate_batch(args: argparse.Namespace) -> None:
    exit_code = asyncio.run(_run_generate_batch(args))
    if exit_code:
        raise SystemExit(exit_code)


def _generate(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        if _run_codex_image(
            prompt=prompt,
            image_paths=[],
            args=args,
            output_paths=output_paths,
            output_format=output_format,
            downscaled=downscaled,
            endpoint_label="generate",
        ):
            return
        _print_request(
            {
                "backend": "openai-compatible-api",
                "endpoint": "/v1/images/generations",
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **payload,
            }
        )
        return

    if _run_codex_image(
        prompt=prompt,
        image_paths=[],
        args=args,
        output_paths=output_paths,
        output_format=output_format,
        downscaled=downscaled,
        endpoint_label="generate",
    ):
        return

    print(
        "Calling Image API (generation). This can take up to a couple of minutes.",
        file=sys.stderr,
    )
    started = time.time()
    client = _create_client()
    result = client.images.generate(**payload)
    elapsed = time.time() - started
    print(f"Generation completed in {elapsed:.1f}s.", file=sys.stderr)

    images = [item.b64_json for item in result.data]
    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
    )


def _edit(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    image_paths = _check_image_paths(args.image)
    mask_path = Path(args.mask) if args.mask else None
    if mask_path:
        if not mask_path.exists():
            _die(f"Mask file not found: {mask_path}")
        if mask_path.suffix.lower() != ".png":
            _warn(f"Mask should be a PNG with an alpha channel: {mask_path}")
        if mask_path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Mask exceeds 50MB limit: {mask_path}")

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        if _run_codex_image(
            prompt=prompt,
            image_paths=image_paths,
            args=args,
            output_paths=output_paths,
            output_format=output_format,
            downscaled=downscaled,
            endpoint_label="edit",
        ):
            return
        payload_preview = dict(payload)
        payload_preview["image"] = [str(p) for p in image_paths]
        if mask_path:
            payload_preview["mask"] = str(mask_path)
        _print_request(
            {
                "backend": "openai-compatible-api",
                "endpoint": "/v1/images/edits",
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **payload_preview,
            }
        )
        return

    if _run_codex_image(
        prompt=prompt,
        image_paths=image_paths,
        args=args,
        output_paths=output_paths,
        output_format=output_format,
        downscaled=downscaled,
        endpoint_label="edit",
    ):
        return

    print(
        f"Calling Image API (edit) with {len(image_paths)} image(s).",
        file=sys.stderr,
    )
    started = time.time()
    client = _create_client()

    with _open_files(image_paths) as image_files, _open_mask(mask_path) as mask_file:
        request = dict(payload)
        request["image"] = image_files if len(image_files) > 1 else image_files[0]
        if mask_file is not None:
            request["mask"] = mask_file
        result = client.images.edit(**request)

    elapsed = time.time() - started
    print(f"Edit completed in {elapsed:.1f}s.", file=sys.stderr)
    images = [item.b64_json for item in result.data]
    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
    )


def _open_files(paths: List[Path]):
    return _FileBundle(paths)


def _open_mask(mask_path: Optional[Path]):
    if mask_path is None:
        return _NullContext()
    return _SingleFile(mask_path)


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _SingleFile:
    def __init__(self, path: Path):
        self._path = path
        self._handle = None

    def __enter__(self):
        self._handle = self._path.open("rb")
        return self._handle

    def __exit__(self, exc_type, exc, tb):
        if self._handle:
            try:
                self._handle.close()
            except Exception:
                pass
        return False


class _FileBundle:
    def __init__(self, paths: List[Path]):
        self._paths = paths
        self._handles: List[object] = []

    def __enter__(self):
        self._handles = [p.open("rb") for p in self._paths]
        return self._handles

    def __exit__(self, exc_type, exc, tb):
        for handle in self._handles:
            try:
                handle.close()
            except Exception:
                pass
        return False


def _add_shared_args(
    parser: argparse.ArgumentParser,
    *,
    include_prompt: bool = True,
    include_out: bool = True,
) -> None:
    parser.add_argument("--model", default=_default_model(), help="Image model. Defaults to IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL or gpt-image-2.")
    if include_prompt:
        parser.add_argument("--prompt", help="Prompt text. Use this or --prompt-file.")
        parser.add_argument("--prompt-file", help="Read prompt text from a file, or '-' for stdin.")
    parser.add_argument("--n", type=int, default=1, help="Number of images to generate, 1-10.")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Output size such as 2560x1440 or auto.")
    parser.add_argument("--quality", default=DEFAULT_QUALITY, help="Image quality: low, medium, high, or auto.")
    parser.add_argument("--background", help="Background mode when supported: transparent, opaque, or auto.")
    parser.add_argument("--output-format", help="Output format: png, jpeg, jpg, or webp.")
    parser.add_argument("--output-compression", type=int, help="Compression 0-100 when supported.")
    parser.add_argument("--moderation", help="Provider moderation setting when supported.")
    if include_out:
        parser.add_argument("--out", default=DEFAULT_OUTPUT_PATH, help="Output file for one image.")
    parser.add_argument("--out-dir", help="Output directory for multiple images or batch generation.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate arguments and show the selected backend without calling it.")
    parser.add_argument("--timeout", type=int, default=180, help="Network timeout in seconds for Codex OAuth requests.")
    parser.add_argument("--augment", dest="augment", action="store_true", help="Expand prompt with structured visual hints.")
    parser.add_argument("--no-augment", dest="augment", action="store_false", help="Send the prompt without augmentation.")
    parser.set_defaults(augment=True)

    # Prompt augmentation hints
    parser.add_argument("--use-case", help="Short intended use, for example clean background or icon asset.")
    parser.add_argument("--scene", help="Scene description appended during prompt augmentation.")
    parser.add_argument("--subject", help="Main subject description appended during prompt augmentation.")
    parser.add_argument("--style", help="Style requirements appended during prompt augmentation.")
    parser.add_argument("--composition", help="Composition requirements appended during prompt augmentation.")
    parser.add_argument("--lighting", help="Lighting requirements appended during prompt augmentation.")
    parser.add_argument("--palette", help="Color palette requirements appended during prompt augmentation.")
    parser.add_argument("--materials", help="Material or texture requirements appended during prompt augmentation.")
    parser.add_argument("--text", help="Text rendering requirements; use 'no text' for text-free assets.")
    parser.add_argument("--constraints", help="Hard visual constraints the result must follow.")
    parser.add_argument("--negative", help="Things to avoid.")

    # Post-processing (optional): generate an additional downscaled copy for fast web loading.
    parser.add_argument("--downscale-max-dim", type=int, help="Also save a downscaled copy with this maximum edge length.")
    parser.add_argument("--downscale-suffix", default=DEFAULT_DOWNSCALE_SUFFIX, help="Suffix for the downscaled copy.")


def main() -> int:
    _load_runtime_env()
    parser = argparse.ArgumentParser(
        prog="editppt image",
        description="""Unified image generation/editing backend for editppt.

Use this command for all generated images, image edits, clean bases, foreground
asset sheets, and batch image jobs in image-to-editable-ppt runs.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=IMAGE_HELP_EPILOG,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_parser = subparsers.add_parser(
        "generate",
        help="Create a new image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=GENERATE_HELP_EPILOG,
    )
    _add_shared_args(gen_parser)
    gen_parser.set_defaults(func=_generate)

    batch_parser = subparsers.add_parser(
        "batch",
        help="Generate or edit multiple JSONL jobs concurrently",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=BATCH_HELP_EPILOG,
    )
    _add_shared_args(batch_parser, include_prompt=False, include_out=False)
    batch_parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL file. Each line needs prompt; add image/images to run an edit job.",
    )
    batch_parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent API calls, 1-25.")
    batch_parser.add_argument("--max-attempts", type=int, default=3, help="Retry attempts per job, 1-10.")
    batch_parser.add_argument("--fail-fast", action="store_true", help="Stop the batch after the first failed job.")
    batch_parser.set_defaults(func=_generate_batch)

    edit_parser = subparsers.add_parser(
        "edit",
        help="Edit one or more images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EDIT_HELP_EPILOG,
    )
    _add_shared_args(edit_parser)
    edit_parser.add_argument("--image", action="append", required=True, help="Input image path. Repeat for multiple inputs.")
    edit_parser.add_argument("--mask", help="Optional mask image path.")
    edit_parser.set_defaults(func=_edit)

    args = parser.parse_args()
    if args.n < 1 or args.n > 10:
        _die("--n must be between 1 and 10")
    if getattr(args, "concurrency", 1) < 1 or getattr(args, "concurrency", 1) > 25:
        _die("--concurrency must be between 1 and 25")
    if getattr(args, "max_attempts", 3) < 1 or getattr(args, "max_attempts", 3) > 10:
        _die("--max-attempts must be between 1 and 10")
    if args.output_compression is not None and not (0 <= args.output_compression <= 100):
        _die("--output-compression must be between 0 and 100")
    if args.command == "batch" and not args.out_dir:
        _die("batch requires --out-dir")
    if getattr(args, "downscale_max_dim", None) is not None and args.downscale_max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    _validate_model(args.model)
    _validate_size(args.size, args.model)
    _validate_quality(args.quality)
    _validate_background(args.background)
    _validate_model_specific_options(model=args.model, background=args.background)
    if not _codex_available():
        _ensure_api_key(args.dry_run)

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
