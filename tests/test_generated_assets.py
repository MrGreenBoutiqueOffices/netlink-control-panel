"""Lossless encoding differences are allowed; actual design drift is rejected."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate_demo_assets", ROOT / "scripts/generate_demo_assets.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class GeneratedAssetsTests(unittest.TestCase):
    def test_png_pixels_are_exact_but_lossless_encoding_can_differ(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.png", Path(temp) / "second.png"
            original = Image.new("RGB", (10, 10), (10, 20, 30))
            original.save(first, compress_level=0)
            original.save(second, compress_level=9)
            self.assertNotEqual(first.read_bytes(), second.read_bytes())
            self.assertTrue(generator.same_asset(first, second))
            original.putpixel((4, 4), (11, 20, 30))
            original.save(second)
            self.assertFalse(generator.same_asset(first, second))
            Image.new("RGB", (11, 10), (10, 20, 30)).save(second)
            self.assertFalse(generator.same_asset(first, second))

    def test_cpp_arrays_are_byte_exact_and_missing_files_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.cpp", Path(temp) / "second.cpp"
            first.write_text("pixels=1;\n")
            self.assertFalse(generator.same_asset(first, second))
            second.write_text(first.read_text())
            self.assertTrue(generator.same_asset(first, second))
            second.write_text("pixels=2;\n")
            self.assertFalse(generator.same_asset(first, second))
