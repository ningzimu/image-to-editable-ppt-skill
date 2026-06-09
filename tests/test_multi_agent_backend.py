import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "skills/image-to-editable-ppt/cli"
RUNTIME_DIR = CLI_DIR / "editppt/runtime"
PROMPT_SCRIPT = ROOT / "skills/image-to-editable-ppt/scripts/build-page-worker-prompt.py"
sys.path.insert(0, str(CLI_DIR))

CLI_ENV = os.environ.copy()
CLI_ENV["PYTHONPATH"] = (
    str(CLI_DIR)
    if not CLI_ENV.get("PYTHONPATH")
    else str(CLI_DIR) + os.pathsep + CLI_ENV["PYTHONPATH"]
)
os.environ["PYTHONPATH"] = CLI_ENV["PYTHONPATH"]

from editppt.runtime import image_gen  # noqa: E402


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_minimal_run(tmpdir):
    run_dir = Path(tmpdir)
    page_1 = run_dir / "pages/page_001"
    page_2 = run_dir / "pages/page_002"
    page_1.mkdir(parents=True)
    page_2.mkdir(parents=True)
    write_json(
        run_dir / "deck_manifest.json",
        {
            "schema_version": 1,
            "run_id": "run-test",
            "pages": [
                {
                    "page_id": "page_001",
                    "page_dir": "pages/page_001",
                    "page_request": "pages/page_001/page_request.json",
                },
                {
                    "page_id": "page_002",
                    "page_dir": "pages/page_002",
                    "page_request": "pages/page_002/page_request.json",
                },
            ],
        },
    )
    write_json(run_dir / "run_state.json", {"status": "inputs_prepared", "history": []})
    write_json(
        run_dir / "page_jobs.json",
        {
            "schema_version": 1,
            "run_id": "run-test",
            "max_concurrent_pages": 6,
            "pages": [
                {
                    "page_id": "page_001",
                    "status": "pending",
                    "page_dir": "pages/page_001",
                    "page_request": "pages/page_001/page_request.json",
                    "result": None,
                    "accepted": False,
                },
                {
                    "page_id": "page_002",
                    "status": "pending",
                    "page_dir": "pages/page_002",
                    "page_request": "pages/page_002/page_request.json",
                    "result": None,
                    "accepted": False,
                },
            ],
        },
    )
    for page_dir, page_id in [(page_1, "page_001"), (page_2, "page_002")]:
        write_json(page_dir / "page_request.json", {"schema_version": 1, "page_id": page_id})
    return run_dir


def valid_page_manifest(text="Valid Page"):
    return {
        "schema_version": 1,
        "source": {"width_px": 1600, "height_px": 900},
        "slide": {"width": 13.333, "height": 7.5},
        "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
        "text_boxes": [
            {
                "text": text,
                "box_px": [100, 100, 500, 80],
                "font_size": 24,
                "color": "#111111",
            }
        ],
        "shapes": [],
        "images": [],
        "visual_inventory": [],
        "background_strategy": {"type": "native", "color": "#ffffff"},
        "quality_checks": {
            "font_size_calibrated": True,
            "visual_inventory_matched": True,
            "background_strategy_checked": True,
            "shape_corner_geometry_checked": True,
        },
    }


def write_page_outputs(page_dir, text="Valid Page", validation_passed=True, manifest=None):
    write_json(page_dir / "manifest.json", manifest or valid_page_manifest(text))
    write_json(page_dir / "imagegen-jobs.json", {"schema_version": 1, "jobs": []})
    build = subprocess.run(
        [
            sys.executable,
            RUNTIME_DIR / "build_pptx_from_manifest.py",
            page_dir / "manifest.json",
            "--out",
            page_dir / "page.pptx",
        ],
        text=True,
        capture_output=True,
    )
    if build.returncode != 0:
        raise AssertionError(build.stderr or build.stdout)
    (page_dir / "preview.png").write_text("x", encoding="utf-8")
    (page_dir / "split_assets_contact.png").write_text("x", encoding="utf-8")
    write_json(page_dir / "validation.json", {"passed": validation_passed})
    write_json(
        page_dir / "page_result.json",
        {
            "page_manifest": "manifest.json",
            "imagegen_jobs": "imagegen-jobs.json",
            "page_pptx": "page.pptx",
            "preview": "preview.png",
            "contact_sheet": "split_assets_contact.png",
            "validation": "validation.json",
            "page_result": "page_result.json",
        },
    )


