import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

RUNTIME = Path(__file__).resolve().parents[1] / 'skills/image-to-editable-ppt/cli/editppt/runtime'
sys.path.insert(0, str(RUNTIME))
from split_alpha_components import region_components


class AlphaRegionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = Image.new('RGBA', (100, 60))
        draw = ImageDraw.Draw(self.image)
        draw.rectangle((10, 20, 25, 40), fill=(255, 0, 200, 180))
        draw.point((30, 10), fill=(0, 200, 0, 3))
        draw.rectangle((65, 20, 80, 40), fill=(30, 0, 255, 255))
        self.source = self.root / 'sheet.png'
        self.image.save(self.source)
        self.regions = self.root / 'regions.json'
        self.write_regions([{'name': 'first', 'box': [0, 0, 50, 60]},
                            {'name': 'second', 'box': [50, 0, 50, 60]}])

    def write_regions(self, regions):
        self.regions.write_text(json.dumps({'regions': regions}))

    def process(self, *extra):
        return subprocess.run([sys.executable, str(RUNTIME / 'process_asset_sheet.py'),
                               str(self.root), '--asset-sheet-source', str(self.source),
                               *extra], capture_output=True, text=True)

    def test_transparent_auto_and_explicit_preserve_exact_alpha(self):
        for options in ([], ['--skip-chroma']):
            with self.subTest(options=options):
                alpha = self.root / 'imagegen_asset_sheet_alpha.png'
                alpha.unlink(missing_ok=True)
                result = self.process('--regions', 'regions.json', *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Image.open(alpha).tobytes(), self.image.tobytes())
                self.assertFalse((self.root / 'imagegen_asset_sheet_chroma.png').exists())
                report = json.loads((self.root / 'split_assets.json').read_text())
                first = report['assets'][0]
                self.assertEqual(first['box'], [10, 10, 31, 41])
                self.assertEqual(first['region_box'], [0, 0, 50, 60])
                output = Image.open(first['path'])
                self.assertEqual(output.tobytes(), self.image.crop(first['padded_box']).tobytes())
                self.assertEqual(sum(output.getchannel('A').histogram()[1:]), 337)

    def test_existing_alpha_is_not_silently_replaced(self):
        alpha = self.root / 'imagegen_asset_sheet_alpha.png'
        alpha.write_bytes(b'existing')
        for options in ([], ['--skip-chroma']):
            result = self.process('--skip-split', *options)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(alpha.read_bytes(), b'existing')
        result = self.process('--skip-split', '--force-chroma')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Image.open(alpha).tobytes(), self.image.tobytes())

    def test_force_preserves_original_alpha_even_when_reprocessing_itself(self):
        result = self.process('--skip-split')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.source = self.root / 'imagegen_asset_sheet_alpha.png'
        result = self.process('--force-chroma', '--skip-split')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Image.open(self.source).tobytes(), self.image.tobytes())

    def test_invalid_regions_write_no_assets(self):
        self.write_regions([{'name': 'first', 'box': [0, 0, 50, 60]}])
        result = self.process('--regions', 'regions.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'assets/first.png').exists())
        self.assertFalse((self.root / 'split_assets.json').exists())

    def test_region_output_cannot_replace_input(self):
        self.write_regions([{'name': 'sheet', 'box': [0, 0, 50, 60]},
                            {'name': 'second', 'box': [50, 0, 50, 60]}])
        before = self.source.read_bytes()
        result = subprocess.run([sys.executable, str(RUNTIME / 'split_alpha_components.py'),
                                 '--input', str(self.source), '--out-dir', str(self.root),
                                 '--regions', str(self.regions)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overwrite the input', result.stderr)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse((self.root / 'second.png').exists())

    def test_explicit_alpha_rejects_opaque_and_empty(self):
        for opacity in (0, 255):
            Image.new('RGBA', (20, 20), (100, 100, 100, opacity)).save(self.source)
            result = self.process('--skip-chroma', '--skip-split')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / 'imagegen_asset_sheet_alpha.png').exists())

    def test_region_validation(self):
        valid = [{'name': 'a', 'box': [0, 0, 50, 60]}, {'name': 'b', 'box': [50, 0, 50, 60]}]
        cases = [
            ([valid[0]], 'uncovered'),
            ([valid[0], {'name': 'b', 'box': [45, 0, 55, 60]}], 'overlaps'),
            ([{'name': 'a', 'box': [10, 0, 40, 60]}, valid[1]], 'boundary'),
            ([{'name': 'a', 'box': [0, 0, 101, 60]}], 'outside'),
            ([{'name': 'a', 'box': [0, 0, 0, 60]}], 'nonpositive'),
            ([{'name': '../a', 'box': [0, 0, 50, 60]}], 'safe filename'),
            ([valid[0], {'name': 'A.PNG', 'box': [50, 0, 50, 60]}], 'unique'),
            ([{'name': 'a', 'box': [0, 0, 5, 5]}], 'no foreground'),
            ([{'name': 'a', 'box': [0.1, 0, 50, 60]}], 'integer'),
        ]
        for regions, message in cases:
            with self.subTest(message=message):
                self.write_regions(regions)
                with self.assertRaisesRegex(SystemExit, message):
                    region_components(self.image, self.regions)

    def test_legacy_merges_small_fragment_before_area_filter(self):
        image = Image.new('RGBA', (60, 50))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 19, 19), fill='red')
        draw.point((21, 12), fill='blue')
        image.save(self.source)
        result = subprocess.run([sys.executable, str(RUNTIME / 'split_alpha_components.py'),
                                 '--input', str(self.source), '--out-dir', str(self.root / 'out'),
                                 '--close-radius', '0', '--min-area', '101', '--merge-gap', '3',
                                 '--manifest', str(self.root / 'report.json')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        assets = json.loads((self.root / 'report.json').read_text())['assets']
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]['area'], 101)
        self.assertEqual(assets[0]['box'], [10, 10, 22, 20])

    def test_opaque_sheet_still_uses_chroma(self):
        image = Image.new('RGB', (60, 60), '#00ff00')
        ImageDraw.Draw(image).rectangle((20, 20, 40, 40), fill='red')
        image.save(self.source)
        result = self.process('--skip-split')
        self.assertEqual(result.returncode, 0, result.stderr)
        alpha = Image.open(self.root / 'imagegen_asset_sheet_alpha.png').getchannel('A')
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertGreater(alpha.getpixel((30, 30)), 0)


if __name__ == '__main__':
    unittest.main()
