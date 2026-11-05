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


class RecoveryBudget:
    """Bound stalled retries; verified forward progress starts a new budget."""

    limit = 5

    def __init__(self):
        self.recoveries = 0
        self.failures_without_progress = 0
        self.confirmed_offset = 0
        self.current_offset = 0

    def advance(self, offset):
        self.current_offset = offset
        if offset > self.confirmed_offset:
            self.confirmed_offset = offset
            self.failures_without_progress = 0

    def retry(self):
        if self.failures_without_progress >= self.limit:
            raise OTAError("OTA reconnect budget exhausted without forward progress")
        self.failures_without_progress += 1
        self.recoveries += 1


def peer_diagnostics(hello):
    """Only bounded numeric/identifier fields; never copy credentials or frames."""
    result = {}
    version = hello.get("firmware")
    if isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,31}", version):
        result["firmware"] = version
    for field in ("uptime_ms", "reset_reason"):
        value = hello.get(field)
        if type(value) is int and 0 <= value <= 0xFFFFFFFF:
            result[field] = value
    wifi = hello.get("wifi")
    if isinstance(wifi, dict):
        value = wifi.get("rssi")
        if type(value) is int and -127 <= value <= 0:
            result["rssi_dbm"] = value
        value = wifi.get("last_disconnect_reason")
        if type(value) is int and 0 <= value <= 65535:
            result["wifi_disconnect_reason"] = value
    return result


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


