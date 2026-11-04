"""Actual TLS connections across a simulated application reboot; no flash hardware."""

import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from netlink_panel.ota import OTAError, inspect_image, update
from netlink_panel.protocol import Decoder, encode
from netlink_panel.wifi import psk_context, save_pairing
from test_ota import MemoryPanel, image_fixture


@unittest.skipUnless(getattr(ssl, "HAS_PSK", False), "Python/OpenSSL does not support TLS-PSK")
class NetworkUpdateTests(unittest.TestCase):
    def scenario(
        self,
        *,
        lost_finish_ack=False,
        wrong_boot=False,
        interrupted=False,
        resume=False,
        lost_confirm_ack=False,
        lost_finish_request=False,
        lost_begin_ack=False,
        reject_begin=False,
        reboot_race=False,
        repeated_drops=0,
        finish_drops=0,
        image_data=None,
        drop_offsets=None,
        drop_before_begin=False,
        chunk_delay=0,
        timeout=10,
        expect_timeout=False,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "firmware.bin"
            data = image_data if image_data is not None else image_fixture(fill=8192 if repeated_drops else 1200)
            resume = resume or repeated_drops > 0
            lost_finish_request = lost_finish_request or finish_drops > 0
            image.write_bytes(data)
            panel = MemoryPanel()
            panel.manifest = inspect_image(data)
            key = secrets.token_hex(32)
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            pairing = root / "panel.json"
            save_pairing(pairing, {"panel_id": "panel-test", "key": key, "host": "127.0.0.1", "port": port})
            failures = []
            resumed_offsets = []
            dropped = False
            drops_remaining = repeated_drops or int(resume)
            finish_remaining = finish_drops or int(lost_finish_request)
            if expect_timeout:
                connections = 1
            elif drop_before_begin:
                connections = repeated_drops
            elif finish_drops:
                connections = finish_drops
            elif repeated_drops:
                connections = repeated_drops + 2
            elif resume or lost_confirm_ack or lost_finish_request or lost_begin_ack or reboot_race:
                connections = 3
            else:
                connections = 2

            def connect():
                deadline = time.monotonic() + 3
                while True:
                    try:
                        return socket.create_connection(("127.0.0.1", port), timeout=2)
                    except ConnectionRefusedError:
                        if time.monotonic() >= deadline:
                            raise
                        threading.Event().wait(0.01)

            def device():
                nonlocal dropped, drops_remaining, finish_remaining
                try:
                    context = psk_context("panel-test", key, server=False)
                    for boot in range(connections):
                        with connect() as raw, context.wrap_socket(raw) as connection:
                            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                            connection.settimeout(3)
                            decoder = Decoder()
                            finished = False
                            while not finished:
                                incoming = connection.recv(4096)
                                if not incoming:
                                    break
                                for message in decoder.feed(incoming):
                                    kind = message["type"]
                                    if kind == "heartbeat":
                                        continue
                                    if kind == "hello":
                                        if reboot_race and boot == 1:
                                            connection.sendall(
                                                encode({"type": "ack", "id": message["id"], "ok": False})
                                            )
                                            finished = True
                                            break
                                        hello = panel.hello(
                                            digest="0" * 64 if not panel.activated or wrong_boot else None,
                                            state="valid" if not panel.activated else None,
                                        )
                                        if panel.activated and not wrong_boot:
                                            hello["firmware"] = panel.manifest["version"]
                                        hello["wifi"] = {
                                            "rssi": -85,
                                            "last_disconnect_reason": 3,
                                            "password": "secret-canary",
                                        }
                                        hello["uptime_ms"] = 1000 + boot * 1000
                                        hello["reset_reason"] = 0
                                        if resume or lost_begin_ack or lost_finish_request:
                                            hello["capabilities"].append("ota_resume_v1")
                                            hello["ota"]["receiving"] = bool(panel.payload) and not panel.activated
                                        connection.sendall(encode({**hello, "id": message["id"]}))
                                        continue
                                    if drop_before_begin and kind == "ota_begin" and drops_remaining:
                                        drops_remaining -= 1
                                        finished = True
                                        break
                                    if (
                                        (resume or lost_begin_ack or lost_finish_request)
                                        and kind == "ota_begin"
                                        and panel.manifest
                                        and dropped
                                    ):
                                        resumed_offsets.append(len(panel.payload))
                                        connection.sendall(
                                            encode(
                                                {
                                                    "type": "ack",
                                                    "id": message["id"],
                                                    "ok": True,
                                                    "next_offset": len(panel.payload),
                                                }
                                            )
                                        )
                                        continue
                                    if lost_finish_request and kind == "ota_finish" and finish_remaining:
                                        finish_remaining -= 1
                                        dropped = True
                                        finished = True
                                        break
                                    if reject_begin and kind == "ota_begin":
                                        panel.requests.append(message)
                                        connection.sendall(
                                            encode(
                                                {
                                                    "type": "ack",
                                                    "id": message["id"],
                                                    "ok": False,
                                                    "error": "different_transfer_active",
                                                }
                                            )
                                        )
                                        continue
                                    if kind == "ota_chunk" and chunk_delay:
                                        time.sleep(chunk_delay)
                                    panel.write(encode(message))
                                    if (
                                        (lost_begin_ack and kind == "ota_begin")
                                        or (lost_confirm_ack and kind == "ota_confirm")
                                    ) and not dropped:
                                        dropped = True
                                        panel.output.clear()
                                        finished = True
                                        break
                                    if (
                                        resume
                                        and kind == "ota_chunk"
                                        and drops_remaining
                                        and (
                                            not drop_offsets
                                            or len(panel.payload) >= drop_offsets[repeated_drops - drops_remaining]
                                        )
                                    ):
                                        drops_remaining -= 1
                                        dropped = True
                                        panel.output.clear()  # Chunk was written but its ACK is lost.
                                        finished = True
                                        break
                                    if interrupted and kind == "ota_chunk":
                                        return
                                    if kind == "ota_finish":
                                        finished = True
                                        if lost_finish_ack:
                                            panel.output.clear()
                                            break
                                    connection.sendall(bytes(panel.output))
                                    panel.output.clear()
                        if not panel.activated and not (resume or lost_begin_ack or lost_finish_request):
                            return
                except Exception as error:
                    if not (expect_timeout and isinstance(error, OSError)):
                        failures.append(error)

            worker = threading.Thread(target=device, daemon=True)
            worker.start()
            args = SimpleNamespace(
                firmware=image, pairing=pairing, bind=None, timeout=timeout, receipt=root / "receipt.json"
            )
            try:
                if finish_drops:
                    with self.assertRaisesRegex(OTAError, "without forward progress"):
                        update(args)
                elif expect_timeout:
                    with self.assertRaises(TimeoutError):
                        update(args)
                elif drop_before_begin:
                    with self.assertRaisesRegex(OTAError, "without forward progress"):
                        update(args)
                elif reject_begin:
                    with self.assertRaisesRegex(OTAError, "different_transfer_active"):
                        update(args)
                elif wrong_boot:
                    with self.assertRaisesRegex(OTAError, "different image"):
                        update(args)
                elif interrupted:
                    with self.assertRaises(OSError):
                        update(args)
                else:
                    self.assertEqual(update(args), 0)
            finally:
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(failures, [])
            import json

            receipt = json.loads(args.receipt.read_text())
            self.assertEqual(
                receipt["status"],
                "unconfirmed"
                if wrong_boot or finish_drops
                else ("failed" if interrupted or reject_begin or drop_before_begin or expect_timeout else "confirmed"),
            )
            self.assertEqual(
                panel.confirmed,
                not wrong_boot
                and not interrupted
                and not reject_begin
                and not drop_before_begin
                and not expect_timeout
                and not finish_drops,
            )
            if drop_before_begin:
                self.assertEqual(receipt["recoveries"], 5)
                self.assertEqual(receipt["confirmed_bytes"], 0)
                self.assertFalse(panel.activated)
            elif resume:
                expected = (
                    [((n + 511) // 512) * 512 for n in drop_offsets]
                    if drop_offsets
                    else [512 * (n + 1) for n in range(repeated_drops or 1)]
                )
                self.assertEqual(resumed_offsets, expected)
            if reject_begin:
                self.assertFalse(
                    any(r["type"] == "ota_abort" for r in panel.requests), "Host must not cancel another active image"
                )
            self.assertNotIn("secret-canary", args.receipt.read_text())
            self.assertLessEqual(len(receipt["sessions"]), 32)
            if not interrupted and not reject_begin and not drop_before_begin and not expect_timeout:
                self.assertEqual(receipt["confirmed_bytes"], len(data))
            if interrupted or reject_begin or drop_before_begin or expect_timeout or finish_drops:
                self.assertFalse(panel.activated)
            else:
                self.assertEqual(panel.payload, data)
            if expect_timeout:
                self.assertGreater(receipt["confirmed_bytes"], 0)
                self.assertLess(receipt["confirmed_bytes"], len(data))
                self.assertLess(receipt["elapsed_ms"], timeout * 1000 + 500)
            return receipt

    def test_update_requires_a_new_tls_session_and_confirmed_boot(self):
        self.scenario()

    def test_lost_finish_ack_is_resolved_by_observing_the_boot(self):
        self.scenario(lost_finish_ack=True)

    def test_rollback_or_other_boot_hash_is_not_reported_as_success(self):
        self.scenario(wrong_boot=True)

    def test_disconnect_during_upload_does_not_activate(self):
        self.scenario(interrupted=True)

    def test_lost_chunk_ack_resumes_on_fresh_tls_without_rewriting_bytes(self):
        self.scenario(resume=True)

    def test_lost_begin_ack_resumes_without_restarting_flash(self):
        self.scenario(lost_begin_ack=True)

    def test_finish_lost_before_processing_resumes_retained_complete_image(self):
        self.scenario(lost_finish_request=True)

    def test_lost_confirmation_ack_rechecks_valid_boot(self):
        self.scenario(lost_confirm_ack=True)

    def test_rejected_begin_does_not_abort_a_different_active_image(self):
        self.scenario(reject_begin=True)

    def test_old_app_rejecting_hello_while_rebooting_does_not_fail_the_update(self):
        self.scenario(reboot_race=True)

    def test_repeated_progressing_disconnects_complete_within_deadline(self):
        self.scenario(repeated_drops=6)

    def test_repeated_disconnects_without_progress_exhaust_the_budget(self):
        self.scenario(repeated_drops=6, drop_before_begin=True)

    def test_full_built_image_over_stable_and_lossy_delayed_tls(self):
        image = Path(__file__).resolve().parents[1] / "firmware/.pio/build/panel-bench/firmware.bin"
        if not image.is_file():
            self.skipTest("Build firmware first for full-image OTA tests")
        data = image.read_bytes()
        for delays, cuts in [(0, []), (0.001, [0.27, 0.48, 0.75, 0.95, 0.96, 0.99])]:
            with self.subTest(chunk_delay=delays, interruptions=len(cuts)):
                self.scenario(
                    image_data=data,
                    repeated_drops=len(cuts),
                    drop_offsets=[int(len(data) * n) for n in cuts],
                    chunk_delay=delays,
                    timeout=60,
                )

    def test_total_deadline_stops_a_slow_but_progressing_transfer(self):
        self.scenario(image_data=image_fixture(fill=128000), chunk_delay=0.05, expect_timeout=True)

    def test_repeated_lost_finish_requests_fail_unconfirmed_without_activation(self):
        self.scenario(finish_drops=6)
