# Signed updates — first part of #15

This implementation adds independent release authorization to existing Wi-Fi bench OTA. Host and panel verify the same ECDSA P-256/SHA-256 signature. Independent downloading and installation over Wi-Fi is the goal of #15; it is not implemented yet. The current bench route requires a host for delivery and boot confirmation. Panel-owned update lifecycle, download client, local controls, persistent attempt records and boot confirmation without a host remain open. Physical full-image OTA acceptance remains #14.

## Trust and build

`release/update-trust.json` is the explicit, reviewed public build policy. The default is `mode: bench`, with no keys and minimum counter 0. The handshake reports `bench_unsigned`; this prototype build accepts the existing unsigned update start. It does not present itself as a signed managed panel.

For a signed build, the policy contains schema 1, `mode: signed`, a `minimum_counter` (uint64) and at most four public keys. A key contains `id` (the first 16 bytes of SHA-256 over canonical SPKI DER, lowercase hex), `public_key` (canonical base64 of P-256 SPKI DER) and boolean `revoked`. The private key never belongs here. The build rejects invalid or duplicate keys, other curves and invalid counters. `PANEL_BOARD_REVISION` is a controlled build input of at most 32 ASCII identifier characters; if absent, it remains `unverified`.

The generated public policy and board revision are compiled into the application. A retained `NETLINK_PANEL_TRUST_V1|<mode>|<revision>|<policy_sha256>;` marker identifies the canonical public policy (`json.dumps(sort_keys=True, separators=(",", ":"))`). Signer and host check that this marker matches their public policy. The marker can be queried using the separate `ota_policy` diagnostic request, keeping the normal handshake within its existing frame. A running panel's local verification policy is not replaced by fields from a download.

A signed policy always rejects `ota_begin`. Unknown board revision, missing/revoked keys or invalid signatures make signed updates unavailable; they do not fall back to unsigned. Initial known board revision and public trust must be provisioned through a controlled USB/factory installation and verified independently. This PR does not do that and contains no production keys.

## Signed bytes

`authorization.json` has exactly two fields, `authorization` and `signature`. Both are canonical base64. The signature is canonical ASN.1 DER ECDSA, at most 72 bytes, over the exact record bytes with SHA-256. JSON canonicalization is not part of the wire protocol.

| Record field in order | Encoding |
| --- | --- |
| Domain/version | ASCII `NETLINK-PANEL-OTA`, followed by `00 01` |
| Key ID | 16 raw bytes |
| Release counter | uint64 big endian, at least 1 |
| Protocol minimum / maximum | Each uint16 big endian, inclusive |
| Firmware length | uint32 big endian, 288 through 0x300000 |
| Firmware file SHA-256 | 32 bytes |
| ESP image SHA-256 | 32 bytes |
| Exact `manifest.json` SHA-256 | 32 bytes |
| Source commit | 20 bytes |
| Version / board profile / board revision / partition layout | Each one length byte and ASCII `[A-Za-z0-9._:-]+`; at most 31/64/32/32 bytes respectively |

Trailing bytes and invalid lengths are rejected. The decoder limits records to 340 bytes; requests fit the existing 1024-byte frame and ArduinoJson arena. The known combination is board profile `lilygo-s3-long-cst3530`, layout `ota3m-v1`, protocol 2. The firmware version marker also remains subject to existing image checks.

Before network contact, the host verifies signature, exact manifest bytes, image integrity, version, source commit, compatibility and the three required artifact digests. The panel verifier checks record, key, board revision, protocol, layout, length and minimum counter before `anchorRunning()` or `esp_ota_begin()`. The full record digest binds resume; another authorization for the same image cannot take over an active transfer. Rejected authorization does not abort that transfer.

Existing chunk, file-hash, ESP-image-hash, profile, slot and pending/confirm/VALID checks remain active afterwards. Only application slots are written; NVS, bootloader and partition table are outside routine OTA.

## Release and host usage

The existing `release.published` job in environment `release` retains ownership of assets. Deliberate activation requires:

- The reviewed signed public policy in the release tag.
- Confirmed `PANEL_BOARD_REVISION` as a GitHub environment variable (`vars`).
- Private P-256 PEM as environment secret `PANEL_RELEASE_SIGNING_KEY`, available only in the signing step.

The GitHub release ID becomes the release counter. `scripts/sign_release.py` first signs in a temporary staging directory and validates the bundle there. It then writes signed manifest metadata, `authorization.json` and updated `SHA256SUMS`. Signed releases have six assets. Missing secret with signed policy, wrong key, unknown board revision or mismatched firmware policy fails the release job; there is no unsigned fallback. PR CI receives no private key. The default bench policy without a secret continues to produce five explicitly unsigned assets.

The existing prototype supports:

```sh
uv run panel wifi update --release-bundle <downloaded-assets> --trusted-keys <pinned-public-policy.json> --board-revision <verified-revision>
```

