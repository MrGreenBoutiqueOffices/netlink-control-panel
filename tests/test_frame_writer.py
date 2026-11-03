"""Exercise the firmware's actual ArduinoJson serializer with a counting sink."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class FrameWriterTests(unittest.TestCase):
    def test_json_response_is_one_bounded_write(self):
        root = Path(__file__).resolve().parents[1]
        compiler = shutil.which("c++")
        library = root / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"
        if compiler is None or not (library / "ArduinoJson.h").exists():
            self.skipTest("Build the firmware first to install its pinned ArduinoJson dependency")
        program = r"""#include "frame_writer.h"
#include <string>
#include <cstdio>
#include <cassert>
struct Sink {
  size_t calls = 0;
  std::string bytes;
  size_t write(uint8_t c) { calls++; bytes.push_back(c); return 1; }
  size_t write(const uint8_t *data, size_t size) { calls++; bytes.append(reinterpret_cast<const char *>(data), size); return size; }
};
int main() {
  StaticJsonDocument<2048> message;
  message["type"] = "hello";
  message["v"] = 1;
  message["panel_id"] = "panel-regression";
  message["firmware"] = "0.3.1";
  message["ota"]["state"] = "valid";
  char buffer[1025];
  Sink output;
  assert(writeJsonFrame(message, output, buffer, sizeof(buffer)));
  std::printf("bytes=%zu writes=%zu\n", output.bytes.size(), output.calls);
  std::fflush(stdout);
  if (output.calls != 1) return 2;
  assert(output.bytes.back() == '\n');
  StaticJsonDocument<2048> decoded;
  assert(!deserializeJson(decoded, output.bytes));
  assert(decoded["panel_id"] == "panel-regression");
  message["oversized"] = std::string(1100, 'x');
  Sink rejected;
  assert(!writeJsonFrame(message, rejected, buffer, sizeof(buffer)));
  assert(rejected.calls == 0);
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "frame.cpp"
            binary = Path(temporary) / "frame"
            source.write_text(program)
            subprocess.run(
                [
                    compiler,
                    "-std=c++11",
                    "-I",
                    str(root / "firmware/src"),
                    "-I",
                    str(library),
                    str(source),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
            )
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
