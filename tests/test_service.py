"""Run the production host against the actual C++ firmware endpoint over a PTY."""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import tty
import unittest
from pathlib import Path
from types import SimpleNamespace

import serial
from netlink_panel.protocol import Decoder, ProtocolError, encode
from netlink_panel.service import (
    Enrollment,
    ServiceError,
    Session,
    atomic_json,
    candidates,
    ownership,
    publish,
    read_status,
    run,
)

PROGRAM = r"""
#include "production_protocol.h"
#include "frame_writer.h"
#include <cstdio>
#include <cassert>
#include <string>
struct Sink { size_t write(const uint8_t *p,size_t n) { return fwrite(p,1,n,stdout); } };
int main(int argc,char **argv) {
  ProductionSession session; char input[2048];unsigned now=0;
  while(fgets(input,sizeof(input),stdin)) {
    StaticJsonDocument<1536> in,out;
    if(deserializeJson(in,input) || in["v"] != 2)continue;
    if(in["type"] == "heartbeat") {
      if(!session.matches(in))continue;
      out["v"]=2;out["type"]="heartbeat";out["session"]=session.session;out["uptime_ms"]=++now;
    } else {
      session.handle(in,out,++now,"panel-test","0.6.0",argv[1],true,"valid");
      if(argc>2 && in["type"] == "hello") {
        if(std::string(argv[2])=="wrong_identity")out["panel_id"]="panel-stranger";
        if(std::string(argv[2])=="bad_version")out["protocol_min"]=3;
        if(std::string(argv[2])=="unhealthy")out["self_test_ok"]=false;
      }
      if(argc>2 && in["type"] == "state.get") {
        if(std::string(argv[2])=="duplicate_revision")out["revision"]=1;
        if(std::string(argv[2])=="fake_desk")out["state"]["desk"]["height_mm"]=740;
      }
    }
    char buffer[1025];Sink sink;assert(writeJsonFrame(out,sink,buffer,sizeof(buffer)));fflush(stdout);
  }
}
"""


