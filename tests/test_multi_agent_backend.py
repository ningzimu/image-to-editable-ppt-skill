import json
import os
import subprocess
import sys
import tempfile as tempfile_module
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "editppt/runtime"


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
            "max_concurrent_pages": 4,
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
        self.assertIn("Agent-friendly CLI", result.stdout)
        self.assertIn("Typical workflow", result.stdout)
        self.assertIn("usage: editppt", result.stdout)
        for command in ("setup", "install", "uninstall", "update", "doctor", "config", "prepare", "run", "image"):
            self.assertIn(command, result.stdout)
        for old_command in ("process-asset-sheet", "record-image", "queue-repairs"):
            self.assertNotIn(old_command, result.stdout)

    def test_old_top_level_commands_are_removed(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "status", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid choice", result.stderr)

    def test_image_batch_help_uses_public_command_name(self):
        result = subprocess.run(
            [sys.executable, "-m", "editppt.cli", "image", "batch", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage: editppt image batch", result.stdout)
        self.assertNotIn("generate-batch", result.stdout)

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

    def test_install_and_update_dry_run_print_external_commands(self):
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "editppt.cli",
                "install",
                "--agent",
                "codex",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, install.returncode, install.stderr)
        self.assertIn("npx -y skills@latest add ningzimu/image-to-editable-ppt-skill", install.stdout)
        self.assertIn("--skill image-to-editable-ppt", install.stdout)
        self.assertIn("--agent codex", install.stdout)

        update = subprocess.run(
            [
                sys.executable,
                "-m",
                "editppt.cli",
                "update",
                "--cli-only",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, update.returncode, update.stderr)
        self.assertTrue("pipx upgrade image-to-editable-ppt" in update.stdout or "cli=editable" in update.stdout)

    def test_unified_cli_backend_defaults_to_built_in_image_gen(self):
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
            self.assertEqual("built-in-image-tool", backend["backend_id"])
            self.assertEqual("image_gen", backend["tool_name"])
            self.assertEqual("image_gen.imagegen", backend["tool_call"])
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
            self.assertEqual("built-in-image-tool", deck["image_backend"]["backend_id"])
            request = read_json(deck_path.parent / "pages/page_001/page_request.json")
            self.assertEqual(deck["image_backend"], request["image_backend"])

    def test_unified_cli_next_uses_platform_temp_dir_for_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            write_json(
                run_dir / "deck_manifest.json",
                {
                    "schema_version": 1,
                    "run_id": "run-test",
                    "image_backend": {"backend_id": "built-in-image-tool"},
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
            self.assertIn(str(Path(tempfile_module.gettempdir())), payload["next_command"])
            self.assertIn("editppt run prompt", payload["next_command"])

    def test_configure_image_backend_writes_deck_and_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "configure_image_backend.py",
                    run_dir,
                    "--backend-id",
                    "built-in-image-tool",
                    "--tool-name",
                    "image_gen",
                    "--model",
                    "built-in default",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            deck = read_json(run_dir / "deck_manifest.json")
            self.assertEqual("built-in-image-tool", deck["image_backend"]["backend_id"])
            request = read_json(run_dir / "pages/page_002/page_request.json")
            self.assertEqual(deck["image_backend"], request["image_backend"])

    def test_record_sample_page_marks_recorded_and_excludes_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = make_minimal_run(tmp)
            page_dir = run_dir / "pages/page_001"
            for name in (
                "manifest.json",
                "imagegen-jobs.json",
                "page.pptx",
                "preview.png",
                "split_assets_contact.png",
                "page_result.json",
            ):
                (page_dir / name).write_text("x", encoding="utf-8")
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
                    "qa_note": "sample accepted",
                    "known_limits": [],
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    RUNTIME_DIR / "record_sample_page.py",
                    run_dir,
                    "--page",
                    "page_001",
                    "--feedback",
                    "User approved page_001 as the sample.",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            jobs = read_json(run_dir / "page_jobs.json")
            page_1 = jobs["pages"][0]
            self.assertEqual("recorded", page_1["status"])
            self.assertTrue(page_1["sample_page_approved"])
            status = subprocess.run(
                [sys.executable, RUNTIME_DIR / "page_job_status.py", run_dir, "--json"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, status.returncode, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(["page_002"], payload["dispatchable_pages"])
            deck = read_json(run_dir / "deck_manifest.json")
            self.assertEqual(["User approved page_001 as the sample."], deck["user_requirements_and_feedback"])
            request_2 = read_json(run_dir / "pages/page_002/page_request.json")
            self.assertEqual(deck["user_requirements_and_feedback"], request_2["user_requirements_and_feedback"])

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
