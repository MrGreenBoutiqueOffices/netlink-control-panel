"""USB panel supervisor. Enrollment/status only; no MQTT or device actuation."""

import argparse
import contextlib
import fcntl
import json
import os
import re
import secrets
import signal
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import serial
from serial.tools.list_ports import comports

from .protocol import Decoder, ProtocolError, encode

VERSION = 2
PROFILE = "lilygo-s3-long-cst3530"
VID, PID = 0x303A, 0x1001
TIMEOUT = 3.5


class ServiceError(RuntimeError):
    pass


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def bounded_text(value, limit=64):
    return isinstance(value, str) and bool(value) and len(value) <= limit and value.isascii() and value.isprintable()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".panel-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(data, output, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def ownership(path):
    """One enrolling/running process per installation; lock survives atomic writes."""
    path = Path(str(path) + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ServiceError("service_already_running") from error
        yield


@dataclass(frozen=True)
class Enrollment:
    panel_id: str
    usb_serial: str
    board_revision: str
    board_profile: str = PROFILE
    vid: int = VID
    pid: int = PID
    schema: int = 1

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.panel_id):
            raise ValueError("Invalid panel identity")
        if not bounded_text(self.usb_serial) or not bounded_text(self.board_revision):
            raise ValueError("Invalid USB serial or board revision")
        if (
            self.board_profile != PROFILE
            or self.vid != VID
            or self.pid != PID
            or type(self.schema) is not int
            or self.schema != 1
        ):
            raise ValueError("Unsupported enrollment")

    @classmethod
    def load(cls, path):
        try:
            return cls(**json.loads(Path(path).read_text()))
        except (ValueError, TypeError) as error:
            raise ServiceError("invalid_enrollment") from error

    def matches(self, port):
        return port.vid == self.vid and port.pid == self.pid and port.serial_number == self.usb_serial


def candidates(enrollment, ports):
    result = [port for port in ports if enrollment.matches(port)]
    # Duplicate identities are ambiguous; do not choose the first one.
    if len(result) > 1:
        raise ServiceError("ambiguous_usb_identity")
    return result


class Session:
    """Bounded request/response session. Outstanding requests die with this object."""

    def __init__(self, device, enrollment, *, clock=time.monotonic, stop=None):
        self.device, self.enrollment, self.clock = device, enrollment, clock
        self.stop = stop or threading.Event()
        self.decoder = Decoder(version=VERSION)
        self.token = secrets.token_hex(16)
        self.sequence = 0
        self.revision = 0
        self.last_peer = self.next_heartbeat = clock()
        self.ready = False
        self.hello = None

    def send(self, kind, **fields):
        message = {"type": kind, "session": self.token, **fields}
        frame = encode(message, version=VERSION)
        if self.device.write(frame) != len(frame):
            raise ServiceError("short_usb_write")

    def request(self, kind, *, timeout=TIMEOUT, handshake=False):
        self.sequence += 1
        request_id = self.sequence
        fields = {"protocol_min": VERSION, "protocol_max": VERSION} if handshake else {}
        started = self.clock()
        self.request_started = started
        self.send(kind, id=request_id, **fields)
        retry = started + 1
        while not self.stop.is_set():
            now = self.clock()
            if now - started >= timeout or (self.ready and now - self.last_peer > TIMEOUT):
                raise ServiceError("handshake_timeout" if handshake else "state_timeout")
            if handshake and now >= retry:
                self.send(kind, id=request_id, **fields)
                retry = now + 1
            if self.ready and now >= self.next_heartbeat:
                self.send("heartbeat")
                self.next_heartbeat = now + 1
            data = self.device.read(4096)
            if self.clock() - started >= timeout:
                raise ServiceError("handshake_timeout" if handshake else "state_timeout")
            for message in self.decoder.feed(data):
                if message.get("session") != self.token:
                    continue
                if message.get("type") == "error" and message.get("id") == request_id:
                    # Do not persist an arbitrary peer-supplied error string.
                    raise ServiceError("peer_rejected_request")
                if self.ready and message["type"] == "heartbeat" and integer(message.get("uptime_ms"), 0, 2**32 - 1):
                    self.last_peer = self.clock()
                if message.get("id") == request_id:
                    return message
        raise ServiceError("stopped")

    def handshake(self):
        message = self.request("hello", timeout=8, handshake=True)
        e = self.enrollment
        if message["type"] != "hello" or message.get("panel_id") != e.panel_id:
            raise ServiceError("panel_identity_mismatch")
        if message.get("board_profile") != e.board_profile or message.get("board_revision") != e.board_revision:
            raise ServiceError("board_mismatch")
        low, high = message.get("protocol_min"), message.get("protocol_max")
        if not integer(low, 1, VERSION) or not integer(high, VERSION, 2**15) or low > high:
            raise ServiceError("incompatible_protocol")
        if (
            not bounded_text(message.get("firmware"), 31)
            or not isinstance(message.get("boot_id"), str)
            or not re.fullmatch(r"[0-9a-f]{16}", message["boot_id"])
        ):
            raise ServiceError("invalid_handshake")
        if message.get("boot_state") != "valid" or message.get("self_test_ok") is not True:
            raise ServiceError("panel_not_healthy")
        caps = message.get("capabilities")
        if (
            not isinstance(caps, list)
            or len(caps) > 16
            or any(not bounded_text(c) for c in caps)
            or "panel.status.v1" not in caps
        ):
            raise ServiceError("unsupported_capabilities")
        if message.get("actions") != []:
            # The initial host has no action adapter and must not pretend otherwise.
            raise ServiceError("unsupported_actions")
        self.hello = {
            k: message[k]
            for k in (
                "panel_id",
                "board_profile",
                "board_revision",
                "firmware",
                "boot_id",
                "boot_state",
                "capabilities",
            )
        }
        self.ready = True
        self.last_peer = self.clock()
        return self.hello

    def snapshot(self):
        message = self.request("state.get")
        state = message.get("state")
        if message["type"] != "state.snapshot" or not integer(message.get("revision"), self.revision + 1, 2**32 - 1):
            raise ServiceError("invalid_state_revision")
        if not integer(message.get("sampled_uptime_ms"), 0, 2**32 - 1) or not integer(
            message.get("valid_for_ms"), 1, 3500
        ):
            raise ServiceError("invalid_state_freshness")
        if (
            not isinstance(state, dict)
            or state.get("self_test_ok") is not True
            or state.get("mode") != "standalone_demo"
        ):
            raise ServiceError("invalid_panel_state")
        if state.get("desk", False) is not None or state.get("monitor", False) is not None:
            raise ServiceError("unexpected_device_state")
        remaining = message["valid_for_ms"] - int((self.clock() - self.request_started) * 1000)
        if remaining <= 0:
            raise ServiceError("expired_snapshot")
        self.revision = message["revision"]
        self.last_peer = self.clock()
        return {
            "revision": self.revision,
            "sampled_uptime_ms": message["sampled_uptime_ms"],
            "valid_for_ms": remaining,
            "state": {"self_test_ok": True, "mode": "standalone_demo", "desk": None, "monitor": None},
        }


