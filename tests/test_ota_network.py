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
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "firmware.bin"
            data = image_fixture()
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
                nonlocal dropped
                try:
                    context = psk_context("panel-test", key, server=False)
                    for boot in range(
                        3 if resume or lost_confirm_ack or lost_finish_request or lost_begin_ack or reboot_race else 2
                    ):
                        with connect() as raw, context.wrap_socket(raw) as connection:
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
                                        if resume or lost_begin_ack or lost_finish_request:
                                            hello["capabilities"].append("ota_resume_v1")
                                            hello["ota"]["receiving"] = bool(panel.payload) and not panel.activated
                                        connection.sendall(encode({**hello, "id": message["id"]}))
                                        continue
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
                                    if lost_finish_request and kind == "ota_finish" and not dropped:
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
                                    panel.write(encode(message))
                                    if (
                                        (lost_begin_ack and kind == "ota_begin")
                                        or (lost_confirm_ack and kind == "ota_confirm")
                                    ) and not dropped:
                                        dropped = True
                                        panel.output.clear()
                                        finished = True
                                        break
                                    if resume and kind == "ota_chunk" and not dropped:
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
                    failures.append(error)

            worker = threading.Thread(target=device, daemon=True)
            worker.start()
            args = SimpleNamespace(
                firmware=image, pairing=pairing, bind=None, timeout=10, receipt=root / "receipt.json"
            )
            try:
                if reject_begin:
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
                "unconfirmed" if wrong_boot else ("failed" if interrupted or reject_begin else "confirmed"),
            )
            self.assertEqual(panel.confirmed, not wrong_boot and not interrupted and not reject_begin)
            if resume:
                self.assertEqual(resumed_offsets, [512])
            if reject_begin:
                self.assertFalse(
                    any(r["type"] == "ota_abort" for r in panel.requests), "Host must not cancel another active image"
                )
            if interrupted or reject_begin:
                self.assertFalse(panel.activated)
            else:
                self.assertEqual(panel.payload, data)

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
