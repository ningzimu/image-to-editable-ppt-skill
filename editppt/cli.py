from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def _skill_root() -> Path:
    env_root = os.environ.get("IMAGE_TO_EDITABLE_PPT_SKILL_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    package_root = Path(__file__).resolve().parent
    packaged_skill = package_root / "skill"
    if packaged_skill.exists():
        return packaged_skill

    source_skill = package_root.parent / "skills" / "image-to-editable-ppt"
    if source_skill.exists():
        return source_skill.resolve()

    raise RuntimeError(
        "Could not locate the image-to-editable-ppt skill directory. "
        "Set IMAGE_TO_EDITABLE_PPT_SKILL_ROOT to the installed skill path."
    )


def main() -> None:
    command_name = Path(sys.argv[0]).name or "editppt"
    if command_name in {"cli.py", "__main__.py"}:
        command_name = "editppt"
    skill_root = _skill_root()
    runtime_dir = Path(__file__).resolve().parent / "runtime"
    script = runtime_dir / "main.py"
    if not script.exists():
        raise RuntimeError(f"runtime entrypoint not found: {script}")

    os.environ.setdefault("IMAGE_TO_EDITABLE_PPT_CLI_PROG", command_name)
    os.environ.setdefault("IMAGE_TO_EDITABLE_PPT_SKILL_ROOT", str(skill_root))
    sys.path.insert(0, str(runtime_dir))
    sys.argv = [command_name, *sys.argv[1:]]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
