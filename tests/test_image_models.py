import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/image-to-editable-ppt/cli"))
from editppt.runtime import image_gen, runtime_env


class ImageModelTests(unittest.TestCase):
    def test_default_and_explicit_configuration(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(image_gen._default_model(), "gpt-image-2.5-sunburst")
            self.assertEqual(runtime_env.DEFAULT_IMAGE_MODEL, image_gen._default_model())
        with mock.patch.dict(os.environ, {"IMAGE_TO_EDITABLE_PPT_IMAGE_MODEL": "gpt-image-2"}):
            self.assertEqual(image_gen._default_model(), "gpt-image-2")

    def test_quality_and_size_for_both_models_and_snapshots(self):
        for name in ("flare", "sunburst"):
            for prefix in ("", "openai/"):
                for suffix in ("", "-2026-09-08"):
                    model = f"{prefix}gpt-image-2.5-{name}{suffix}"
                    with self.subTest(model=model):
                        for quality in ("auto", "high", "xhigh", "max"):
                            image_gen._validate_quality(quality, model)
                        image_gen._validate_size("2560x1440", model)
                        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                            image_gen._validate_size("2561x1440", model)

    def test_new_quality_rejected_for_legacy_and_lookalike_models(self):
        for model in ("gpt-image-1.5", "gpt-image-2", "gpt-image-2-2026-04-21",
                      "gpt-image-2.5", "gpt-image-2.5-flare-invalid", "gpt-image-20"):
            for quality in ("xhigh", "max"):
                with self.subTest(model=model, quality=quality):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        image_gen._validate_quality(quality, model)
            image_gen._validate_quality("high", model)

    def test_oauth_body_preserves_requested_model_and_quality(self):
        for model in (image_gen.DEFAULT_MODEL, "gpt-image-2.5-flare"):
            body = image_gen._codex_image_body(
                prompt="test", image_paths=[], mask_path=None,
                model=model, size="auto", quality="xhigh",
            )
            self.assertEqual(body["model"], model)
            self.assertEqual(body["quality"], "xhigh")
        self.assertEqual(image_gen.DEFAULT_QUALITY, "auto")

    def test_dry_run_preserves_model_and_quality_for_generate_and_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            Image.new("RGB", (16, 16)).save(source)
            self._check_dry_runs(source)

    def _check_dry_runs(self, source):
        for operation in ("generate", "edit"):
            argv = ["editppt image", operation, "--prompt", "test", "--model",
                    "gpt-image-2.5-flare", "--quality", "max", "--dry-run"]
            if operation == "edit":
                argv += ["--image", str(source)]
            output = io.StringIO()
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(image_gen, "_load_runtime_env"), \
                 mock.patch.object(image_gen, "_codex_available", return_value=False), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(image_gen.main(), 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["model"], "gpt-image-2.5-flare")
            self.assertEqual(payload["quality"], "max")


if __name__ == "__main__":
    unittest.main()
