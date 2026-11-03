"""Compile the actual firmware arbitration policy on the host."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class FirmwarePolicyTests(unittest.TestCase):
    def test_actual_ota_guard_rejects_partial_duplicate_gap_and_overflow(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler not available")
        firmware = Path(__file__).resolve().parents[1] / "firmware/src"
        program = """#include "ota_policy.h"
#include <cassert>
int main() {
  TransferGuard guard;
  assert(!guard.begin(1, 3145728));
  assert(!guard.begin(3145729, 3145728));
  assert(guard.begin(1025, 3145728));
  assert(!guard.complete());
  assert(!guard.begin(1025, 3145728));
  assert(!guard.accepts(1, 512));
  assert(!guard.accepts(0, 513));
  assert(!guard.accepts(0, 0));
  assert(guard.accepts(0, 512)); guard.advance(512);
  assert(!guard.accepts(0, 512));
  assert(!guard.complete());
  assert(guard.accepts(512, 512)); guard.advance(512);
  assert(!guard.accepts(1024, 2));
  assert(guard.accepts(1024, 1)); guard.advance(1);
  assert(guard.complete());
  assert(!guard.accepts(1025, 1));
  guard.reset();
  assert(!guard.complete());
  assert(!guard.accepts(0, 512));
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "ota_policy.cpp"
            binary = Path(temporary) / "ota_policy"
            source.write_text(program)
            subprocess.run(
                [compiler, "-std=c++11", "-I", str(firmware), str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
            )
            subprocess.run([str(binary)], check=True)

    def test_usb_preempts_wifi_but_wifi_cannot_take_usb(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler not available")
        firmware = Path(__file__).resolve().parents[1] / "firmware/src"
        program = """#include "session_policy.h"
static_assert(canHandshake(Transport::None, Transport::USB), "USB starts");
static_assert(canHandshake(Transport::None, Transport::Wifi), "Wi-Fi starts");
static_assert(canHandshake(Transport::Wifi, Transport::USB), "USB preempts");
static_assert(!canHandshake(Transport::USB, Transport::Wifi), "Wi-Fi cannot preempt");
static_assert(!canHandshake(Transport::None, Transport::None), "No null session");
int main() { return 0; }
"""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "policy.cpp"
            binary = Path(temporary) / "policy"
            source.write_text(program)
            subprocess.run(
                [compiler, "-std=c++11", "-I", str(firmware), str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
            )
            subprocess.run([str(binary)], check=True)