class NativePanel:
    def __init__(self, binary, mode=None):
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.port = os.ttyname(self.slave)
        self.boot = os.urandom(8).hex()
        self.process = subprocess.Popen(
            [str(binary), self.boot, *([mode] if mode else [])],
            stdin=self.master,
            stdout=self.master,
            stderr=subprocess.PIPE,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.communicate(timeout=3)
        os.close(self.master)
        os.close(self.slave)


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        library = root / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"
        if not shutil.which("c++") or not (library / "ArduinoJson.h").exists():
            raise unittest.SkipTest("Build firmware first for the pinned ArduinoJson dependency")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        source = Path(cls.temp.name) / "endpoint.cpp"
        source.write_text(PROGRAM)
        cls.binary = source.with_suffix("")
        subprocess.run(
            [
                "c++",
                "-std=c++11",
                "-I",
                str(root / "firmware/src"),
                "-I",
                str(library),
                str(source),
                "-o",
                str(cls.binary),
            ],
            check=True,
            capture_output=True,
        )

    def setUp(self):
        self.enrollment = Enrollment("panel-test", "TEST-SERIAL", "unverified")

    def session(self, panel):
        device = serial.Serial(panel.port, 115200, timeout=0.02, write_timeout=1)
        self.addCleanup(device.close)
        return Session(device, self.enrollment)

    def test_real_firmware_handshake_snapshot_and_no_actuation(self):
        with NativePanel(self.binary) as panel:
            session = self.session(panel)
            hello = session.handshake()
            self.assertEqual(hello["firmware"], "0.6.0")
            self.assertEqual(hello["boot_id"], panel.boot)
            first, second = session.snapshot(), session.snapshot()
            self.assertEqual((first["revision"], second["revision"]), (1, 2))
            self.assertIsNone(second["state"]["desk"])
            result = session.request("action.request")
            self.assertEqual(result["stage"], "rejected")
            self.assertEqual(result["code"], "unsupported_action")
            with self.assertRaisesRegex(ServiceError, "peer_rejected_request"):
                session.request("demo_ui")

    def test_wrong_identity_incompatible_and_unhealthy_are_rejected(self):
        for mode, reason in (
            ("wrong_identity", "panel_identity"),
            ("bad_version", "incompatible"),
            ("unhealthy", "healthy"),
        ):
            with self.subTest(mode=mode), NativePanel(self.binary, mode) as panel:
                with self.assertRaisesRegex(ServiceError, reason):
                    self.session(panel).handshake()

    def test_duplicate_revision_and_fake_device_state_are_rejected(self):
        for mode in ("duplicate_revision", "fake_desk"):
            with self.subTest(mode=mode), NativePanel(self.binary, mode) as panel:
                session = self.session(panel)
                session.handshake()
                if mode == "duplicate_revision":
                    session.snapshot()
                with self.assertRaisesRegex(ServiceError, "invalid_state_revision|unexpected_device_state"):
                    session.snapshot()

    def test_deadline_and_old_session_cannot_satisfy_response(self):
        class WrongSession:
            def write(self, data):
                return len(data)

            def read(self, _):
                time.sleep(0.005)
                return encode({"type": "hello", "id": 1, "session": "0" * 32}, version=2)

        session = Session(WrongSession(), self.enrollment)
        with self.assertRaisesRegex(ServiceError, "handshake_timeout"):
            session.request("hello", timeout=0.05, handshake=True)

    def test_reenumeration_uses_fresh_session_and_full_snapshot(self):
        with (
            NativePanel(self.binary) as first,
            NativePanel(self.binary) as second,
            tempfile.TemporaryDirectory() as temp,
        ):
            current = [first]
            opened = []
            stop = threading.Event()
            status = Path(temp) / "status.json"

            def ports():
                return [SimpleNamespace(vid=0x303A, pid=0x1001, serial_number="TEST-SERIAL", device=current[0].port)]

            def opener(port):
                opened.append(port)
                return serial.Serial(port, 115200, timeout=0.02, write_timeout=0.2)

            thread = threading.Thread(
                target=run, args=(self.enrollment, status, stop), kwargs={"ports": ports, "opener": opener}, daemon=True
            )
            thread.start()
            try:
                self.wait_status(status, lambda s: s["status"] == "connected" and s["panel"]["boot_id"] == first.boot)
                current[0] = second
                first.process.terminate()
                first.process.wait(timeout=2)
                result = self.wait_status(
                    status, lambda s: s["status"] == "connected" and s["panel"]["boot_id"] == second.boot
                )
                self.assertEqual(result["snapshot"]["revision"], 1)
                self.assertEqual(opened[:2], [first.port, second.port])
            finally:
                stop.set()
                thread.join(timeout=4)
                self.assertFalse(thread.is_alive())
            self.assertEqual(json.loads(status.read_text())["status"], "stopped")

    def wait_status(self, path, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if path.exists():
                value = json.loads(path.read_text())
                if predicate(value):
                    return value
            time.sleep(0.02)
        self.fail("Service did not publish expected status")

    def test_discovery_pins_full_usb_identity_and_rejects_duplicates(self):
        right = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number="TEST-SERIAL", device="changed-port")
        wrong = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number="OTHER", device="old-port")
        self.assertEqual(candidates(self.enrollment, [wrong, right]), [right])
        self.assertEqual(candidates(self.enrollment, [wrong]), [])
        with self.assertRaisesRegex(ServiceError, "ambiguous"):
            candidates(self.enrollment, [right, right])

    def test_enrollment_lock_atomic_state_and_disconnect_clears_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "enrollment.json"
            with ownership(path):
                with self.assertRaisesRegex(ServiceError, "already_running"):
                    with ownership(path):
                        pass
            from dataclasses import asdict

            atomic_json(path, asdict(self.enrollment))
            self.assertEqual(Enrollment.load(path), self.enrollment)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            publish(path, "stale", reason="usb_io_error")
            result = json.loads(path.read_text())
            self.assertIsNone(result["snapshot"])
            self.assertIsNone(result["panel"])

    def test_status_after_service_crash_expires_without_running_daemon(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "status.json"
            publish(path, "connected", hello={"firmware": "0.6.0"}, snapshot={"valid_for_ms": 3500})
            observed = json.loads(path.read_text())["observed_at_unix_ms"] / 1000
            self.assertEqual(read_status(path, clock=lambda: observed + 1)["status"], "connected")
            for now in (observed + 4, observed - 1):
                stale = read_status(path, clock=lambda: now)
                self.assertEqual(stale["status"], "stale")
                self.assertIsNone(stale["snapshot"])

    def test_invalid_cached_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "status.json"
            for content in ("not json", "[]", '{"schema":1,"status":"connected","snapshot":null}'):
                path.write_text(content)
                with self.assertRaisesRegex(ServiceError, "invalid_cached_status"):
                    read_status(path)

    def test_invalid_hello_and_old_session_do_not_change_firmware_session(self):
        with NativePanel(self.binary) as panel:
            session = self.session(panel)
            session.handshake()
            self.assertEqual(session.snapshot()["revision"], 1)
            session.sequence += 1
            session.send("hello", id=session.sequence, protocol_min=3, protocol_max=3)
            # Read the explicit incompatibility response without creating a new Session.
            deadline = time.monotonic() + 1
            messages = []
            while not messages and time.monotonic() < deadline:
                messages = session.decoder.feed(session.device.read(4096))
            self.assertEqual(messages[-1]["code"], "incompatible_protocol")
            self.assertEqual(session.snapshot()["revision"], 2)
            session.device.write(encode({"type": "state.get", "id": 99, "session": "f" * 32}, version=2))
            # An old session cannot consume a state revision or complete the current request.
            self.assertEqual(session.snapshot()["revision"], 3)

    def test_protocol_v1_and_v2_are_isolated_and_oversize_recovers(self):
        legacy = encode({"type": "hello", "id": 1})
        production = encode({"type": "hello", "id": 1}, version=2)
        self.assertEqual(Decoder().feed(production), [])
        decoder = Decoder(version=2)
        self.assertEqual(decoder.feed(legacy), [])
        self.assertEqual(decoder.feed(b"x" * 1025 + b"\n" + production)[0]["v"], 2)
        with self.assertRaises(ProtocolError):
            encode({"type": "hello", "id": True}, version=2)


if __name__ == "__main__":
    unittest.main()