def upload(peer, data, manifest, *, allow_resume=False, progress=None, authorization=None):
    response = (
        peer.request("ota_begin_signed", **authorization)
        if authorization is not None
        else peer.request("ota_begin", **manifest)
    )
    start = response.get("next_offset")
    if type(start) is not int or start < 0 or start > len(data) or (start != len(data) and start % CHUNK_SIZE):
        raise OTAError("Panel returned an invalid resume offset")
    if start and not allow_resume:
        raise OTAError("Panel did not begin at offset zero")
    if progress is not None:
        progress(start)
    if start:
        report("ota_resumed", offset=start, size=len(data))
    last_percent = -1
    for offset in range(start, len(data), CHUNK_SIZE):
        chunk = data[offset : offset + CHUNK_SIZE]
        response = peer.request("ota_chunk", offset=offset, data=base64.b64encode(chunk).decode("ascii"))
        if response.get("next_offset") != offset + len(chunk):
            raise OTAError("Panel acknowledged an unexpected offset; transfer stopped")
        if progress is not None:
            progress(offset + len(chunk))
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
    authorization = None
    bundle = getattr(args, "release_bundle", None)
    trust_path = getattr(args, "trusted_keys", None)
    board_revision = getattr(args, "board_revision", None)
    if bundle is not None:
        from .signed_updates import load_trust, verify_bundle

        if not trust_path or not board_revision:
            raise OTAError("Signed bundle requires --trusted-keys and --board-revision")
        authorization = json.loads((bundle / "authorization.json").read_bytes())
        verify_bundle(bundle, authorization, load_trust(trust_path), board_revision=board_revision)
        args.firmware = bundle / "firmware.bin"
    elif trust_path or board_revision:
        raise OTAError("--trusted-keys and --board-revision require --release-bundle")
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
    started = time.monotonic()
    deadline = started + args.timeout
    awaiting_reboot = False
    recovering_transfer = False
    budget = RecoveryBudget()
    sessions = deque(maxlen=32)
    session_count = 0
    tls_rejections = 0
    phase = "listen"

    def checkpoint(status=None):
        elapsed = time.monotonic() - started
        receipt.update(
            phase=phase,
            elapsed_ms=round(elapsed * 1000),
            confirmed_bytes=budget.confirmed_offset,
            current_bytes=budget.current_offset,
            tls_rejections=tls_rejections,
            average_bytes_per_second=round(budget.confirmed_offset / max(elapsed, 0.001), 1),
            recoveries=budget.recoveries,
            failures_without_progress=budget.failures_without_progress,
            sessions=list(sessions),
            sessions_omitted=max(0, session_count - len(sessions)),
        )
        if status is not None:
            receipt["status"] = status
        write_receipt(args.receipt, receipt)

    def retry(error):
        receipt["last_transport_error"] = {"phase": phase, "reason": type(error).__name__}
        budget.retry()
        checkpoint("reconnecting")
        report(
            "ota_reconnecting",
            recovery=budget.recoveries,
            failures_without_progress=budget.failures_without_progress,
            confirmed_bytes=budget.confirmed_offset,
            phase=phase,
            reason=type(error).__name__,
            elapsed_ms=receipt["elapsed_ms"],
        )

    context = psk_context(pairing["panel_id"], pairing["key"], server=True)
    try:
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((args.bind or pairing["host"], pairing["port"]))
            listener.listen(1)
            listener.settimeout(0.5)
            report("ota_waiting", panel_id=pairing["panel_id"], version=manifest["version"])
            while time.monotonic() < deadline:
                phase = "listen"
                try:
                    raw, _ = listener.accept()
                except TimeoutError:
                    continue
                phase = "tls"
                # Bad TLS clients cannot receive image bytes or stop the server.
                try:
                    raw.settimeout(min(3, max(0.01, deadline - time.monotonic())))
                    raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    tls_started = time.monotonic()
                    connection = context.wrap_socket(raw, server_side=True)
                    tls_ms = round((time.monotonic() - tls_started) * 1000)
                except OSError as error:
                    raw.close()
                    tls_rejections += 1
                    if tls_rejections <= 5:
                        report("ota_client_rejected", phase="tls", reason=type(error).__name__)
                    continue
                with connection:
                    peer = Peer(TLSStream(connection), deadline=deadline)
                    phase = "hello"
                    hello_started = time.monotonic()
                    try:
                        hello = peer.request("hello")
                    except (OSError, HandshakeRejected) as error:
                        if awaiting_reboot or recovering_transfer:
                            retry(error)
                            continue
                        raise
                    ota = check_hello(hello, pairing, manifest)
                    if authorization is not None:
                        if (
                            ota.get("signed_required") is not True
                            or ota.get("authorization") != "ecdsa-p256-sha256-v1"
                            or ota.get("board_revision") != board_revision
                        ):
                            raise OTAError("Panel does not match the pinned signed-update policy")
                    elif ota.get("signed_required") is True:
                        raise OTAError("Panel requires an authenticated release bundle")
                    session_count += 1
                    sample = {
                        **peer_diagnostics(hello),
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                        "hello_ms": round((time.monotonic() - hello_started) * 1000),
                        "tls_ms": tls_ms,
                        "confirmed_bytes": budget.confirmed_offset,
                    }
                    sessions.append(sample)
                    checkpoint()
                    report("ota_session", **sample)
                    # A finish ACK may be lost before the device processes it.
                    # Only an explicitly retained transfer permits finishing on
                    # the old image; a different boot without it means failure.
                    retained_finish = awaiting_reboot and ota.get("receiving") is True
                    if (awaiting_reboot and not retained_finish) or ota.get("image_sha256") == manifest["image_sha256"]:
                        phase = "confirm"
                        try:
                            result = confirm(peer, hello, pairing, manifest)
                        except (OSError, TimeoutError) as error:
                            if time.monotonic() >= deadline:
                                raise
                            retry(error)
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
                        receipt["confirmed"] = result
                        phase = "complete"
                        checkpoint("confirmed")
                        report("ota_confirmed", **result)
                        return 0
                    if ota.get("state") == "pending":
                        raise OTAError("Another image is awaiting boot confirmation; refusing to overwrite")
                    resumable = "ota_resume_v1" in hello["capabilities"]
                    phase = "transfer"
                    try:
                        upload(
                            peer,
                            data,
                            manifest,
                            allow_resume=resumable,
                            progress=budget.advance,
                            authorization=authorization,
                        )
                        recovering_transfer = False
                    except (OSError, TimeoutError) as error:
                        if resumable and time.monotonic() < deadline:
                            retry(error)
                            recovering_transfer = True
                            continue
                        raise
                    awaiting_reboot = True
                    phase = "activate"
                    checkpoint("awaiting_reboot")
                    try:
                        response = peer.request("ota_finish")
                        if response.get("state") != "rebooting":
                            raise OTAError("Panel did not schedule a reboot")
                    except (OSError, TimeoutError) as error:
                        # Activation may have succeeded. Reconnect and verify,
                        # but repeated lost finish requests must also be bounded.
                        if time.monotonic() >= deadline:
                            raise
                        retry(error)
                    report("ota_awaiting_reboot")
            raise OTAError("Update timed out without observing the requested image and confirmed boot")
    except BaseException as error:
        receipt.update(status="unconfirmed" if awaiting_reboot else "failed", reason=type(error).__name__)
        if isinstance(error, OTAError):
            receipt["detail"] = str(error)
        checkpoint()
        raise