class MultiAgentBackendTest(unittest.TestCase):
    def test_package_console_entrypoint_help(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "editppt.cli",
                "--help",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("CLI for preparing, rebuilding, validating, and finalizing editable PPTX runs.", result.stdout)
        self.assertIn("Command groups", result.stdout)
        self.assertIn("usage: editppt", result.stdout)
        for command in ("setup", "doctor", "config", "prepare", "run", "image", "formula"):
            self.assertIn(command, result.stdout)
        for old_command in ("install", "uninstall", "update", "process-asset-sheet", "record-image", "queue-repairs"):
            self.assertNotIn(f"    {old_command}", result.stdout)

    def test_old_top_level_commands_are_removed(self):
        for command in ("status", "install", "uninstall", "update"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "editppt.cli", command, "--help"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("invalid choice", result.stderr)

    def test_removed_run_prompt_command_is_rejected(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "run", "prompt", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid choice", result.stderr)

    def test_runtime_doctor_direct_entrypoint_is_cli_scoped(self):
        result = subprocess.run(
            [sys.executable, str(RUNTIME_DIR / "main.py"), "doctor", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotIn("skill_root", payload)
        self.assertNotIn("<repo-path>", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("pipx upgrade image-to-editable-ppt", json.dumps(payload, ensure_ascii=False))

    def test_image_batch_help_uses_public_command_name(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "image", "batch", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage: editppt image batch", result.stdout)
        self.assertIn("Backend:", result.stdout)
        self.assertIn("JSONL input:", result.stdout)
        self.assertIn("image: \"source.png\" -> edit job", result.stdout)
        self.assertIn("images: [\"source.png\", \"style.png\"]", result.stdout)
        self.assertIn("Duplicate output paths fail before requests are sent.", result.stdout)
        self.assertNotIn("--prompt PROMPT", result.stdout)
        self.assertNotIn("--prompt-file", result.stdout)
        self.assertNotIn("--out OUT", result.stdout)
        self.assertNotIn("generate-batch", result.stdout)

    def test_image_help_documents_backend_contract(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "image", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Backend selection:", result.stdout)
        self.assertIn("Codex OAuth uses", result.stdout)
        self.assertIn("API fallback uses", result.stdout)
        self.assertIn("editppt image edit --image pages/page_001/source.png", result.stdout)

    def test_image_edit_help_omits_unsupported_fidelity_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "image", "edit", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage: editppt image edit", result.stdout)
        self.assertIn("Background cleanup", result.stdout)
        self.assertIn("strict visual reference", result.stdout)
        self.assertNotIn("--input-fidelity", result.stdout)

    def test_process_sheet_resolves_asset_source_relative_to_page_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp) / "pages/page_001"
            assets_dir = page_dir / "assets"
            assets_dir.mkdir(parents=True)
            Image.new("RGB", (24, 24), "#ff00ff").save(assets_dir / "sheet.png")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "image",
                    "process-sheet",
                    str(page_dir),
                    "--asset-sheet-source",
                    "assets/sheet.png",
                    "--chroma",
                    "copied-sheet.png",
                    "--skip-chroma",
                    "--skip-split",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((page_dir / "copied-sheet.png").exists())

    def test_image_batch_api_dry_run_routes_image_jobs_to_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            jobs = Path(tmp) / "jobs.jsonl"
            out_dir = Path(tmp) / "out"
            Image.new("RGB", (24, 24), "white").save(source)
            jobs.write_text(
                json.dumps(
                    {
                        "prompt": "extract the foreground icon",
                        "image": str(source),
                        "out": "icon.png",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["CODEX_AUTH_FILE"] = str(Path(tmp) / "missing-auth.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "image",
                    "batch",
                    "--input",
                    str(jobs),
                    "--out-dir",
                    str(out_dir),
                    "--dry-run",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("openai-compatible-api", payload["backend"])
            self.assertEqual("/v1/images/edits", payload["endpoint"])
            self.assertEqual("edit", payload["operation"])
            self.assertEqual([str(source)], payload["image"])
            self.assertEqual([str(out_dir / "icon.png")], payload["outputs"])

    def test_image_batch_api_edit_jobs_run_concurrently(self):
        class FakeImage:
            b64_json = base64.b64encode(b"fake-png").decode("ascii")

        class FakeResult:
            data = [FakeImage()]

        class FakeImages:
            def __init__(self):
                self.active = 0
                self.max_active = 0
                self.requests = []

            async def edit(self, **request):
                self.requests.append(request)
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.05)
                self.active -= 1
                return FakeResult()

        class FakeClient:
            def __init__(self):
                self.images = FakeImages()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_1 = tmp_path / "source-1.png"
            source_2 = tmp_path / "source-2.png"
            jobs = tmp_path / "jobs.jsonl"
            out_dir = tmp_path / "out"
            Image.new("RGB", (24, 24), "white").save(source_1)
            Image.new("RGB", (24, 24), "black").save(source_2)
            jobs.write_text(
                "\n".join(
                    [
                        json.dumps({"prompt": "edit one", "image": str(source_1), "out": "one.png"}),
                        json.dumps({"prompt": "edit two", "image": str(source_2), "out": "two.png"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_client = FakeClient()
            args = argparse.Namespace(
                input=str(jobs),
                out_dir=str(out_dir),
                model="gpt-image-2",
                n=1,
                size="1024x1024",
                quality="low",
                background="auto",
                output_format="png",
                output_compression=None,
                moderation=None,
                downscale_max_dim=None,
                downscale_suffix="-web",
                augment=True,
                use_case=None,
                scene=None,
                subject=None,
                style=None,
                composition=None,
                lighting=None,
                palette=None,
                materials=None,
                text=None,
                constraints=None,
                negative=None,
                concurrency=2,
                max_attempts=1,
                fail_fast=False,
                force=True,
                dry_run=False,
                timeout=180,
            )

            with mock.patch.object(image_gen, "_codex_available", return_value=False), mock.patch.object(
                image_gen, "_create_async_client", return_value=fake_client
            ):
                exit_code = asyncio.run(image_gen._run_generate_batch(args))

            self.assertEqual(0, exit_code)
            self.assertEqual(2, fake_client.images.max_active)
            self.assertEqual(2, len(fake_client.images.requests))
            self.assertTrue((out_dir / "one.png").exists())
            self.assertTrue((out_dir / "two.png").exists())

    def test_image_edit_passthrough_preserves_image_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "out.png"
            Image.new("RGB", (24, 24), "white").save(source)
            env = os.environ.copy()
            env["CODEX_AUTH_FILE"] = str(Path(tmp) / "missing-auth.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "image",
                    "edit",
                    "--image",
                    str(source),
                    "--prompt",
                    "test",
                    "--out",
                    str(out),
                    "--dry-run",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([str(source)], payload["image"])
            self.assertEqual("Primary request: test", payload["prompt"])

    def test_image_edit_dry_run_prefers_codex_oauth_when_auth_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "out.png"
            auth = Path(tmp) / "auth.json"
            Image.new("RGB", (24, 24), "white").save(source)
            write_json(auth, {"tokens": {"access_token": "test-token"}})
            env = os.environ.copy()
            env["CODEX_AUTH_FILE"] = str(auth)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "image",
                    "edit",
                    "--image",
                    str(source),
                    "--prompt",
                    "test",
                    "--out",
                    str(out),
                    "--dry-run",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("codex-oauth", payload["backend"])
            self.assertEqual([str(source)], payload["input_images"])

    def test_runtime_config_writes_owner_only_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["EDITPPT_CONFIG_HOME"] = tmp
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "config",
                    "--api-key",
                    "sk-test-secret",
                    "--base-url",
                    "https://example.test/v1",
                    "--model",
                    "gpt-image-2",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            config_path = Path(tmp) / "config.yaml"
            self.assertTrue(config_path.exists())
            text = config_path.read_text(encoding="utf-8")
            self.assertIn("OPENAI_API_KEY: sk-test-secret", text)
            if sys.platform != "win32":
                mode = config_path.stat().st_mode
                self.assertFalse(mode & 0o077)

    def test_runtime_doctor_json_checks_cli_deps_without_large_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["EDITPPT_CONFIG_HOME"] = tmp
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "doctor",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"fitz", "PIL", "openai", "yaml"}, set(payload["dependencies"]))
            self.assertNotIn("skill_root", payload)
            self.assertNotIn("LibreOffice", result.stdout)
            self.assertNotIn("ImageMagick", result.stdout)

    def test_setup_is_idempotent_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["EDITPPT_CONFIG_HOME"] = str(Path(tmp) / "config")
            configured = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "config",
                    "--api-key",
                    "sk-test-secret",
                    "--base-url",
                    "https://example.test/v1",
                    "--model",
                    "gpt-image-2",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, configured.returncode, configured.stderr)

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "setup",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            first_payload = json.loads(first.stdout)
            self.assertEqual("ok", first_payload["setup"])
            config_path = Path(env["EDITPPT_CONFIG_HOME"]) / "config.yaml"
            before = config_path.read_text(encoding="utf-8")

            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "setup",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, second.returncode, second.stderr)
            second_payload = json.loads(second.stdout)
            self.assertEqual("ok", second_payload["setup"])
            self.assertEqual(before, config_path.read_text(encoding="utf-8"))

    def test_unified_cli_backend_defaults_to_editppt_image_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "run",
                    "backend",
                    run_dir,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            deck = read_json(run_dir / "deck_manifest.json")
            backend = deck["image_backend"]
            self.assertEqual("editppt-image-cli", backend["backend_id"])
            self.assertEqual("editppt image", backend["tool_name"])
            self.assertEqual("editppt image generate/edit/batch", backend["tool_call"])
            self.assertFalse(backend["requires_openai_api_key"])

    def test_prepare_writes_default_backend_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "slide.png"
            Image.new("RGB", (320, 180), "white").save(source)
            out_root = Path(tmp) / "runs"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "prepare",
                    str(source),
                    "--out-root",
                    str(out_root),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            deck_line = next(line for line in result.stdout.splitlines() if line.endswith("deck_manifest.json"))
            deck_path = Path(deck_line)
            self.assertTrue(deck_path.exists())
            deck = read_json(deck_path)
            self.assertEqual("editppt-image-cli", deck["image_backend"]["backend_id"])
            request = read_json(deck_path.parent / "pages/page_001/page_request.json")
            self.assertEqual(deck["image_backend"], request["image_backend"])

    def test_skill_prompt_script_output_is_accepted_by_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            write_json(
                run_dir / "deck_manifest.json",
                {
                    "schema_version": 1,
                    "run_id": "run-test",
                    "image_backend": {"backend_id": "editppt-image-cli"},
                    "pages": [],
                },
            )
            result = subprocess.run(
                [sys.executable, "-m", "editppt.cli", "run", "next", run_dir, "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            prompt_path = (run_dir / "pages/page_001/worker-prompt.md").resolve()
            self.assertEqual(str(prompt_path), payload["prompt_file"])
            self.assertIn(str(prompt_path), payload["next_command"])
            self.assertIn("editppt run dispatch", payload["next_command"])

            prompt = subprocess.run(
                [
                    sys.executable,
                    PROMPT_SCRIPT,
                    run_dir,
                    "--page",
                    "page_001",
                    "--out",
                    str(prompt_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, prompt.returncode, prompt.stderr)
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn(str(run_dir), prompt_text)
            self.assertIn(str(ROOT / "skills/image-to-editable-ppt/references/page-decision-tree.md"), prompt_text)

            dispatch = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "run",
                    "dispatch",
                    run_dir,
                    "--page",
                    "page_001",
                    "--agent-id",
                    "worker-1",
                    "--prompt-file",
                    str(prompt_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, dispatch.returncode, dispatch.stderr)
            jobs = read_json(run_dir / "page_jobs.json")
            self.assertEqual("dispatched", jobs["pages"][0]["status"])

    def test_single_page_next_and_record_allow_main_agent_direct_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            deck = read_json(run_dir / "deck_manifest.json")
            deck["image_backend"] = {"backend_id": "editppt-image-cli"}
            deck["pages"] = deck["pages"][:1]
            write_json(run_dir / "deck_manifest.json", deck)
            jobs = read_json(run_dir / "page_jobs.json")
            jobs["pages"] = jobs["pages"][:1]
            write_json(run_dir / "page_jobs.json", jobs)

            next_result = subprocess.run(
                [sys.executable, "-m", "editppt.cli", "run", "next", run_dir, "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, next_result.returncode, next_result.stderr)
            next_payload = json.loads(next_result.stdout)
            self.assertEqual("rebuild_page", next_payload["stage"])
            self.assertIn("editppt run record", next_payload["next_command"])

            page_dir = run_dir / "pages/page_001"
            write_page_outputs(page_dir, "Direct Page")

            record = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "run",
                    "record",
                    run_dir,
                    "--page",
                    "page_001",
                    "--agent-id",
                    "main",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, record.returncode, record.stderr)
            jobs = read_json(run_dir / "page_jobs.json")
            result_payload = jobs["pages"][0]["result"]
            self.assertEqual("recorded", jobs["pages"][0]["status"])
            self.assertEqual("direct-main-agent", result_payload["record_mode"])

    def test_configure_image_backend_writes_deck_and_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "configure_image_backend.py",
                    run_dir,
                    "--backend-id",
                    "editppt-image-cli",
                    "--tool-name",
                    "editppt image",
                    "--model",
                    "gpt-image-2",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            deck = read_json(run_dir / "deck_manifest.json")
            self.assertEqual("editppt-image-cli", deck["image_backend"]["backend_id"])
            request = read_json(run_dir / "pages/page_002/page_request.json")
            self.assertEqual(deck["image_backend"], request["image_backend"])

    def test_all_pending_pages_are_dispatchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            status = subprocess.run(
                [sys.executable, RUNTIME_DIR / "page_job_status.py", run_dir, "--json"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, status.returncode, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(["page_001", "page_002"], payload["dispatchable_pages"])

    def test_record_page_result_does_not_store_qa_note_or_known_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            jobs = read_json(run_dir / "page_jobs.json")
            page_2 = jobs["pages"][1]
            page_2["status"] = "dispatched"
            page_2["dispatch"] = {"agent_id": "worker-1"}
            write_json(run_dir / "page_jobs.json", jobs)

            page_dir = run_dir / "pages/page_002"
            write_page_outputs(page_dir, "Worker Page")

            result = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "record_page_result.py",
                    run_dir,
                    "--page",
                    "page_002",
                    "--agent-id",
                    "worker-1",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            jobs = read_json(run_dir / "page_jobs.json")
            result_payload = jobs["pages"][1]["result"]
            self.assertNotIn("qa_note", result_payload)
            self.assertNotIn("known_limits", result_payload)

    def test_record_page_result_rejects_manifest_without_positioned_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            jobs = read_json(run_dir / "page_jobs.json")
            page_2 = jobs["pages"][1]
            page_2["status"] = "dispatched"
            page_2["dispatch"] = {"agent_id": "worker-1"}
            write_json(run_dir / "page_jobs.json", jobs)

            page_dir = run_dir / "pages/page_002"
            manifest = valid_page_manifest("Missing Box")
            del manifest["text_boxes"][0]["box_px"]
            write_page_outputs(page_dir, manifest=manifest)

            result = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "record_page_result.py",
                    run_dir,
                    "--page",
                    "page_002",
                    "--agent-id",
                    "worker-1",
                ],
                text=True,
                capture_output=True,
            )
            combined_output = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Page manifest contract validation failed", combined_output)
            self.assertIn("text_boxes[0].box_px", combined_output)

    def test_record_page_result_refreshes_recorded_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            jobs = read_json(run_dir / "page_jobs.json")
            page_2 = jobs["pages"][1]
            page_2["status"] = "dispatched"
            page_2["dispatch"] = {"agent_id": "worker-1"}
            write_json(run_dir / "page_jobs.json", jobs)

            page_dir = run_dir / "pages/page_002"
            write_page_outputs(page_dir, "Refresh Page", validation_passed=False)

            first = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "record_page_result.py",
                    run_dir,
                    "--page",
                    "page_002",
                    "--agent-id",
                    "worker-1",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, first.returncode, first.stderr)

            write_json(page_dir / "validation.json", {"passed": True})
            second = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "record_page_result.py",
                    run_dir,
                    "--page",
                    "page_002",
                    "--agent-id",
                    "worker-1",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, second.returncode, second.stderr)
            jobs = read_json(run_dir / "page_jobs.json")
            self.assertIs(jobs["pages"][1]["result"]["validation_passed"], True)

    def test_finalize_rebuilds_final_deck_from_page_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            write_json(run_dir / "notes_manifest.json", {"notes": []})
            deck = read_json(run_dir / "deck_manifest.json")
            deck["slide"] = {"width": 13.333, "height": 7.5}
            deck["page_count"] = 2
            deck["notes_manifest"] = "notes_manifest.json"
            deck["output"] = "final/test_edited.pptx"
            for index, page in enumerate(deck["pages"], start=1):
                page["manifest"] = f"pages/page_{index:03d}/manifest.json"
                page["validation"] = f"pages/page_{index:03d}/validation.json"
            write_json(run_dir / "deck_manifest.json", deck)

            jobs = read_json(run_dir / "page_jobs.json")
            for index, page in enumerate(jobs["pages"], start=1):
                page_dir = run_dir / f"pages/page_{index:03d}"
                write_json(
                    page_dir / "manifest.json",
                    {
                        "schema_version": 1,
                        "source": {"width_px": 1600, "height_px": 900},
                        "slide": {"width": 13.333, "height": 7.5},
                        "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
                        "text_boxes": [
                            {
                                "text": f"Manifest Page {index}",
                                "box_px": [100, 100, 500, 80],
                                "font_size": 24,
                                "color": "#111111",
                            }
                        ],
                        "shapes": [],
                        "images": [],
                        "visual_inventory": [],
                        "background_strategy": {"type": "native", "color": "#ffffff"},
                        "quality_checks": {
                            "font_size_calibrated": True,
                            "visual_inventory_matched": True,
                            "background_strategy_checked": True,
                            "shape_corner_geometry_checked": True,
                        },
                    },
                )
                write_json(page_dir / "imagegen-jobs.json", {"schema_version": 1, "jobs": []})
                (page_dir / "page.pptx").write_text("not a pptx", encoding="utf-8")
                (page_dir / "preview.png").write_text("x", encoding="utf-8")
                (page_dir / "split_assets_contact.png").write_text("x", encoding="utf-8")
                write_json(page_dir / "validation.json", {"passed": True})
                write_json(
                    page_dir / "page_result.json",
                    {
                        "page_manifest": "manifest.json",
                        "imagegen_jobs": "imagegen-jobs.json",
                        "page_pptx": "page.pptx",
                        "preview": "preview.png",
                        "contact_sheet": "split_assets_contact.png",
                        "validation": "validation.json",
                        "page_result": "page_result.json",
                    },
                )
                page["status"] = "recorded"
                page["result"] = {"validation_passed": True}
            write_json(run_dir / "page_jobs.json", jobs)

            result = subprocess.run(
                [sys.executable, "-m", "editppt.cli", "run", "finalize", run_dir],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            final_pptx = run_dir / "final/test_edited.pptx"
            self.assertTrue(final_pptx.exists())
            with zipfile.ZipFile(final_pptx) as z:
                slide_text = z.read("ppt/slides/slide1.xml").decode("utf-8") + z.read("ppt/slides/slide2.xml").decode("utf-8")
            self.assertIn("Manifest Page 1", slide_text)
            self.assertIn("Manifest Page 2", slide_text)

    def test_finalize_rejects_recorded_manifest_without_positioned_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            write_json(run_dir / "notes_manifest.json", {"notes": []})
            deck = read_json(run_dir / "deck_manifest.json")
            deck["slide"] = {"width": 13.333, "height": 7.5}
            deck["page_count"] = 2
            deck["notes_manifest"] = "notes_manifest.json"
            deck["output"] = "final/test_edited.pptx"
            for index, page in enumerate(deck["pages"], start=1):
                page["manifest"] = f"pages/page_{index:03d}/manifest.json"
                page["validation"] = f"pages/page_{index:03d}/validation.json"
            write_json(run_dir / "deck_manifest.json", deck)

            jobs = read_json(run_dir / "page_jobs.json")
            for index, page in enumerate(jobs["pages"], start=1):
                page_dir = run_dir / f"pages/page_{index:03d}"
                manifest = valid_page_manifest(f"Manifest Page {index}")
                if index == 2:
                    del manifest["text_boxes"][0]["box_px"]
                write_json(page_dir / "manifest.json", manifest)
                write_json(page_dir / "validation.json", {"passed": True})
                page["status"] = "recorded"
                page["result"] = {"validation_passed": True}
            write_json(run_dir / "page_jobs.json", jobs)

            result = subprocess.run(
                [sys.executable, "-m", "editppt.cli", "run", "finalize", run_dir],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            combined_output = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode)
            self.assertIn("page_contract_violations", combined_output)
            self.assertIn("text_boxes[0].box_px", combined_output)

    def test_image_import_records_generated_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp) / "page_001"
            page_dir.mkdir()
            write_json(page_dir / "imagegen-jobs.json", {"schema_version": 1, "jobs": []})
            source = Path(tmp) / "generated.png"
            Image.new("RGBA", (12, 12), (255, 0, 0, 255)).save(source)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "editppt.cli",
                    "image",
                    "import",
                    str(page_dir),
                    "--job-id",
                    "job-1",
                    "--source-image",
                    str(source),
                    "--dest",
                    "assets/generated.png",
                    "--role",
                    "asset",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            copied = page_dir / "assets/generated.png"
            self.assertTrue(copied.exists())
            jobs = read_json(page_dir / "imagegen-jobs.json")
            self.assertEqual("recorded", jobs["jobs"][0]["status"])
            self.assertEqual("assets/generated.png", jobs["jobs"][0]["output"])


if __name__ == "__main__":
    unittest.main()
