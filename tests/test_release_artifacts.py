"""Test artifact integrity, provenance gates and the pinned SerialX core boundary."""

import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tarfile
import tempfile
import tomllib
import types
import unittest
from pathlib import Path

import test_service as service_tests
from netlink_panel.ota import OTAError
from test_ota import image_fixture

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
spec = importlib.util.spec_from_file_location("release_artifacts", ROOT / "scripts/release_artifacts.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseArtifactTests(unittest.TestCase):
    def package(self, output, *, tag=None, version=VERSION, commit="1" * 40):
        firmware = output.parent / "firmware.bin"
        firmware.write_bytes(image_fixture(version=version))
        return release.package(ROOT, firmware, output, commit, tag)

    def test_deterministic_artifacts_manifest_and_checksums(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            manifest = self.package(first, tag=f"v{VERSION}")
            self.package(second, tag=f"v{VERSION}")
            for file in first.iterdir():
                self.assertEqual(file.read_bytes(), (second / file.name).read_bytes())
            for line in (first / "SHA256SUMS").read_text().splitlines():
                expected, name = line.split("  ")
                self.assertEqual(hashlib.sha256((first / name).read_bytes()).hexdigest(), expected)
            self.assertEqual(manifest["source"]["commit"], "1" * 40)
            self.assertEqual(manifest["firmware"]["version"], VERSION)
            self.assertEqual(manifest["signature"]["status"], "unsigned")
            self.assertEqual(manifest["compatibility"]["actions"], [])
            for name, item in manifest["artifacts"].items():
                self.assertEqual(item["sha256"], hashlib.sha256((first / name).read_bytes()).hexdigest())

    def test_mismatched_tag_image_version_commit_and_mixed_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            for kwargs in [{"tag": "v9.0.0"}, {"version": "0.7.0"}, {"commit": "main"}]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    self.package(output, **kwargs)
                self.assertFalse(output.exists())
            self.package(output)
            with self.assertRaisesRegex(ValueError, "empty"):
                self.package(output)

    def test_changed_consumer_contract_and_corrupt_image_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in [
                "release/protocol-core.json",
                "host/netlink_panel/protocol.py",
                "host/netlink_panel/service.py",
            ]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            protocol = root / "host/netlink_panel/protocol.py"
            protocol.write_bytes(protocol.read_bytes() + b"\n# incompatible core digest\n")
            with self.assertRaisesRegex(ValueError, "pinned webserver contract"):
                release.protocol_core(root, "1" * 40)
            firmware = root / "bad.bin"
            data = image_fixture(version=VERSION)
            firmware.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            with self.assertRaisesRegex(OTAError, "SHA-256"):
                release.package(ROOT, firmware, root / "out", "1" * 40)

    def test_core_has_exact_consumer_hashes_and_no_serial_or_daemon(self):
        data, manifest = release.protocol_core(ROOT, "1" * 40)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            self.assertEqual(set(archive.getnames()), {"UPSTREAM.json", "__init__.py", "protocol.py", "transport.py"})
            transport = archive.extractfile("transport.py").read()
            for forbidden in [b"import serial", b"def open_usb", b"def run(", b"def main("]:
                self.assertNotIn(forbidden, transport)
            for name, expected in manifest["consumer"]["generated_sha256"].items():
                self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(), expected)
            self.assertEqual(json.load(archive.extractfile("UPSTREAM.json"))["version"], "1.0.0")

    def test_packaged_core_communicates_with_actual_firmware_endpoint(self):
        # The webserver injects its own SerialX stream; the packaged core must
        # keep this transport boundary and actual firmware framing compatible.
        data, _ = release.protocol_core(ROOT, "1" * 40)
        package_name = "release_test_core"
        package = types.ModuleType(package_name)
        package.__path__ = []
        sys.modules[package_name] = package
        self.addCleanup(sys.modules.pop, package_name, None)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for name in ["protocol", "transport"]:
                module = types.ModuleType(f"{package_name}.{name}")
                module.__package__ = package_name
                sys.modules[module.__name__] = module
                self.addCleanup(sys.modules.pop, module.__name__, None)
                exec(compile(archive.extractfile(name + ".py").read(), name + ".py", "exec"), module.__dict__)
        service_tests.ServiceTests.setUpClass()
        try:
            import serial

            with (
                service_tests.NativePanel(service_tests.ServiceTests.binary) as panel,
                serial.Serial(panel.port, 115200, timeout=0.02) as stream,
            ):
                transport = sys.modules[package_name + ".transport"]
                session = transport.Session(stream, transport.Enrollment("panel-test", "TEST-SERIAL", "unverified"))
                self.assertIn("device.state.v1", session.handshake()["capabilities"])
                ack = session.request(
                    "device.state",
                    fields={
                        "revision": 1,
                        "valid_for_ms": 2000,
                        "desk": {"height_mm": 1086, "fresh": True},
                        "monitor": None,
                    },
                )
                self.assertEqual(ack["type"], "device.state.ack")
                self.assertEqual(session.snapshot()["state"]["mode"], "read_only")
                self.assertEqual(session.request("action.request")["stage"], "rejected")
        finally:
            service_tests.ServiceTests.doClassCleanups()
