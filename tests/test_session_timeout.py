"""Compile the exact session policy used by the firmware loop."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class SessionTimeoutTests(unittest.TestCase):
    def test_ota_uses_its_transfer_budget_without_weakening_control_timeout(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        program = r"""#include "session_timeout.h"
#include <cstdio>
int main() {
  if (sessionExpired(false, 3500) || !sessionExpired(false, 3501)) return 1;
  if (sessionExpired(true, 10000)) {
    std::puts("OTA link expires before the configured 15-second transfer deadline");
    return 2;
  }
  if (sessionExpired(true, 15000) || !sessionExpired(true, 15001)) return 3;
  if (!sessionExpired(false, 10000)) return 4;
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "timeout.cpp"
            binary = Path(temporary) / "timeout"
            source.write_text(program)
            subprocess.run(
                [compiler, "-std=c++11", "-I", str(root / "firmware/src"), str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
            )
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