def open_usb(port):
    return serial.Serial(port, 115200, timeout=0.1, write_timeout=1, exclusive=True)


def publish(path, status, *, reason=None, hello=None, snapshot=None):
    # Offline states never carry a usable last snapshot or stale movement target.
    atomic_json(
        path,
        {
            "schema": 1,
            "status": status,
            "reason": reason,
            "transport": "usb",
            "observed_at_unix_ms": int(time.time() * 1000),
            "panel": hello,
            "snapshot": snapshot,
        },
    )


def read_status(path, *, clock=time.time):
    try:
        value = json.loads(Path(path).read_text())
        if (
            not isinstance(value, dict)
            or value.get("schema") != 1
            or value.get("status") not in ("connected", "waiting", "stale", "stopped")
        ):
            raise ValueError("Invalid cached status")
        if value["status"] == "connected":
            if (
                not integer(value.get("observed_at_unix_ms"), 0, 2**63 - 1)
                or not isinstance(value.get("snapshot"), dict)
                or not integer(value["snapshot"].get("valid_for_ms"), 1, 3500)
            ):
                raise ValueError("Invalid cached freshness")
            age = clock() * 1000 - value["observed_at_unix_ms"]
            if age < 0 or age > value["snapshot"]["valid_for_ms"]:
                value.update(status="stale", reason="status_expired", panel=None, snapshot=None)
        return value
    except (ValueError, TypeError) as error:
        raise ServiceError("invalid_cached_status") from error


def run(enrollment, status, stop, *, ports=comports, opener=open_usb):
    retry = 1
    while not stop.is_set():
        publish(status, "waiting")
        try:
            found = candidates(enrollment, ports())
            if not found:
                stop.wait(retry)
                retry = min(15, retry * 2)
                continue
            with opener(found[0].device) as device:
                session = Session(device, enrollment, stop=stop)
                hello = session.handshake()
                while not stop.is_set():
                    snapshot = session.snapshot()
                    publish(status, "connected", hello=hello, snapshot=snapshot)
                    retry = 1
                    # Device sends heartbeats while idle; request() drains them next pass.
                    stop.wait(min(1, snapshot["valid_for_ms"] / 2000))
        except (ServiceError, ProtocolError, OSError, serial.SerialException) as error:
            reason = str(error) if isinstance(error, ServiceError) else "usb_io_error"
            publish(status, "stale", reason=reason)
            stop.wait(retry)
            retry = min(15, retry * 2)
    publish(status, "stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollment", type=Path, default=Path("/data/enrollment.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    enroll = commands.add_parser("enroll", help="Explicitly enroll an identified USB panel; never overwrite")
    for name in ("port", "panel-id", "usb-serial", "board-revision"):
        enroll.add_argument("--" + name, required=True)
    serve = commands.add_parser("run", help="Supervise the enrolled panel without actuating hardware")
    serve.add_argument("--status", type=Path, default=Path("/data/status.json"))
    status = commands.add_parser("status", help="Read cached status; expired snapshots are never reported connected")
    status.add_argument("--status", type=Path, default=Path("/data/status.json"))
    args = parser.parse_args()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        if args.command == "status":
            value = read_status(args.status)
            print(json.dumps(value), flush=True)
            return 0 if value["status"] == "connected" else 1
        with ownership(args.enrollment):
            if args.command == "enroll":
                if args.enrollment.exists():
                    raise ServiceError("already_enrolled")
                enrollment = Enrollment(args.panel_id, args.usb_serial, args.board_revision)
                found = candidates(enrollment, comports())
                if len(found) != 1 or found[0].device != args.port:
                    raise ServiceError("usb_identity_mismatch")
                with open_usb(args.port) as device:
                    Session(device, enrollment, stop=stop).handshake()
                atomic_json(args.enrollment, asdict(enrollment))
                print(json.dumps({"event": "enrolled", "panel_id": enrollment.panel_id}), flush=True)
            else:
                enrollment = Enrollment.load(args.enrollment)
                run(enrollment, args.status, stop)
        return 0
    except (ServiceError, OSError, ValueError, serial.SerialException) as error:
        # Do not echo filesystem paths or peer data into runtime logs.
        reason = str(error) if isinstance(error, ServiceError) else "configuration_or_io_error"
        print(json.dumps({"event": "service_failed", "reason": reason}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
