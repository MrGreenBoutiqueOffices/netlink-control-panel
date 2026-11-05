"""Independent P-256 release authorization; no trust-on-first-use or JSON signing."""

import base64
import hashlib
import json
import re
import struct
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

DOMAIN = b"NETLINK-PANEL-OTA\0\x01"
BOARD_PROFILE = "lilygo-s3-long-cst3530"
LAYOUT = "ota3m-v1"
FIELDS = (("version", 31), ("board_profile", 64), ("board_revision", 32), ("partition_layout", 32))


class SignatureError(ValueError):
    pass


def unbase64(value, maximum):
    if not isinstance(value, str) or len(value) > ((maximum + 2) // 3) * 4:
        raise SignatureError("Invalid bounded base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError as error:
        raise SignatureError("Invalid bounded base64") from error
    if len(decoded) > maximum or base64.b64encode(decoded).decode() != value:
        raise SignatureError("Noncanonical or oversized base64")
    return decoded


def public_key_id(der):
    return hashlib.sha256(der).digest()[:16].hex()


def load_trust(path):
    data = json.loads(Path(path).read_text())
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "mode", "minimum_counter", "keys"}
        or type(data["schema"]) is not int
        or data["schema"] != 1
    ):
        raise SignatureError("Unknown trust policy")
    if (
        data["mode"] not in {"bench", "signed"}
        or type(data["minimum_counter"]) is not int
        or not 0 <= data["minimum_counter"] < 2**64
    ):
        raise SignatureError("Invalid trust policy")
    if not isinstance(data["keys"], list) or len(data["keys"]) > 4:
        raise SignatureError("At most four pinned keys are allowed")
    seen = set()
    for key in data["keys"]:
        if not isinstance(key, dict) or set(key) != {"id", "public_key", "revoked"} or type(key["revoked"]) is not bool:
            raise SignatureError("Invalid pinned key")
        der = unbase64(key["public_key"], 128)
        try:
            public = serialization.load_der_public_key(der)
        except ValueError as error:
            raise SignatureError("Invalid public key") from error
        if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
            raise SignatureError("Only ECDSA P-256 keys are accepted")
        if public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) != der:
            raise SignatureError("Public key must be canonical SPKI DER")
        if key["id"] != public_key_id(der) or key["id"] in seen:
            raise SignatureError("Invalid or duplicate key fingerprint")
        seen.add(key["id"])
    if data["mode"] == "bench" and (data["keys"] or data["minimum_counter"]):
        raise SignatureError("Bench mode cannot contain managed trust policy")
    return data


def encode_record(record):
    if set(record) != {
        "key_id",
        "counter",
        "protocol_min",
        "protocol_max",
        "size",
        "sha256",
        "image_sha256",
        "manifest_sha256",
        "commit",
        *[name for name, _ in FIELDS],
    }:
        raise SignatureError("Invalid authorization fields")
    for name, low, high in [
        ("counter", 1, 2**64 - 1),
        ("protocol_min", 1, 65535),
        ("protocol_max", 1, 65535),
        ("size", 288, 0x300000),
    ]:
        if type(record[name]) is not int or not low <= record[name] <= high:
            raise SignatureError("Invalid authorization range")
    if record["protocol_min"] > record["protocol_max"]:
        raise SignatureError("Invalid protocol range")
    for name, length in [("key_id", 32), ("sha256", 64), ("image_sha256", 64), ("manifest_sha256", 64), ("commit", 40)]:
        if not isinstance(record[name], str) or not re.fullmatch(r"[0-9a-f]{" + str(length) + "}", record[name]):
            raise SignatureError("Invalid authorization digest")
    output = (
        DOMAIN
        + bytes.fromhex(record["key_id"])
        + struct.pack(">QHHI", record["counter"], record["protocol_min"], record["protocol_max"], record["size"])
    )
    output += b"".join(bytes.fromhex(record[name]) for name in ["sha256", "image_sha256", "manifest_sha256", "commit"])
    for name, maximum in FIELDS:
        value = record[name]
        if not isinstance(value, str) or not 1 <= len(value) <= maximum or not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
            raise SignatureError("Invalid authorization identifier")
        output += bytes([len(value)]) + value.encode("ascii")
    return output


def decode_record(data):
    position = len(DOMAIN)
    if not data.startswith(DOMAIN) or len(data) > 340 or len(data) < position + 148:
        raise SignatureError("Invalid authorization format")
    key_id = data[position : position + 16].hex()
    position += 16
    counter, low, high, size = struct.unpack_from(">QHHI", data, position)
    position += 16
    result = {"key_id": key_id, "counter": counter, "protocol_min": low, "protocol_max": high, "size": size}
    for name, count in [("sha256", 32), ("image_sha256", 32), ("manifest_sha256", 32), ("commit", 20)]:
        result[name] = data[position : position + count].hex()
        position += count
    try:
        for name, maximum in FIELDS:
            count = data[position]
            position += 1
            result[name] = data[position : position + count].decode("ascii")
            position += count
    except (IndexError, UnicodeDecodeError) as error:
        raise SignatureError("Truncated authorization") from error
    if position != len(data) or encode_record(result) != data:
        raise SignatureError("Noncanonical authorization")
    return result