The public policy must be trusted beforehand; do not take it from the same firmware download without independent verification. All required assets must be present. A panel must report signed-required and the same board revision. The host prototype does not fall back to the old unsigned start if signed preflight or panel verification fails. Existing pairing/TLS authentication is also still required.

This is the current bench CLI; it supplies bytes and confirms boot. This implementation cannot yet independently download a release or confirm a candidate boot without a host. Future ownership is described below.

## Decision: the panel owns its updates

Decided on 2026-11-05: the panel must independently fetch, install and assess a signed release over Wi-Fi. It needs only power, configured Wi-Fi and access to the update source. A Mac, NetLink, paired control session or running webserver is not a prerequisite. Wi-Fi remains optional for normal USB operation; independent wireless updates do require Wi-Fi. USB remains available for installation and recovery. Webserver integration, central rollout orchestration and routine host-fed updates are outside #15. The webserver retains its existing desk/monitor control role.

| Component | Responsibility in the target design |
| --- | --- |
| Panel firmware | One update state machine, admission/idle, release verification, Wi-Fi download, slot selection, progress/outcome, candidate boot, local self-check, VALID and rollback |
| Release workflow | Produce the same signed manifests, authorization and firmware assets; never directly flash a panel |

The first independent user flow is on the panel: check for an update, show version/status and explicitly start installation. Automatic checking or rollout is separate policy and is not enabled by default here. Current pairing is for the host bench route; future independent download must not require a paired host.

The download client first fetches the bounded manifest and authorization, verifies the independent release signature against already embedded public trust and checks board revision, version, protocol, layout, length and counter before erasing or writing flash. The firmware stream is bounded and hashed before activation. HTTPS must validate server identity; redirects, retry budget, time limits and maximum download size must be bounded. Source outage must not cause unsigned fallback or an endless restart loop. The actual source, channel selection and any access mechanism remain to be specified. A private GitHub repository does not automatically make assets reachable by a panel; no long-lived GitHub token is embedded in firmware and no public mirror is implicitly created. Published assets remain the distribution source.

The panel enforces one active update attempt, requires idle controls and blocks conflicting actions until completion or safe abort. A second update request gets a busy result and cannot take over an ongoing attempt. This admission policy is enforced locally.

The panel persistently stores attempt identity, authorized expected image, phase and outcome. After power loss or panel restart, actual slot/boot state is reconciled against that attempt before admitting a new one. An existing flash handle does not survive reboot: resuming or deliberately restarting the inactive slot must be explicitly implemented and tested. Existing settings and the last working image must be preserved.

A new boot checks expected image and startup health locally, then explicitly confirms VALID itself. A Mac, new host handshake or working webserver must not be necessary to retain a healthy candidate. Local self-checks and network reachability are separate signals. Invalid image, failed self-check or expired confirmation deadline still lead to rollback. The current host-driven `ota_confirm` route must still be adapted; the signing foundation from PR #32 does not provide this behavior. The panel displays the stored outcome locally. The existing handshake applies to later normal controls; it does not confirm an update.

## Remaining acceptance for #15

- Independent Wi-Fi trial with power only and no Mac, NetLink or webserver: check, download, install, restart, confirm VALID locally and display the outcome from the panel.
- Independent downloads enforce embedded verification and installation policy; invalid signature, wrong hardware/protocol and conflicting attempts are rejected.
- Network interruption, source outage, power loss, panel restart and self-check failure produce a bounded visible outcome; rollback and settings preservation are physically demonstrated.
- Production trust, known board revision, key management and reachable distribution source are provisioned under control. #14 remains the physical full-image/recovery gate; #9 is not a dependency of this update feature.

## Rotation and limitations

For planned rotation: start with A, deploy an A-signed A+B policy, confirm migration, then deploy a B-signed B policy with A removed or revoked. The host pin is deliberately updated to the expected candidate policy; the running panel must already trust the signer. Release counters below the embedded floor are rejected. The floor is not an automatically stored highest installed version: older valid releases above it remain allowed.

Rollback can restore an older key policy. This mechanism provides no permanent revocation, hardware antirollback, expiry/freeze protection, Secure Boot or protection against physical reprogramming. A compromised sole signer can sign a bad release or rotation. Production key ownership, secure storage, independent recovery and policy acceptance must be explicitly arranged before use.

## Evidence and open acceptance

Tests use only ephemeral keys. Python signatures are verified natively with the actual pinned mbedTLS 2.28.4 source from the SDK used; the actual `PanelOta` handler runs with fake SDK flash calls. Tests check rejection before flash, no unsigned bypass, revoked keys, changed authorization, wrong board/protocol/layout/counter, format bounds, artifact mutation and resume with only the same authorization. `scripts/prepare_crypto_tests.py` fetches the exact source with SHA-256 verification and builds only the native test library; production uses the PlatformIO/ESP-IDF library.

Compilation and native tests do not establish cryptographic timing/heap margins on the display, independent Wi-Fi lifecycle or physical recoverability. No panel was flashed and no production key was created, installed or read for this change. See [research sources](signed-update-research.md) and the [release procedure](releases.md).
