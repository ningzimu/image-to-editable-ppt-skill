#!/usr/bin/env python3
import argparse
from pathlib import Path

from _page_artifacts import write_pair


def main():
    parser = argparse.ArgumentParser(description="Create an origin/preview contact sheet for a page.")
    parser.add_argument("page_dir")
    parser.add_argument("--source", default="source.png")
    parser.add_argument("--preview", default="preview.png")
    parser.add_argument("--out", default="split_assets_contact.png")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    source = page_dir / args.source
    preview = page_dir / args.preview
    out = page_dir / args.out
    if not source.exists():
        raise SystemExit(f"Missing source image: {source}")
    if not preview.exists():
        raise SystemExit(f"Missing preview image: {preview}")
    write_pair(source, preview, out)


if __name__ == "__main__":
    main()
