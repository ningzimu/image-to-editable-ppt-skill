#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def skill_root():
    return Path(__file__).resolve().parents[1]


def runtime_home():
    return Path(os.getenv("IMAGE_TO_EDITABLE_PPT_HOME", skill_root())).expanduser()


def venv_python(home=None):
    home = home or runtime_home()
    if os.name == "nt":
        return home / ".venv" / "Scripts" / "python.exe"
    return home / ".venv" / "bin" / "python"


def requirements_path():
    return skill_root() / "requirements.txt"


def bootstrap(_args):
    home = runtime_home()
    env_dir = home / ".venv"
    python = venv_python(home)
    if not python.exists():
        print(f"Creating virtual environment: {env_dir}")
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)
    else:
        print(f"Virtual environment already exists: {env_dir}")
    requirements = requirements_path()
    if not requirements.exists():
        raise SystemExit(f"requirements.txt not found: {requirements}")
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    print(f"runtime home: {home}")
    print(f"runtime python: {python}")
    return 0


def check_import(python, module):
    result = subprocess.run(
        [str(python), "-c", f"import {module}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0, result.stderr.strip()


def doctor(_args):
    home = runtime_home()
    python = venv_python(home)
    ok = True
    print(f"skill root: {skill_root()}")
    print(f"runtime home: {home}")
    print(f"runtime python: {python} ({'exists' if python.exists() else 'missing'})")
    if not python.exists():
        ok = False
        print("venv: missing; run bootstrap")
    else:
        for module in ("fitz", "PIL"):
            module_ok, stderr = check_import(python, module)
            print(f"python import {module}: {'ok' if module_ok else 'missing'}")
            if not module_ok:
                ok = False
                if stderr:
                    print(stderr)
    magick = shutil.which("magick") or shutil.which("convert")
    print(f"ImageMagick: {magick or 'missing'}")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    print(f"LibreOffice/soffice: {soffice or 'missing'} (optional; only needed for legacy .ppt conversion)")
    return 0 if ok else 1


def print_python(_args):
    print(venv_python())
    return 0


def main():
    parser = argparse.ArgumentParser(description="Manage the image-to-editable-ppt local runtime")
    sub = parser.add_subparsers(required=True)
    boot = sub.add_parser("bootstrap", help="Create the local .venv and install dependencies")
    boot.set_defaults(func=bootstrap)
    doc = sub.add_parser("doctor", help="Check Python and system dependencies")
    doc.set_defaults(func=doctor)
    py = sub.add_parser("python", help="Print the runtime Python path")
    py.set_defaults(func=print_python)
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
