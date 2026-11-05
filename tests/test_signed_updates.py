"""Ephemeral-key interoperability and denial-before-flash coverage."""

import base64
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from netlink_panel.ota import OTAError, update, upload
from netlink_panel.signed_updates import (
    SignatureError,
    decode_record,
    encode_record,
    load_trust,
    public_key_id,
    sign_bundle,
    verify_authorization,
    verify_bundle,
)
from test_ota import image_fixture
from test_ota_firmware_resume import STUB
from test_release_artifacts import ROOT, VERSION, release


def key_fixture():
    private = ec.generate_private_key(ec.SECP256R1())
    der = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key = {"id": public_key_id(der), "public_key": base64.b64encode(der).decode(), "revoked": False}
    return private, der, {"schema": 1, "mode": "signed", "minimum_counter": 10, "keys": [key]}


def record_fixture(trust):
    return dict(
        key_id=trust["keys"][0]["id"],
        counter=10,
        protocol_min=2,
        protocol_max=2,
        size=1024,
        sha256="a" * 64,
        image_sha256="b" * 64,
        manifest_sha256="c" * 64,
        commit="d" * 40,
        version=VERSION,
        board_profile="lilygo-s3-long-cst3530",
        board_revision="test-rev1",
        partition_layout="ota3m-v1",
    )


def envelope(private, record):
    payload = encode_record(record)
    return {
        "authorization": base64.b64encode(payload).decode(),
        "signature": base64.b64encode(private.sign(payload, ec.ECDSA(hashes.SHA256()))).decode(),
    }


