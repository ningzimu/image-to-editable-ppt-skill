import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "skills/image-to-editable-ppt/cli/editppt/runtime"
SKILL_SCRIPT_DIR = ROOT / "skills/image-to-editable-ppt/scripts"
LEGACY_ENTRYPOINTS = {
    "prepare_inputs.py",
    "run_page_experiment.py",
    "crop_image_asset.py",
    "render_diff.py",
}
FORBIDDEN_IMAGE_BACKEND_PHRASES = {
    "$imagegen/SKILL.md",
    "skills/.system/imagegen/SKILL.md",
    "CODEX_HOME/skills/.system/imagegen",
    "built-in image_gen only",
    "imagegen-integration.md",
    "script-contracts.md",
    "imagegen-clean-base.md",
    "imagegen-asset-sheet.md",
    "imagegen-repair.md",
    "architecture.md",
    "state-machine.md",
    "subagent-contract.md",
    "repair-policy.md",
    "page-repair-worker.md",
    "image-backend-clean-base.md",
    "image-backend-asset-sheet.md",
    "image-backend-repair.md",
    "requirements.txt",
    "editppt image crop",
    "--crop-box",
    "source-derived-rasterization",
}
SCAN_ROOTS = [
    ROOT / "README.md",
    ROOT / "README_en.md",
    ROOT / "skills/image-to-editable-ppt/SKILL.md",
    ROOT / "skills/image-to-editable-ppt/references",
    ROOT / "skills/image-to-editable-ppt/prompts",
    RUNTIME_DIR,
]


class ScriptInventoryTest(unittest.TestCase):
    def test_legacy_entrypoints_are_not_present(self):
        present = sorted(name for name in LEGACY_ENTRYPOINTS if (RUNTIME_DIR / name).exists())
        self.assertEqual([], present)

    def test_skill_directory_contains_only_prompt_builder_script(self):
        present = []
        if SKILL_SCRIPT_DIR.exists():
            present = sorted(path.name for path in SKILL_SCRIPT_DIR.glob("*.py"))
        self.assertEqual(["build-page-worker-prompt.py"], present)

    def test_legacy_entrypoints_are_not_referenced(self):
        hits = []
        for root in SCAN_ROOTS:
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file() or path.suffix not in {".md", ".py", ".yaml"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for name in LEGACY_ENTRYPOINTS:
                    if name in text:
                        hits.append(f"{path.relative_to(ROOT)}: {name}")
        self.assertEqual([], hits)

    def test_external_imagegen_skill_is_not_required(self):
        hits = []
        for root in SCAN_ROOTS:
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file() or path.suffix not in {".md", ".py", ".yaml"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for phrase in FORBIDDEN_IMAGE_BACKEND_PHRASES:
                    if phrase in text:
                        hits.append(f"{path.relative_to(ROOT)}: {phrase}")
        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
