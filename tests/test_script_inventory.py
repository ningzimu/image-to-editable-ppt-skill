import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills/image-to-editable-ppt/scripts"
LEGACY_ENTRYPOINTS = {
    "prepare_inputs.py",
    "run_page_experiment.py",
    "crop_image_asset.py",
    "render_diff.py",
}
SCAN_ROOTS = [
    ROOT / "README.md",
    ROOT / "README_en.md",
    ROOT / "skills/image-to-editable-ppt/SKILL.md",
    ROOT / "skills/image-to-editable-ppt/references",
    ROOT / "skills/image-to-editable-ppt/prompts",
    SCRIPT_DIR,
]


class ScriptInventoryTest(unittest.TestCase):
    def test_legacy_entrypoints_are_not_present(self):
        present = sorted(name for name in LEGACY_ENTRYPOINTS if (SCRIPT_DIR / name).exists())
        self.assertEqual([], present)

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


if __name__ == "__main__":
    unittest.main()
