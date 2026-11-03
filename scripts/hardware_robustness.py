"""Physical panel checks. OTA fault injection requires an explicit candidate image."""

import argparse
import base64
import json
import socket
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from netlink_panel.cli import bench
from netlink_panel.ota import Peer, inspect_image, upload
from netlink_panel.protocol import Decoder, encode
from netlink_panel.wifi import TLSStream, load_pairing, psk_context


class Harness:
    def __init__(self, pairing, report_file):
        self.pairing = load_pairing(pairing)
        self.context = psk_context(self.pairing["panel_id"], self.pairing["key"], server=True)
        self.report_file = report_file
        self.results = []
        self.open_listener()

    def open_listener(self):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.pairing["host"], self.pairing["port"]))
        self.listener.listen(1)
        self.listener.settimeout(0.5)

    def server_outage(self, expected_hash, seconds=5):
        self.listener.close()
        time.sleep(seconds)
        self.open_listener()
        connection, peer, hello, latency = self.connect(timeout=30)
        with connection:
            peer.request("demo_state", height_mm=740, brightness=60)
            if hello["ota"]["image_sha256"] != expected_hash or hello["ota"]["state"] != "valid":
                raise RuntimeError("Server outage changed firmware state")
        self.record("server_port_outage", unavailable_seconds=seconds, reconnect_seconds=round(latency, 2))

    def record(self, name, **details):
        entry = {"test": name, "passed": True, **details}
        self.results.append(entry)
        print(json.dumps(entry), flush=True)
        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_file.write_text(
            json.dumps(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "panel_id": self.pairing["panel_id"],
                    "results": self.results,
                },
                indent=2,
            )
            + "\n"
        )

    def connect(self, timeout=20):
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            try:
                raw, _ = self.listener.accept()
            except TimeoutError:
                continue
            raw.settimeout(3)
            raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                connection = self.context.wrap_socket(raw, server_side=True)
            except OSError:
                raw.close()
                continue
            peer = Peer(TLSStream(connection))
            try:
                hello = peer.request("hello")
                if hello.get("panel_id") != self.pairing["panel_id"] or hello.get("self_test_ok") is not True:
                    raise RuntimeError("Identity or self-check failure")
            except BaseException:
                connection.close()
                raise
            return connection, peer, hello, time.monotonic() - started
        raise TimeoutError("Panel did not reconnect")

    def response_probe(self, samples=8):
        class Counter:
            def __init__(self, source):
                self.source = source
                self.lengths = []

            def write(self, data):
                return self.source.write(data)

            def read(self, size):
                data = self.source.read(size)
                if data:
                    self.lengths.append(len(data))
                return data

        connection, peer, hello, _ = self.connect()
        times, records = [], []
        with connection:
            counter = Counter(peer.stream)
            peer.stream = counter
            for _ in range(samples):
                counter.lengths.clear()
                started = time.monotonic()
                peer.request("hello")
                times.append(round(time.monotonic() - started, 4))
                records.append(len(counter.lengths))
        if max(records) > 4:
            raise RuntimeError("Response is fragmented into too many TLS records")
        self.record(
            "batched_tls_responses",
            version=hello["firmware"],
            samples=samples,
            rtt_seconds=times,
            median_seconds=statistics.median(times),
            tls_reads=records,
            rssi_dbm=hello["wifi"].get("rssi"),
        )

    def connection_checks(self, cycles, stable_seconds):
        connection, peer, hello, latency = self.connect()
        original_hash = hello["ota"]["image_sha256"]
        with connection:
            result = bench(
                device=peer.stream, duration=stable_seconds, transport="wifi", expected_panel=self.pairing["panel_id"]
            )
        if result["heartbeats"] < stable_seconds * 0.6:
            raise RuntimeError("Too few heartbeats in stable session")
        self.record(
            "steady_session",
            seconds=stable_seconds,
            heartbeats=result["heartbeats"],
            rejected=result["rejected_frames"],
            initial_connect_seconds=round(latency, 2),
            image_sha256=original_hash,
        )
        latencies = []
        for index in range(cycles):
            connection, peer, hello, latency = self.connect()
            with connection:
                peer.request("demo_state", height_mm=740 + index * 10, brightness=50)
                if hello["ota"]["image_sha256"] != original_hash:
                    raise RuntimeError("Unexpected image change")
            latencies.append(round(latency, 2))
            self.record("server_connection_restart", cycle=index + 1, reconnect_seconds=latencies[-1])

        connection, peer, hello, _ = self.connect()
        with connection:
            start = time.monotonic()
            closed = False
            # Keep TCP open but send absolutely no more application heartbeats.
            while time.monotonic() - start < 7:
                try:
                    peer.stream.read(4096)
                except ConnectionError:
                    closed = True
                    break
            if not closed:
                raise RuntimeError("Panel kept stale control session alive without host heartbeat")
            self.record("missing_heartbeat_disconnect", seconds=round(time.monotonic() - start, 2))

        connection, peer, hello, latency = self.connect()
        with connection:
            peer.stream.write(b"not-json\n" + b"x" * 10000 + b"\n")
            peer.request("demo_state", height_mm=740, brightness=60)
            verified = peer.request("hello")
            if verified["ota"]["image_sha256"] != original_hash:
                raise RuntimeError("Parser fault changed firmware identity")
        self.record("malformed_and_oversized_input", bytes=10010, recovered=True, reconnect_seconds=round(latency, 2))
        return original_hash

    def partial_ota(self, image, original_hash):
        data = image.read_bytes()
        manifest = inspect_image(data)
        connection, peer, _, _ = self.connect()
        with connection:
            peer.request("ota_begin", **manifest)
            for offset in range(0, 4096, 512):
                chunk = data[offset : offset + 512]
                peer.request("ota_chunk", offset=offset, data=base64.b64encode(chunk).decode())
            # Drop the TLS connection without ota_finish or ota_abort.
        connection, peer, hello, latency = self.connect()
        with connection:
            if hello["ota"]["image_sha256"] != original_hash or hello["ota"]["state"] != "valid":
                raise RuntimeError("Interrupted upload changed running image/state")
            if "ota_resume_v1" in hello["capabilities"]:
                resumed = peer.request("ota_begin", **manifest)
                if resumed.get("next_offset") != 4096:
                    raise RuntimeError("Interrupted transfer was not retained at the expected offset")
                peer.request("ota_abort")
            elif hello["ota"]["receiving"]:
                raise RuntimeError("Legacy panel did not abort its interrupted transfer")
        self.record(
            "interrupted_physical_flash_transfer",
            written_bytes=4096,
            current_image_unchanged=True,
            reconnect_seconds=round(latency, 2),
        )

    def rollback(self, image, original_hash):
        data = image.read_bytes()
        manifest = inspect_image(data)
        if manifest["image_sha256"] == original_hash:
            raise RuntimeError("Rollback test requires a distinct candidate image")
        connection, peer, hello, _ = self.connect()
        with connection:
            started = time.monotonic()
            upload(peer, data, manifest)
            peer.request("ota_finish")
            upload_seconds = time.monotonic() - started
        self.record(
            "candidate_activated",
            upload_seconds=round(upload_seconds, 2),
            bytes=len(data),
            candidate_sha256=manifest["image_sha256"],
        )
        connection, peer, hello, latency = self.connect(timeout=40)
        with connection:
            if hello["ota"]["image_sha256"] != manifest["image_sha256"] or hello["ota"]["state"] != "pending":
                raise RuntimeError("Candidate did not boot in PENDING_VERIFY")
            self.record("candidate_pending_boot", version=hello["firmware"], connect_seconds=round(latency, 2))
            start = time.monotonic()
            decoder = Decoder()
            closed = False
            # Keep connectivity healthy, deliberately withhold only ota_confirm.
            while time.monotonic() - start < 100:
                try:
                    peer.stream.write(encode({"type": "heartbeat"}))
                    deadline = time.monotonic() + 0.8
                    while time.monotonic() < deadline:
                        decoder.feed(peer.stream.read(4096))
                except OSError:
                    closed = True
                    break
            if not closed:
                raise RuntimeError("Unconfirmed candidate did not reset within boot deadline")
        connection, peer, hello, latency = self.connect(timeout=40)
        with connection:
            if hello["ota"]["image_sha256"] != original_hash or hello["ota"]["state"] != "valid":
                raise RuntimeError("Did not return to known VALID previous image")
            self.record(
                "automatic_unconfirmed_boot_rollback",
                previous_version=hello["firmware"],
                seconds_after_pending=round(time.monotonic() - start, 2),
                reconnect_seconds=round(latency, 2),
                image_sha256=original_hash,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairing", type=Path, default=Path(".secrets/panel.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/hardware-robustness.json"))
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--stable-seconds", type=int, default=30)
    parser.add_argument("--candidate", type=Path, help="Explicitly enable real flash interruption and rollback tests")
    parser.add_argument(
        "--ota-only", action="store_true", help="Run server outage and OTA faults after earlier connection checks"
    )
    args = parser.parse_args()
    if args.candidate:
        inspect_image(args.candidate.read_bytes())
    if args.ota_only and not args.candidate:
        parser.error("--ota-only requires --candidate")
    harness = Harness(args.pairing, args.report)
    try:
        if args.ota_only:
            if not args.candidate:
                parser.error("--ota-only requires --candidate")
            connection, peer, hello, _ = harness.connect()
            with connection:
                current = hello["ota"]["image_sha256"]
                if hello["ota"]["state"] != "valid":
                    raise RuntimeError("OTA fault tests require a valid baseline")
            harness.record("valid_ota_baseline", version=hello["firmware"], image_sha256=current)
        else:
            harness.response_probe()
            current = harness.connection_checks(args.cycles, args.stable_seconds)
        harness.server_outage(current)
        if args.candidate:
            harness.partial_ota(args.candidate, current)
            harness.rollback(args.candidate, current)
    except BaseException as error:
        entry = {"test": "aborted", "passed": False, "error": str(error)}
        harness.results.append(entry)
        print(json.dumps(entry), flush=True)
        args.report.write_text(json.dumps({"results": harness.results}, indent=2) + "\n")
        raise
    finally:
        harness.listener.close()


if __name__ == "__main__":
    main()