def verify_authorization(envelope, trust, *, board_revision, protocol=2):
    if not isinstance(envelope, dict) or set(envelope) != {"authorization", "signature"}:
        raise SignatureError("Invalid signed envelope")
    payload = unbase64(envelope["authorization"], 340)
    signature = unbase64(envelope["signature"], 72)
    record = decode_record(payload)
    if trust["mode"] != "signed":
        raise SignatureError("Signed updates are not configured")
    key = next((key for key in trust["keys"] if key["id"] == record["key_id"]), None)
    if key is None or key["revoked"]:
        raise SignatureError("Unknown or revoked release key")
    public = serialization.load_der_public_key(unbase64(key["public_key"], 128))
    try:
        if utils.encode_dss_signature(*utils.decode_dss_signature(signature)) != signature:
            raise SignatureError("Noncanonical release signature")
        public.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError) as error:
        raise SignatureError("Invalid release signature") from error
    if board_revision in {"", "unverified"} or record["board_revision"] != board_revision:
        raise SignatureError("Unknown or incompatible board revision")
    if (
        record["board_profile"] != BOARD_PROFILE
        or record["partition_layout"] != LAYOUT
        or not record["protocol_min"] <= protocol <= record["protocol_max"]
    ):
        raise SignatureError("Incompatible signed release")
    if record["counter"] < trust["minimum_counter"]:
        raise SignatureError("Release counter below trusted minimum")
    return record


def verify_bundle(folder, envelope, trust, *, board_revision):
    from .ota import OTAError, inspect_image

    folder = Path(folder)
    record = verify_authorization(envelope, trust, board_revision=board_revision)
    manifest_bytes = (folder / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    firmware = (folder / "firmware.bin").read_bytes()
    policy_digest = hashlib.sha256(json.dumps(trust, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    marker = f"NETLINK_PANEL_TRUST_V1|signed|{board_revision}|{policy_digest};".encode()
    if firmware.count(marker) != 1:
        raise SignatureError("Firmware does not contain the expected signed trust policy")
    try:
        image = inspect_image(firmware)
    except OTAError as error:
        raise SignatureError("Invalid application image") from error
    if hashlib.sha256(manifest_bytes).hexdigest() != record["manifest_sha256"] or image != manifest["firmware"]:
        raise SignatureError("Release manifest does not match authorization")
    for name in ["sha256", "image_sha256", "size", "version"]:
        if image[name] != record[name]:
            raise SignatureError("Firmware does not match authorization")
    if manifest["source"]["commit"] != record["commit"]:
        raise SignatureError("Source commit does not match authorization")
    for name in ["board_profile", "board_revision", "partition_layout", "protocol_min", "protocol_max"]:
        if manifest["compatibility"][name] != record[name]:
            raise SignatureError("Compatibility does not match authorization")
    if set(manifest["artifacts"]) != {"firmware.bin", "protocol-core.tar.gz", "RELEASE_NOTES.md"}:
        raise SignatureError("Incomplete release artifact set")
    for name, item in manifest["artifacts"].items():
        if name not in {"firmware.bin", "protocol-core.tar.gz", "RELEASE_NOTES.md"}:
            raise SignatureError("Unsupported release artifact")
        data = (folder / name).read_bytes()
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise SignatureError("Release artifact digest mismatch")
    return record


def sign_bundle(folder, private_pem, trust, *, counter):
    folder = Path(folder)
    if trust["mode"] != "signed":
        raise SignatureError("Signing requires an explicit signed policy")
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, ec.EllipticCurvePrivateKey) or not isinstance(private.curve, ec.SECP256R1):
        raise SignatureError("Signer must use ECDSA P-256")
    der = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = public_key_id(der)
    key = next((key for key in trust["keys"] if key["id"] == key_id and not key["revoked"]), None)
    if key is None:
        raise SignatureError("Signing key is not active in the pinned trust store")
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["signature"] = {
        "status": "signed",
        "algorithm": "ecdsa-p256-sha256",
        "authorization_file": "authorization.json",
        "key_id": key_id,
        "counter": counter,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    compat = manifest["compatibility"]
    record = {
        "key_id": key_id,
        "counter": counter,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "commit": manifest["source"]["commit"],
        **{name: manifest["firmware"][name] for name in ["size", "sha256", "image_sha256", "version"]},
        **{
            name: compat[name]
            for name in ["board_profile", "board_revision", "partition_layout", "protocol_min", "protocol_max"]
        },
    }
    if compat["board_revision"] in {"", "unverified"} or counter < trust["minimum_counter"]:
        raise SignatureError("Signing requires known board revision and allowed counter")
    payload = encode_record(record)
    envelope = {
        "authorization": base64.b64encode(payload).decode(),
        "signature": base64.b64encode(private.sign(payload, ec.ECDSA(hashes.SHA256()))).decode(),
    }
    # Stage and verify before replacing the unsigned bundle metadata.
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary)
        for name in ["firmware.bin", "protocol-core.tar.gz", "RELEASE_NOTES.md"]:
            shutil.copyfile(folder / name, staged / name)
        (staged / "manifest.json").write_bytes(manifest_bytes)
        verify_bundle(staged, envelope, trust, board_revision=compat["board_revision"])
    (folder / "manifest.json").write_bytes(manifest_bytes)
    (folder / "authorization.json").write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    names = ["firmware.bin", "manifest.json", "protocol-core.tar.gz", "RELEASE_NOTES.md", "authorization.json"]
    (folder / "SHA256SUMS").write_text(
        "".join(hashlib.sha256((folder / name).read_bytes()).hexdigest() + "  " + name + "\n" for name in sorted(names))
    )
    return envelope
