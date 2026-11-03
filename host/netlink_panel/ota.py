"""Application-only OTA over the existing authenticated Wi-Fi connection."""

import base64
import hashlib
import json
import os
import re
import socket
import struct
import tempfile
import time
from collections import deque
from datetime import datetime, timezone

from .cli import report
from .protocol import Decoder, encode

PROFILE = "lilygo-s3-long-cst3530:p1:ota3m-v1"
SLOT_SIZE = 0x300000
CHUNK_SIZE = 512
MARKER = re.compile(rb"NETLINK_PANEL_IMAGE_V1\|" + PROFILE.encode() + rb"\|v([A-Za-z0-9._-]{1,31});")


class OTAError(RuntimeError):
    pass


class HandshakeRejected(OTAError):
    """The old app may reject hello during its short committed/reboot window."""

    pass


def inspect_image(data):
    """Accept only an exact ESP32-S3 app image with our retained board marker."""
    if not 288 <= len(data) <= SLOT_SIZE or data[0] != 0xE9 or not 1 <= data[1] <= 16:
        raise OTAError("Use firmware.bin: an ESP32-S3 application image, not a bootloader or merged flash image")
    if struct.unpack_from("<H", data, 12)[0] != 9 or data[23] != 1:
        raise OTAError("Expected an ESP32-S3 image with an appended SHA-256 digest")
    if struct.unpack_from("<I", data, 32)[0] != 0xABCD5432:
        raise OTAError("Application descriptor is missing")
    position, checksum = 24, 0xEF
    for _ in range(data[1]):
        if position + 8 > len(data):
            raise OTAError("Truncated ESP segment header")
        length = struct.unpack_from("<I", data, position + 4)[0]
        position += 8
        if position + length > len(data) - 33:
            raise OTAError("Truncated ESP segment")
        for value in data[position : position + length]:
            checksum ^= value
        position += length
    checksum_position = position | 15
    if checksum_position + 33 != len(data) or data[checksum_position] != checksum:
        raise OTAError("ESP image length or checksum is invalid")
    digest = hashlib.sha256(data[:-32]).digest()
    if digest != data[-32:]:
        raise OTAError("ESP image SHA-256 check failed")
    identities = set(MARKER.findall(data))
    if len(identities) != 1:
        raise OTAError("Image does not identify this NetLink panel board/protocol/partition layout")
    return {
        "profile": PROFILE,
        "version": identities.pop().decode("ascii"),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "image_sha256": digest.hex(),
    }


class Peer:
    """Keep one decoder across requests, preserving coalesced frames."""

    def __init__(self, stream, *, deadline=float("inf")):
        self.stream = stream
        self.decoder = Decoder()
        self.messages = deque()
        self.sequence = 0
        self.next_heartbeat = time.monotonic()
        self.deadline = deadline

    def request(self, kind, *, timeout=8, **fields):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Overall update deadline expired")
        self.sequence += 1
        request_id = self.sequence
        self.stream.write(encode({"type": kind, "id": request_id, **fields}))
        deadline = min(self.deadline, time.monotonic() + timeout)
        while time.monotonic() < deadline:
            if time.monotonic() >= self.next_heartbeat:
                self.stream.write(encode({"type": "heartbeat"}))
                self.next_heartbeat = time.monotonic() + 1
            while self.messages:
                message = self.messages.popleft()
                if message.get("id") != request_id:
                    continue
                expected = "hello" if kind == "hello" else "ack"
                if expected == "hello" and message["type"] == "ack" and message.get("ok") is False:
                    raise HandshakeRejected("Panel is not accepting a handshake")
                if message["type"] != expected:
                    raise OTAError("Unexpected OTA response type")
                if expected == "ack" and message.get("ok") is not True:
                    # Firmware error values are identifiers, never payloads.
                    code = message.get("error", "rejected")
                    if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,64}", code):
                        code = "rejected"
                    raise OTAError(f"Panel rejected {kind}: {code}")
                return message
            self.messages.extend(self.decoder.feed(self.stream.read(4096)))
        raise TimeoutError(f"Timeout waiting for {kind}")


