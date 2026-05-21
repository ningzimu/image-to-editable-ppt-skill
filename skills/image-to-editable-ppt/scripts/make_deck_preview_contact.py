#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_job_dir(deck_manifest_path, manifest):
    job_dir = manifest.get("job_dir")
    if job_dir:
        return Path(job_dir).resolve()
    return deck_manifest_path.resolve().parent


def page_preview_path(job_dir, page):
    page_dir = job_dir / page["page_dir"]
    return page_dir / "preview.png"


def fit(image, max_width):
    if image.width <= max_width:
        return image.copy()
    ratio = max_width / image.width
    return image.resize((max_width, max(1, int(image.height * ratio))))


def draw_page_tile(source, label, width, label_height):
    image = fit(source.convert("RGB"), width)
    tile = Image.new("RGB", (width, image.height + label_height), "#f5f7fb")
    tile.paste(image, ((width - image.width) // 2, label_height))
    draw = ImageDraw.Draw(tile)
    draw.text((10, 9), label, fill="black")
    return tile


def build_contact_sheet(deck_manifest_path, out_path, columns, tile_width, gap, label_height):
    manifest = read_json(deck_manifest_path)
    job_dir = resolve_job_dir(deck_manifest_path, manifest)
    pages = sorted(manifest.get("pages", []), key=lambda page: int(page.get("page_index", 0)))
    if not pages:
        raise SystemExit("Deck manifest has no pages.")

    missing = []
    tiles = []
    for page in pages:
        page_index = int(page.get("page_index", len(tiles) + 1))
        preview_path = page_preview_path(job_dir, page)
        if not preview_path.exists():
            missing.append(preview_path)
            continue
        with Image.open(preview_path) as image:
            label = f"page {page_index:03d}"
            tiles.append(draw_page_tile(image, label, tile_width, label_height))

    if missing:
        missing_list = "\n".join(str(path) for path in missing)
        raise SystemExit(f"Missing page preview(s):\n{missing_list}")
    if not tiles:
        raise SystemExit("No page previews found.")

    if columns <= 0:
        columns = min(3, max(1, math.ceil(math.sqrt(len(tiles)))))
    rows = math.ceil(len(tiles) / columns)
    row_heights = []
    for row in range(rows):
        row_tiles = tiles[row * columns : (row + 1) * columns]
        row_heights.append(max(tile.height for tile in row_tiles))

    width = columns * tile_width + (columns + 1) * gap
    height = sum(row_heights) + (rows + 1) * gap
    canvas = Image.new("RGB", (width, height), "white")

    y = gap
    for row in range(rows):
        x = gap
        for tile in tiles[row * columns : (row + 1) * columns]:
            canvas.paste(tile, (x, y))
            x += tile_width + gap
        y += row_heights[row] + gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(out_path)


def main():
    parser = argparse.ArgumentParser(description="Combine per-page preview.png files into one deck-level contact sheet.")
    parser.add_argument("deck_manifest", help="Path to deck_manifest.json")
    parser.add_argument("--out", default="deck_preview_contact.png", help="Output path, relative to the job folder by default")
    parser.add_argument("--columns", type=int, default=0, help="Grid columns; 0 chooses a compact automatic layout")
    parser.add_argument("--tile-width", type=int, default=900)
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--label-height", type=int, default=32)
    args = parser.parse_args()

    deck_manifest_path = Path(args.deck_manifest).resolve()
    manifest = read_json(deck_manifest_path)
    job_dir = resolve_job_dir(deck_manifest_path, manifest)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = job_dir / out_path
    build_contact_sheet(deck_manifest_path, out_path, args.columns, args.tile_width, args.gap, args.label_height)


if __name__ == "__main__":
    main()