class SignedUpdatesTests(unittest.TestCase):
    def test_host_rejects_mutations_revocation_compatibility_and_noncanonical_input(self):
        private, _, trust = key_fixture()
        record = record_fixture(trust)
        signed = envelope(private, record)
        self.assertEqual(verify_authorization(signed, trust, board_revision="test-rev1"), record)
        for name, value in [
            ("counter", 9),
            ("board_revision", "other"),
            ("board_profile", "other"),
            ("partition_layout", "other"),
            ("protocol_min", 3),
            ("key_id", "0" * 32),
        ]:
            changed = {**record, name: value}
            if name == "protocol_min":
                changed["protocol_max"] = 3
            with self.subTest(name=name), self.assertRaises(SignatureError):
                verify_authorization(envelope(private, changed), trust, board_revision="test-rev1")
        bad_trust = copy.deepcopy(trust)
        bad_trust["keys"][0]["revoked"] = True
        for policy, revision in [
            (bad_trust, "test-rev1"),
            (trust, "unverified"),
            ({**trust, "keys": []}, "test-rev1"),
            ({**trust, "mode": "bench"}, "test-rev1"),
        ]:
            with self.assertRaises(SignatureError):
                verify_authorization(signed, policy, board_revision=revision)
        for field in ["authorization", "signature"]:
            for value in [
                signed[field] + "=",
                "!",
                "A" * 2000,
                base64.b64encode(base64.b64decode(signed[field]) + b"\0").decode(),
            ]:
                with self.subTest(field=field, value=value[:15]), self.assertRaises(SignatureError):
                    verify_authorization({**signed, field: value}, trust, board_revision="test-rev1")
        data = bytearray(base64.b64decode(signed["authorization"]))
        data[60] ^= 1
        with self.assertRaises(SignatureError):
            verify_authorization(
                {**signed, "authorization": base64.b64encode(data).decode()}, trust, board_revision="test-rev1"
            )
        for length in range(len(data)):
            with self.assertRaises(SignatureError):
                decode_record(bytes(data[:length]))

    def test_planned_key_overlap_and_removal(self):
        a, _, policy_a = key_fixture()
        b, _, policy_b = key_fixture()
        overlap = {**policy_a, "keys": policy_a["keys"] + policy_b["keys"]}
        signed_a = envelope(a, record_fixture(policy_a))
        signed_b = envelope(b, record_fixture(policy_b))
        for signed in [signed_a, signed_b]:
            verify_authorization(signed, overlap, board_revision="test-rev1")
        verify_authorization(signed_b, policy_b, board_revision="test-rev1")
        with self.assertRaises(SignatureError):
            verify_authorization(signed_a, policy_b, board_revision="test-rev1")
        wrong = (
            ec.generate_private_key(ec.SECP384R1())
            .public_key()
            .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        )
        wrong_policy = {
            **policy_a,
            "keys": [{"id": public_key_id(wrong), "public_key": base64.b64encode(wrong).decode(), "revoked": False}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trust.json"
            path.write_text(json.dumps(wrong_policy))
            with self.assertRaisesRegex(SignatureError, "P-256"):
                load_trust(path)

    def test_signed_sender_never_uses_unsigned_begin_and_preflight_is_offline(self):
        class Peer:
            def __init__(self):
                self.requests = []

            def request(self, kind, **fields):
                self.requests.append((kind, fields))
                return {"next_offset": fields.get("offset", -512) + 512}

        peer = Peer()
        authorization = {"authorization": "record", "signature": "signature"}
        upload(peer, b"x" * 512, {}, authorization=authorization)
        self.assertEqual(peer.requests[0], ("ota_begin_signed", authorization))
        self.assertEqual([kind for kind, _ in peer.requests], ["ota_begin_signed", "ota_chunk"])
        with tempfile.TemporaryDirectory() as temporary, patch("socket.socket") as socket:
            args = SimpleNamespace(timeout=600, release_bundle=Path(temporary), trusted_keys=None, board_revision=None)
            with self.assertRaisesRegex(OTAError, "requires"):
                update(args)
            socket.assert_not_called()

    def test_trust_loading_and_no_implicit_bench_promotion(self):
        _, _, trust = key_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trust.json"
            path.write_text(json.dumps(trust))
            self.assertEqual(load_trust(path), trust)
            for policy in [
                {**trust, "mode": "bench"},
                {**trust, "keys": trust["keys"] * 2},
                {**trust, "minimum_counter": True},
                {**trust, "keys": [{**trust["keys"][0], "id": "0" * 32}]},
            ]:
                path.write_text(json.dumps(policy))
                with self.assertRaises(SignatureError):
                    load_trust(path)

    def test_bundle_signing_rechecks_image_policy_and_all_artifacts(self):
        private, _, trust = key_fixture()
        digest = hashlib.sha256(json.dumps(trust, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        marker = f"NETLINK_PANEL_TRUST_V1|signed|test-rev1|{digest};".encode()
        # Build a valid ESP fixture with the compiled trust marker in its segment.
        import struct

        image = bytearray(image_fixture(version=VERSION))
        payload = bytearray(image[32:-32])
        payload = payload[: struct.unpack_from("<I", image, 28)[0]]
        payload.extend(marker)
        payload.extend(b"\0" * (-len(payload) % 4))
        image = image[:32]
        struct.pack_into("<I", image, 28, len(payload))
        image.extend(payload)
        checksum = 0xEF
        for value in payload:
            checksum ^= value
        image.extend(b"\0" * ((len(image) | 15) - len(image)))
        image.append(checksum)
        image.extend(hashlib.sha256(image).digest())
        pem = private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            firmware = folder / "input.bin"
            firmware.write_bytes(image)
            bundle = folder / "bundle"
            with patch.dict("os.environ", {"PANEL_BOARD_REVISION": "test-rev1"}):
                release.package(ROOT, firmware, bundle, "1" * 40)
            signed = sign_bundle(bundle, pem, trust, counter=10)
            verify_bundle(bundle, signed, trust, board_revision="test-rev1")
            self.assertEqual(len(list(bundle.iterdir())), 6)
            notes = bundle / "RELEASE_NOTES.md"
            notes.write_bytes(notes.read_bytes() + b"changed")
            with self.assertRaises(SignatureError):
                verify_bundle(bundle, signed, trust, board_revision="test-rev1")
            notes.write_bytes(notes.read_bytes()[:-7])
            manifest = bundle / "manifest.json"
            manifest.write_bytes(manifest.read_bytes() + b" ")
            with self.assertRaises(SignatureError):
                verify_bundle(bundle, signed, trust, board_revision="test-rev1")

    def test_real_mbedtls_and_actual_handler_deny_before_flash_and_bind_resume(self):
        private, der, trust = key_fixture()
        record = record_fixture(trust)
        valid = envelope(private, record)
        variants = [valid]
        for name, value in [
            ("board_revision", "other"),
            ("counter", 9),
            ("key_id", "0" * 32),
            ("partition_layout", "other"),
            ("protocol_min", 3),
        ]:
            changed = {**record, name: value}
            if name == "protocol_min":
                changed["protocol_max"] = 3
            variants.append(envelope(private, changed))
        corrupt = {**valid, "signature": base64.b64encode(base64.b64decode(valid["signature"])[:-1]).decode()}
        variants.append(corrupt)
        wrong_private, _, _ = key_fixture()
        variants.append(envelope(wrong_private, record))
        variants.append({**valid, "signature": base64.b64encode(base64.b64decode(valid["signature"]) + b"\0").decode()})
        variants.append({**valid, "authorization": valid["authorization"] + "="})
        other = envelope(private, {**record, "commit": "e" * 40})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "stub.h").write_text(STUB)
            for header in [
                "Arduino.h",
                "esp_ota_ops.h",
                "esp_timer.h",
                "sdkconfig.h",
                "esp_app_format.h",
                "mbedtls/sha256.h",
                "mbedtls/base64.h",
            ]:
                path = directory / header
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#include "stub.h"\n')
            arrays = f"const uint8_t der[]={{{','.join(str(c) for c in der)}}};\nconst uint8_t id[]={{{','.join(str(c) for c in bytes.fromhex(record['key_id']))}}};\n"
            frames = [json.dumps({"type": "ota_begin_signed", "id": 1, **item}) for item in variants + [other]]
            self.assertTrue(all(len(frame.encode()) < 1024 for frame in frames))
            program = (
                """#include "panel_ota.h"
#include <cassert>
#include <string>
unsigned begins=0,writes=0,aborts=0,clockMs=100;
"""
                + arrays
                + """int main() {
UpdateKey key{id,der,sizeof(der),false}; UpdatePolicy policy{true,"test-rev1",2,10,&key,1};
PanelOta ota(policy);ota.bootStart();
StaticJsonDocument<512> boot;ota.describe(boot.to<JsonObject>());assert(!boot.overflowed());
StaticJsonDocument<2048> hello;
assert(!deserializeJson(hello,R"({"v":1,"type":"hello","id":2147483647,"panel_id":"panel-ffffffffffff","firmware":"1234567890123456789012345678901","simulated":false,"display_ready":true,"transport":"wifi","capabilities":["demo_state","wifi_provision","tls_psk","ota_v1","ota_resume_v1","demo_ui_v1","frame_snapshot_v1"],"self_test_ok":true,"uptime_ms":4294967295,"reset_reason":12,"wifi":{"last_disconnect_reason":65535,"configured":true,"connected":true,"ip":"255.255.255.255","rssi":-127}})"));
ota.describe(hello["ota"].to<JsonObject>());assert(!hello.overflowed());assert(measureJson(hello)+1<=1024);
StaticJsonDocument<1536> m;StaticJsonDocument<512> r;
auto call=[&](const char *frame){m.clear();r.clear();assert(!deserializeJson(m,frame));assert(!m.overflowed());ota.handle(m,r,true);};
call("{\\"type\\":\\"ota_begin\\"}");assert(r["ok"]==false && begins==0);
"""
            )
            for frame in frames[1:-1]:
                program += "call(" + json.dumps(frame) + ');assert(r["ok"]==false && begins==0 && aborts==0);\n'
            program += "call(" + json.dumps(frames[0]) + ');assert(r["ok"]==true && begins==1);\n'
            for frame in frames[1:]:
                program += (
                    "call("
                    + json.dumps(frame)
                    + ');assert(r["ok"]==false && ota.receiving() && begins==1 && aborts==0);\n'
                )
            program += "call(" + json.dumps(frames[0]) + ');assert(r["ok"]==true && begins==1);\n'
            program += (
                """key.revoked=true;call("""
                + json.dumps(frames[0])
                + """);assert(r["ok"]==false && begins==1 && aborts==0);
return 0;}
"""
            )
            (directory / "signed.cpp").write_text(program)
            subprocess.run(
                [
                    shutil.which("c++"),
                    "-std=c++11",
                    "-I",
                    str(directory),
                    "-I",
                    str(ROOT / "firmware/src"),
                    "-I",
                    str(ROOT / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"),
                    "-I",
                    str(ROOT / "firmware/.vendor/mbedtls/include"),
                    str(directory / "signed.cpp"),
                    str(ROOT / "firmware/src/panel_ota.cpp"),
                    str(ROOT / "firmware/src/signed_update.cpp"),
                    str(ROOT / "firmware/.vendor/mbedtls/build/library/libmbedcrypto.a"),
                    "-o",
                    str(directory / "signed"),
                ],
                check=True,
                capture_output=True,
            )
            result = subprocess.run([str(directory / "signed")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