def check_hello(hello, pairing, manifest):
    if hello.get("panel_id") != pairing["panel_id"]:
        raise OTAError("Panel identity does not match the pairing")
    capabilities = hello.get("capabilities")
    ota = hello.get("ota")
    if not isinstance(capabilities, list) or "ota_v1" not in capabilities or not isinstance(ota, dict):
        raise OTAError("Install firmware 0.3.0 or newer once over USB; this panel does not yet support OTA")
    if ota.get("supported") is not True or ota.get("profile") != manifest["profile"]:
        raise OTAError("Panel board/partition profile does not support this image")
    if type(ota.get("max_size")) is not int or manifest["size"] > ota["max_size"]:
        raise OTAError("Firmware is too large for the inactive slot")
    if hello.get("self_test_ok") is not True:
        raise OTAError("Panel display/touch startup self-check has not passed")
    return ota


def upload(peer, data, manifest, *, allow_resume=False):
    response = peer.request("ota_begin", **manifest)
    start = response.get("next_offset")
    if type(start) is not int or start < 0 or start > len(data) or (start != len(data) and start % CHUNK_SIZE):
        raise OTAError("Panel returned an invalid resume offset")
    if start and not allow_resume:
        raise OTAError("Panel did not begin at offset zero")
    if start:
        report("ota_resumed", offset=start, size=len(data))
    last_percent = -1
    for offset in range(start, len(data), CHUNK_SIZE):
        chunk = data[offset : offset + CHUNK_SIZE]
        response = peer.request("ota_chunk", offset=offset, data=base64.b64encode(chunk).decode("ascii"))
        if response.get("next_offset") != offset + len(chunk):
            raise OTAError("Panel acknowledged an unexpected offset; transfer stopped")
        percent = (offset + len(chunk)) * 100 // len(data)
        if percent // 10 != last_percent // 10:
            report("ota_progress", percent=percent)
            last_percent = percent
    # A lost finish acknowledgement is ambiguous: the panel may already reboot.
    # The caller must reconnect and verify; it must never blindly resend a flash.


def confirm(peer, hello, pairing, manifest):
    ota = check_hello(hello, pairing, manifest)
    if ota.get("image_sha256") != manifest["image_sha256"]:
        raise OTAError("Panel returned a different image after reboot; possible rollback")
    if hello.get("firmware") != manifest["version"]:
        raise OTAError("Running version differs from the image identity")
    response = peer.request("ota_confirm", image_sha256=manifest["image_sha256"])
    if response.get("state") != "valid":
        raise OTAError("Panel did not confirm its new boot")
    final = peer.request("hello")
    ota = check_hello(final, pairing, manifest)
    if ota.get("state") != "valid" or ota.get("image_sha256") != manifest["image_sha256"]:
        raise OTAError("Post-confirmation verification failed")
    return {
        "panel_id": pairing["panel_id"],
        "version": manifest["version"],
        "image_sha256": manifest["image_sha256"],
        "state": "valid",
    }


