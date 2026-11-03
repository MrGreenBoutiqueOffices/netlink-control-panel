"""Image validation and transfer/confirmation regression tests without a panel."""

import base64
import hashlib
import struct
import unittest

from netlink_panel.ota import (
    CHUNK_SIZE,
    PROFILE,
    SLOT_SIZE,
    OTAError,
    Peer,
    check_hello,
    confirm,
    inspect_image,
    upload,
)
from netlink_panel.protocol import Decoder, encode


def image_fixture(*, version="0.3.0", profile=PROFILE, chip=9, fill=1200):
    header = bytearray(24)
    header[0], header[1], header[23] = 0xE9, 1, 1
    struct.pack_into("<H", header, 12, chip)
    payload = bytearray(256)
    struct.pack_into("<I", payload, 0, 0xABCD5432)
    payload.extend(f"NETLINK_PANEL_IMAGE_V1|{profile}|v{version};".encode())
    payload.extend(b"x" * fill)
    payload.extend(b"\0" * (-len(payload) % 4))
    result = header + struct.pack("<II", 0x3C000020, len(payload)) + payload
    checksum = 0xEF
    for value in payload:
        checksum ^= value
    result.extend(b"\0" * ((len(result) | 15) - len(result)))
    result.append(checksum)
    return bytes(result + hashlib.sha256(result).digest())


class MemoryPanel:
    """Application responses only; this model is NOT an ESP flash emulator."""

    def __init__(self, *, wrong_offset=False, corrupt=False):
        self.decoder = Decoder()
        self.output = bytearray()
        self.requests = []
        self.manifest = None
        self.payload = bytearray()
        self.wrong_offset = wrong_offset
        self.corrupt = corrupt
        self.confirmed = False
        self.activated = False

    def hello(self, *, digest=None, state=None):
        return {
            "type": "hello",
            "panel_id": "panel-test",
            "firmware": "0.3.0",
            "self_test_ok": True,
            "capabilities": ["ota_v1"],
            "ota": {
                "supported": True,
                "profile": PROFILE,
                "max_size": SLOT_SIZE,
                "image_sha256": digest or self.manifest["image_sha256"],
                "state": state or ("valid" if self.confirmed else "pending"),
            },
        }

    def write(self, data):
        for request in self.decoder.feed(data):
            self.requests.append(request)
            kind = request["type"]
            if kind == "heartbeat":
                continue
            response = {"type": "ack", "id": request["id"], "ok": True}
            if kind == "hello":
                response = {**self.hello(), "id": request["id"]}
            elif kind == "ota_begin":
                self.manifest = request
                response["next_offset"] = 0
            elif kind == "ota_chunk":
                chunk = base64.b64decode(request["data"], validate=True)
                if request["offset"] != len(self.payload) or not 0 < len(chunk) <= CHUNK_SIZE:
                    raise AssertionError("Invalid host chunk")
                self.payload.extend(chunk)
                response["next_offset"] = len(self.payload) + int(self.wrong_offset)
            elif kind == "ota_finish":
                correct = (
                    len(self.payload) == self.manifest["size"]
                    and hashlib.sha256(self.payload).hexdigest() == self.manifest["sha256"]
                )
                response["ok"] = correct and not self.corrupt
                response["state"] = "rebooting"
                self.activated = response["ok"]
            elif kind == "ota_confirm":
                self.confirmed = True
                response["state"] = "valid"
            self.output.extend(encode({"type": "heartbeat"}) + encode(response))
        return len(data)

    def read(self, size):
        result = bytes(self.output[:size])
        del self.output[:size]
        return result


