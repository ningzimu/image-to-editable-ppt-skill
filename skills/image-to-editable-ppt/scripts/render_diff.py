#!/usr/bin/env python3
import argparse
from pathlib import Path


def write_comparison(expected, actual, diff, out_path):
    from PIL import Image, ImageDraw

    label_h = 44
    gap = 24
    width, height = expected.size
    canvas = Image.new("RGB", (width * 3 + gap * 2, height + label_h), "#f5f7fb")
    canvas.paste(expected, (0, label_h))
    canvas.paste(actual, (width + gap, label_h))
    canvas.paste(diff, ((width + gap) * 2, label_h))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 12), "source", fill="black")
    draw.text((width + gap + 12, 12), "rebuilt preview", fill="black")
    draw.text(((width + gap) * 2 + 12, 12), "pixel diff", fill="black")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main():
    parser = argparse.ArgumentParser(description="Render a simple pixel diff between two images.")
    parser.add_argument("--expected", required=True, help="Reference/source image.")
    parser.add_argument("--actual", required=True, help="Preview or renderer screenshot.")
    parser.add_argument("--out", required=True, help="Diff image path.")
    parser.add_argument("--report", help="Optional JSON report path.")
    parser.add_argument("--comparison", help="Optional side-by-side source/actual/diff QA image path.")
    args = parser.parse_args()

    try:
        from PIL import Image, ImageChops, ImageStat
    except Exception as exc:
        raise SystemExit(f"Pillow is required for image diff: {exc}")

    expected = Image.open(args.expected).convert("RGB")
    actual = Image.open(args.actual).convert("RGB")
    if actual.size != expected.size:
        actual = actual.resize(expected.size)

    diff = ImageChops.difference(expected, actual)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    diff.save(args.out)
    if args.comparison:
        write_comparison(expected, actual, diff, args.comparison)

    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / len(stat.mean)
    rms = (sum(value * value for value in stat.rms) / len(stat.rms)) ** 0.5
    report = {
        "expected": str(Path(args.expected).resolve()),
        "actual": str(Path(args.actual).resolve()),
        "diff": str(Path(args.out).resolve()),
        "comparison": str(Path(args.comparison).resolve()) if args.comparison else None,
        "size": list(expected.size),
        "mae": mae,
        "rms": rms,
    }
    if args.report:
        import json

        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    if args.comparison:
        print(f"Wrote {args.comparison}")
    print(f"mae={mae:.4f} rms={rms:.4f}")


if __name__ == "__main__":
    main()