def write_receipt(path, receipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
        json.dump(receipt, output, indent=2)
        output.write("\n")
        temporary = output.name
    os.replace(temporary, path)


def update(args):
    from .wifi import TLSStream, load_pairing, psk_context

    if not 10 <= args.timeout <= 3600:
        raise OTAError("Update timeout must be 10..3600 seconds")
    if args.firmware.stat().st_size > SLOT_SIZE:
        raise OTAError("Firmware exceeds the application slot")
    data = args.firmware.read_bytes()
    manifest = inspect_image(data)  # Before opening any network connection.
    pairing = load_pairing(args.pairing)
    receipt = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "panel_id": pairing["panel_id"],
        "requested": manifest,
        "status": "started",
    }
    write_receipt(args.receipt, receipt)
    deadline = time.monotonic() + args.timeout
    awaiting_reboot = False
    recovering_transfer = False
    recovery_count = 0
    context = psk_context(pairing["panel_id"], pairing["key"], server=True)
    try:
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((args.bind or pairing["host"], pairing["port"]))
            listener.listen(1)
            listener.settimeout(0.5)
            report("ota_waiting", panel_id=pairing["panel_id"], version=manifest["version"])
            while time.monotonic() < deadline:
                try:
                    raw, _ = listener.accept()
                except TimeoutError:
                    continue
                # Bad TLS clients cannot receive image bytes or stop the server.
                try:
                    raw.settimeout(3)
                    raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    connection = context.wrap_socket(raw, server_side=True)
                except OSError:
                    raw.close()
                    report("ota_client_rejected")
                    continue
                with connection:
                    peer = Peer(TLSStream(connection), deadline=deadline)
                    try:
                        hello = peer.request("hello")
                    except (OSError, HandshakeRejected):
                        if awaiting_reboot or recovering_transfer:
                            recovery_count += 1
                            if recovery_count > 5:
                                raise OTAError("OTA reconnect budget exhausted")
                            continue
                        raise
                    ota = check_hello(hello, pairing, manifest)
                    # A finish ACK may be lost before the device processes it.
                    # Only an explicitly retained transfer permits finishing on
                    # the old image; a different boot without it means failure.
                    retained_finish = awaiting_reboot and ota.get("receiving") is True
                    if (awaiting_reboot and not retained_finish) or ota.get("image_sha256") == manifest["image_sha256"]:
                        try:
                            result = confirm(peer, hello, pairing, manifest)
                        except (OSError, TimeoutError):
                            if recovery_count >= 5 or time.monotonic() >= deadline:
                                raise
                            recovery_count += 1
                            recovering_transfer = True
                            continue
                        action = (
                            "updated"
                            if awaiting_reboot
                            else (
                                "confirmed_existing_candidate" if ota.get("state") == "pending" else "already_current"
                            )
                        )
                        result.update(action=action, reboot_observed=awaiting_reboot)
                        receipt.update(status="confirmed", confirmed=result, recoveries=recovery_count)
                        write_receipt(args.receipt, receipt)
                        report("ota_confirmed", **result)
                        return 0
                    if ota.get("state") == "pending":
                        raise OTAError("Another image is awaiting boot confirmation; refusing to overwrite")
                    resumable = "ota_resume_v1" in hello["capabilities"]
                    try:
                        upload(peer, data, manifest, allow_resume=resumable)
                        recovering_transfer = False
                    except (OSError, TimeoutError):
                        if resumable and recovery_count < 5 and time.monotonic() < deadline:
                            recovery_count += 1
                            recovering_transfer = True
                            receipt.update(status="reconnecting", recoveries=recovery_count)
                            write_receipt(args.receipt, receipt)
                            report("ota_reconnecting", recovery=recovery_count)
                            continue
                        raise
                    awaiting_reboot = True
                    receipt["status"] = "awaiting_reboot"
                    write_receipt(args.receipt, receipt)
                    try:
                        response = peer.request("ota_finish")
                        if response.get("state") != "rebooting":
                            raise OTAError("Panel did not schedule a reboot")
                    except (OSError, TimeoutError):
                        # Activation may have succeeded. Only observed boot hash
                        # and a confirmed app state can resolve this uncertainty.
                        pass
                    report("ota_awaiting_reboot")
            raise OTAError("Update timed out without observing the requested image and confirmed boot")
    except BaseException as error:
        receipt.update(status="unconfirmed" if awaiting_reboot else "failed", reason=type(error).__name__)
        if isinstance(error, OTAError):
            receipt["detail"] = str(error)
        write_receipt(args.receipt, receipt)
        raise