class ImageTests(unittest.TestCase):
    def test_valid_s3_image_and_both_hashes(self):
        data = image_fixture()
        manifest = inspect_image(data)
        self.assertEqual(manifest["size"], len(data))
        self.assertEqual(manifest["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest["image_sha256"], data[-32:].hex())

    def test_wrong_chip_board_and_oversized_images_are_rejected(self):
        for data in (image_fixture(chip=0), image_fixture(profile="wrong-board"), b"x" * (SLOT_SIZE + 1)):
            with self.assertRaises(OTAError):
                inspect_image(data)

    def test_corruption_truncation_and_merged_flash_are_rejected(self):
        data = image_fixture()
        corrupt = bytearray(data)
        corrupt[300] ^= 1
        for bad in (bytes(corrupt), data[:-1], b"\xff" * 0x10000 + data, data + b"\0"):
            with self.assertRaises(OTAError):
                inspect_image(bad)

    def test_checksum_mismatch_even_with_recomputed_sha_is_rejected(self):
        data = bytearray(image_fixture())
        data[-33] ^= 1
        data[-32:] = hashlib.sha256(data[:-32]).digest()
        with self.assertRaisesRegex(OTAError, "checksum"):
            inspect_image(data)


class TransferTests(unittest.TestCase):
    def test_older_firmware_needs_one_usb_install(self):
        with self.assertRaisesRegex(OTAError, "once over USB"):
            check_hello(
                {"panel_id": "panel-test", "capabilities": ["demo_state"]},
                {"panel_id": "panel-test"},
                inspect_image(image_fixture()),
            )

    def test_unhealthy_panel_is_not_updated(self):
        panel = MemoryPanel()
        panel.manifest = inspect_image(image_fixture())
        with self.assertRaisesRegex(OTAError, "self-check"):
            check_hello({**panel.hello(), "self_test_ok": False}, {"panel_id": "panel-test"}, panel.manifest)
        self.assertFalse(panel.activated)

    def test_chunks_reassemble_exact_image_and_finish_is_explicit(self):
        data = image_fixture()
        panel = MemoryPanel()
        peer = Peer(panel)
        upload(peer, data, inspect_image(data))
        self.assertEqual(panel.payload, data)
        self.assertFalse(panel.activated)
        self.assertFalse(panel.confirmed)
        peer.request("ota_finish")
        self.assertTrue(panel.activated)
        self.assertFalse(panel.confirmed)

    def test_bad_offset_stops_before_activation(self):
        panel = MemoryPanel(wrong_offset=True)
        data = image_fixture()
        with self.assertRaisesRegex(OTAError, "offset"):
            upload(Peer(panel), data, inspect_image(data))
        self.assertFalse(panel.activated)
        self.assertEqual(sum(r["type"] == "ota_chunk" for r in panel.requests), 1)

    def test_confirmation_requires_target_hash_and_observed_valid_state(self):
        data = image_fixture()
        manifest = inspect_image(data)
        panel = MemoryPanel()
        panel.manifest = manifest
        result = confirm(Peer(panel), panel.hello(), {"panel_id": "panel-test"}, manifest)
        self.assertEqual(result["state"], "valid")
        self.assertTrue(panel.confirmed)

    def test_old_image_after_reboot_is_not_success(self):
        panel = MemoryPanel()
        manifest = inspect_image(image_fixture())
        panel.manifest = manifest
        with self.assertRaisesRegex(OTAError, "different image"):
            confirm(Peer(panel), panel.hello(digest="0" * 64), {"panel_id": "panel-test"}, manifest)
        self.assertFalse(panel.confirmed)

    def test_missing_or_failed_confirmation_never_reports_success(self):
        class NoConfirmation(MemoryPanel):
            def write(self, data):
                messages = Decoder().feed(data)
                if any(m["type"] == "ota_confirm" for m in messages):
                    self.output.extend(
                        encode({"type": "ack", "id": messages[0]["id"], "ok": False, "error": "boot_check_failed"})
                    )
                    return len(data)
                return super().write(data)

        panel = NoConfirmation()
        manifest = inspect_image(image_fixture())
        panel.manifest = manifest
        with self.assertRaisesRegex(OTAError, "boot_check_failed"):
            confirm(Peer(panel), panel.hello(), {"panel_id": "panel-test"}, manifest)

    def test_total_deadline_expires_before_writing(self):
        panel = MemoryPanel()
        with self.assertRaises(TimeoutError):
            Peer(panel, deadline=0).request("hello")
        self.assertEqual(panel.requests, [])

    def test_confirmation_ack_without_valid_observed_state_is_rejected(self):
        class FalseConfirmation(MemoryPanel):
            def write(self, data):
                message = Decoder().feed(data)[0]
                if message["type"] == "ota_confirm":
                    self.output.extend(encode({"type": "ack", "id": message["id"], "ok": True, "state": "valid"}))
                    return len(data)
                return super().write(data)

        panel = FalseConfirmation()
        manifest = inspect_image(image_fixture())
        panel.manifest = manifest
        with self.assertRaisesRegex(OTAError, "Post-confirmation"):
            confirm(Peer(panel), panel.hello(), {"panel_id": "panel-test"}, manifest)

    def test_frames_stay_within_existing_1024_byte_limit(self):
        panel = MemoryPanel()
        data = image_fixture()
        upload(Peer(panel), data, inspect_image(data))
        for message in panel.requests:
            self.assertLessEqual(len(encode(message)), 1025)


class ResumeOffsetTests(unittest.TestCase):
    def test_resume_offset_must_be_bounded_and_chunk_aligned(self):
        data = image_fixture()
        for offset in (-1, True, 1, len(data) + 1, "512"):

            class BadResume(MemoryPanel):
                def write(self, frame):
                    message = Decoder().feed(frame)[0]
                    if message["type"] == "ota_begin":
                        self.output.extend(
                            encode({"type": "ack", "id": message["id"], "ok": True, "next_offset": offset})
                        )
                        return len(frame)
                    return super().write(frame)

            panel = BadResume()
            with self.subTest(offset=offset), self.assertRaisesRegex(OTAError, "resume offset"):
                upload(Peer(panel), data, inspect_image(data), allow_resume=True)
            self.assertFalse(panel.activated)

    def test_retained_complete_image_can_finish_without_replaying_a_chunk(self):
        data = image_fixture()

        class Complete(MemoryPanel):
            def write(self, frame):
                message = Decoder().feed(frame)[0]
                if message["type"] == "ota_begin":
                    self.output.extend(
                        encode({"type": "ack", "id": message["id"], "ok": True, "next_offset": len(data)})
                    )
                    return len(frame)
                return super().write(frame)

        panel = Complete()
        upload(Peer(panel), data, inspect_image(data), allow_resume=True)
        self.assertEqual(panel.payload, b"")
        self.assertFalse(panel.activated)
