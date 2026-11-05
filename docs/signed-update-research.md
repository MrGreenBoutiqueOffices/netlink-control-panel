# Signed panel updates: research for #15

Researched on 2026-11-05. This document records source research before implementation; the current implementation and remaining boundaries are in [signed updates](signed-updates.md). The research itself changed no production keys or hardware.

## Conclusion

For the existing toolchain, use **ECDSA P-256 with SHA-256**, an embedded public key set and a small separately signed OTA authorization record. Verify on both host and panel. The panel must do so before `anchorRunning()` and `esp_ota_begin()`. Retain all existing image, hash, slot, rollback and startup checks afterwards. Signed updates here are application policy: they provide no Secure Boot, physical protection, permanent revocation or hardware anti-rollback.

## Established baseline

The repository pins Arduino ESP32 package `3.20014.231204` and ArduinoJson `6.21.5` in `firmware/platformio.ini`. Espressif confirms Arduino ESP32 2.0.14 is based on ESP-IDF 4.4.6. The installed package identity matches that pin. [Arduino release](https://github.com/espressif/arduino-esp32/releases/tag/2.0.14)

Local source inspection: `firmware/src/panel_ota.cpp` currently accepts sender-provided SHA-256, version and profile, but no release signature. `scripts/release_artifacts.py` produces an explicitly unsigned manifest with `board_revision: unverified`; `SHA256SUMS` is integrity metadata, not a trust anchor. `host/netlink_panel/ota.py` inspects raw image bytes and sends that metadata to `ota_begin`. The new managed path therefore needs a separate entry point requiring a verified release bundle.

`host/netlink_panel/protocol.py` limits JSON frames to 1024 bytes excluding newline; `firmware/src/frame_writer.h` has the same limit. `firmware/src/ota_policy.h` and the host use 512-byte chunks, at most 684 base64 characters. The existing `StaticJsonDocument<1536>` receive path does not prove every new 1024-byte frame also fits its JSON arena. Measure both limits separately.

## Exact SDK and cryptographic API

The ESP-IDF 4.4.6 GitHub tree references mbedTLS commit `1d7033af30e20ccb2a0c0a114d3a08e372430f34`; its header identifies mbedTLS 2.28.4. This is also the version in locally installed ESP32-S3 headers. [Exact submodule reference](https://api.github.com/repos/espressif/esp-idf/contents/components/mbedtls/mbedtls?ref=v4.4.6), [version header](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/version.h)

The Arduino 2.0.14 ESP32-S3 `qio_opi` configuration enables `CONFIG_MBEDTLS_ECDSA_C`, `CONFIG_MBEDTLS_ECP_DP_SECP256R1_ENABLED` and PEM parsing. These values were also found locally. This supports implementation with the existing library; add compile-time guards and a compile/link trial for the actual board configuration. Do not merely change an sdkconfig macro against a prebuilt library. [Pinned sdkconfig](https://github.com/espressif/arduino-esp32/blob/2.0.14/tools/sdk/esp32s3/qio_opi/include/sdkconfig.h)

A suitable panel path is `mbedtls_pk_init`, `mbedtls_pk_parse_public_key`, explicit EC key type and `MBEDTLS_ECP_DP_SECP256R1` checks, then SHA-256 of the exact payload bytes and `mbedtls_pk_verify(&ctx, MBEDTLS_MD_SHA256, digest, 32, signature, signature_len)`. Accept only return value zero and free resources on every path. The verify argument is already a digest; do not hash it again. [Exact pk.h API](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/pk.h)

Use DER SubjectPublicKeyInfo for public keys, or PEM `PUBLIC KEY` around the same structure. DER length is exact; PEM length for `mbedtls_pk_parse_public_key` includes the terminating NUL. Trust only provisioned key bytes: an included public key or key ID establishes no trust. The header also describes key-type checks; a parser may support multiple key types.

ECDSA signatures are ASN.1 `SEQUENCE(INTEGER r, INTEGER s)`, not fixed 64-byte `r || s`. P-256 needs at most 72 DER bytes, hence at most 96 base64 characters. The exact mbedTLS implementation checks the sequence boundary and two integers and returns errors for trailing bytes. This is not a general canonical-DER guarantee for every possible BER variant; specify canonical DER and explicitly test negative/non-minimal integers, truncation and trailing bytes, adding a small strict encoding check before the library if needed. [Exact ECDSA parser](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/library/ecdsa.c)

Ed25519 requires another implementation or toolchain change in this SDK. The 2.28.4 ECP/PK interfaces have no EdDSA/Ed25519 key type; existing Curve25519 is a Montgomery curve, not an Ed25519 signature API. ECDSA source also explicitly excludes Curve25519. P-256 is therefore the smallest change within the current pin. [Curve API 2.28.4](https://github.com/Mbed-TLS/mbedtls/blob/v2.28.4/include/mbedtls/ecp.h), [exact PK types](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/pk.h)

## Proposed exact byte contract

The contract below is a proposal to finalize once before implementation with shared golden vectors. It avoids JSON canonicalization entirely. Do not sign reserialized JSON objects or implicitly use Python `sort_keys=True` as a cross-language standard.

Create `ota-authorization.bin` as consecutive bytes, with no padding or implicit terminators:

| Order | Encoding |
| --- | --- |
| Domain | Exact ASCII `NETLINK-PANEL-OTA` followed by one NUL byte |
| Format | One byte `0x01`; this format fixes ECDSA-P256-SHA256, no arbitrary algorithm choice |
| Key ID | 16 bytes: first 16 bytes of SHA-256 of DER SPKI; collision check in the embedded keyring |
| Release sequence number | Unsigned 64-bit big-endian |
| Protocol minimum, maximum | Two unsigned 16-bit big-endian integers |
| Firmware file size | Unsigned 32-bit big-endian |
| Firmware SHA-256 | Exactly 32 bytes of the complete `firmware.bin` |
| ESP image SHA-256 | Exactly 32 bytes using the existing image-inspection/partition-hash semantics |
| Release manifest SHA-256 | Exactly 32 bytes of published `manifest.json` bytes |
| Source commit | Exactly 20 bytes of the Git commit ID |
| Version, board profile, board revision, partition layout | Each one unsigned length byte followed by exactly that many ASCII bytes; at most 31, 64, 32, 32 bytes respectively |

All strings are required and nonempty, only `[A-Za-z0-9._:-]`, with field-specific allowlists where possible. Wrong lengths, unknown format, out-of-range values and trailing bytes fail. The old `profile` can be derived unambiguously from board profile, protocol and partition layout; do not retain it as a second unprotected authority. Bind compatibility to known local properties, not merely echoed host values.

The signer signs `ota-authorization.bin` directly with ECDSA/SHA-256 and writes detached canonical DER to `ota-authorization.sig`. Hash the entire release JSON as exact bytes: whitespace changes require resigning. Keep signature files and their own digests outside this manifest to avoid a cycle. The host checks both this manifest digest and every listed artifact digest; authorizing panel fields come only from the verified binary record. A signature over a manifest digest does not prove the offered firmware belongs to that manifest without these binding checks.

Transport proposal: one new `ota_begin_signed` with base64 `authorization` and `signature`, alongside the existing v2 session/id envelope. Maximum payload from these field limits is below 340 bytes; base64 stays below 456 characters. With at most 96 signature characters, bounded envelope fields fit within 1024 bytes. Verify using the actual encoder, maximum session/id/fields and ArduinoJson arena; do not send the expanded release manifest to the panel. Decode base64 strictly with bounds. Never trust an outer `key_id`, `size`, `profile` or `version` alongside the signed record.

ArduinoJson mutates writable zero-copy input and may replace escapes; therefore hash only the owned decoded binary buffer, never the input buffer after JSON parsing. This keeps the byte contract independent of object order, whitespace, Unicode escapes or duplicate JSON members. [ArduinoJson 6 input semantics](https://arduinojson.org/v6/api/json/deserializejson/)

## Preflight and legacy boundary

1. Host: load only a release bundle, verify the record against a pinned public keyring and check exact manifest/artifact digests, size, version, release sequence number and known hardware compatibility before network contact.
2. Panel: decode and verify with bounds; check trust/key policy, local board revision, protocol, partition layout and size before any mutation, including `anchorRunning()` and before `esp_ota_begin`. All unknown, missing or `unverified` board revisions fail closed on the managed path. Host claims do not establish an unknown physical board revision.
3. Bind resume to the digest of the complete verified record, not just size/image hash. Verify authorization again at begin/resume and retain the valid record in RAM with the transfer.
4. Retain byte hash, image hash, magic/chip/profile marker, image validation, boot-slot selection and existing pending/confirm/rollback. ESP-IDF documents that `esp_ota_begin` erases flash and application rollback is a separate mechanism. [OTA API 4.4.6](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html)
5. Old `ota_begin` and the bench CLI must not remain an unsigned bypass on managed firmware. An explicitly separate bench build may allow unsigned with visible capability/status and explicit bench selection; no automatic fallback after signature failures, missing keys, old panel capabilities or unknown board revision. A paired or TLS host does not replace panel verification either.

## Python signer/verifier and evidence

The normal API is `private_key.sign(payload, ec.ECDSA(hashes.SHA256()))` and `public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))`; output is DER and invalid signatures raise `InvalidSignature`. For precomputed digests, use only `utils.Prehashed(hashes.SHA256())`. Avoid optional deterministic-signing features that needlessly require another library/backend version. [cryptography ECDSA API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/)

Load an external signer key with `serialization.load_pem_private_key`, public verification keys with `load_der_public_key`/`load_pem_public_key`; check EC type and `SECP256R1` each time. SPKI serialization is `public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)`. Only the signer environment accesses private keys; host and panel contain public keys only. This research generated no keys or signatures. [cryptography key serialization](https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/)

Implementation evidence with clearly marked test keys must demonstrate: Python sign → firmware mbedTLS verify and host verify; every payload, signature and firmware bit mutation fails; wrong algorithm/curve/key, unknown key ID, revoked key, unknown board revision, wrong layout/protocol, missing authorization and unsigned fallback fail before a mock `esp_ota_begin`. Add format bounds, malformed ASN.1/base64, duplicate outer fields, recovery after failure, resume with different authorization and maximum frame. Source/header research is not compile/link, interoperability, timing/heap or physical OTA evidence.

## Trust, rotation and remaining limitations

Provision the first public keyring through a controlled initial USB/factory installation and verify the fingerprint outside the download channel. Never trust on first use from a release file. Choose key management and recovery procedures beforehand; a key ID is a lookup, not authorization.

A limited initial version can offer keyring updates only through firmware authorized by an existing key: deploy A+B first, confirm migration, then remove A. Reserve an independently managed recovery/root key if compromise recovery is required; a compromised sole release key can sign a malicious rotation itself. TUF explicitly specifies previously trusted root metadata, versioned roots and verification under both old and new root thresholds. This proposal does not implement TUF or claim its protection. [TUF root loading/updating and key management](https://theupdateframework.github.io/specification/latest/#detailed-client-workflow)

A software denylist or minimum release counter is only as trustworthy as the firmware and storage enforcing it. Old correctly signed firmware or a rollback slot can restore old keys/policy; NVS reset, physical flashing or a compromised signer can undermine this foundation. Without reliable time, expiry/freeze guarantees are not automatic either. Do not claim permanent revocation or anti-rollback guarantees yet.

ESP32-S3 Secure Boot V2 in IDF 4.4.6 uses RSA-3072/PSS with eFuse trust, not this application P-256 record. Signed-app verification without hardware Secure Boot is also a separate Espressif path. This proposal changes no bootloader/eFuse policy and does not protect against physical reprogramming. [Secure Boot V2 4.4.6 and signed-app verification](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/security/secure-boot-v2.html)

Open decisions before implementation: known board-revision provisioning; who verifies offline trust bootstrap; signer/owner/storage and recovery key; admission policy for older signed releases; atomic policy storage and power-loss recovery; maximum envelope fields; test keys and concrete interoperability vectors. Keep production key provisioning, CI secrets, release signing and physical acceptance as separate explicit steps.
