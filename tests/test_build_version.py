"""The release version reaches compiler defines without editing fallback sources."""

import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class BuildVersionTests(unittest.TestCase):
    def run_hook(self, version):
        class Environment:
            defines = None

            def __getitem__(self, key):
                return str(ROOT / "firmware")

            def subst(self, value):
                return temporary

            def Append(self, **kwargs):
                if "CPPDEFINES" in kwargs:
                    self.defines = kwargs["CPPDEFINES"]

        environment = Environment()
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"PANEL_RELEASE_VERSION": version}):
            runpy.run_path(
                str(ROOT / "firmware/release_version.py"), init_globals={"env": environment, "Import": lambda _: None}
            )
        return environment.defines

    def test_release_override_is_quoted_and_fallback_remains_available(self):
        self.assertIsNone(self.run_hook(""))
        self.assertEqual(self.run_hook("0.9.1"), [("PANEL_FIRMWARE_VERSION", '\\"0.9.1\\"')])
        self.assertEqual(self.run_hook("1.0.0-rc.1"), [("PANEL_FIRMWARE_VERSION", '\\"1.0.0-rc.1\\"')])

    def test_invalid_versions_cannot_inject_compiler_flags(self):
        for version in ['1.2.3" -DBAD', "1.2.3\nBAD=1", "01.2.3", "main", "1" * 32 + ".0.0"]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.run_hook(version)
