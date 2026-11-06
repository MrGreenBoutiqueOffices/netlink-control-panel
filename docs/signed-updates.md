# Signed Wi-Fi updates

The panel can check GitHub Releases and install firmware itself over Wi-Fi. A Mac, NetLink, paired control session or running webserver is not required. USB remains the installation and recovery route. The host-fed bench updater remains available for diagnostics.

## On the panel

Open **Meer → Software**, tap **Controleren**, inspect the offered version and tap **Installeren**. Checks and installation are manual. The panel uses the latest published stable release from `MrGreenBoutiqueOffices/netlink-control-panel`; drafts and prereleases are excluded. Updates are refused while controls or another transfer are busy. **Annuleren** safely stops a download into the inactive slot. The installation/verification screen is not cancellable; activation keeps the existing last-working-image safeguards.

Wi-Fi can be provisioned once through USB without a bench server or pairing file:

```sh
uv run panel wifi setup --port <usb-port> --wifi-only
```

The command prompts locally for the SSID and password. Existing configurations with `--host` still work, even when that host is offline. Wi-Fi remains optional for normal USB operation.

## Activation and release signing

The repository's default `release/update-trust.json` is still `mode: bench`, with no keys and an unverified board revision. This build displays **Updatesleutel nog niet ingesteld** and does not install public releases independently. The published v0.8.0 assets are unsigned and cannot be installed through this path.

Before enabling it on a panel:

1. Confirm the physical board revision. Configure schema 1, `mode: signed`, a `minimum_counter` and up to four reviewed P-256 public keys in `release/update-trust.json`. Public-key IDs are the first 16 bytes of SHA-256 over canonical SPKI DER, encoded as lowercase hex. Keys have `id`, canonical base64 `public_key` and boolean `revoked` fields.
2. Set `PANEL_BOARD_REVISION` in the GitHub `release` environment and provision `PANEL_RELEASE_SIGNING_KEY` there as an environment secret. Keep the private key out of source and device configuration.
3. Install this initial signed-policy firmware over USB and independently verify its public policy fingerprint and board revision. A download never bootstraps its own trust.
4. Publish a subsequent release through the existing release workflow. The workflow produces `firmware.bin`, `manifest.json`, `authorization.json`, `protocol-core.tar.gz`, `RELEASE_NOTES.md` and `SHA256SUMS`. The GitHub release ID is the signed counter. A missing or mismatched signer fails the signed release job without unsigned fallback.

No production keys, secrets or device policy are provisioned by this implementation. The retained `NETLINK_PANEL_TRUST_V1|<mode>|<revision>|<policy_sha256>;` marker and `ota_policy` diagnostic identify the compiled public policy. The hash uses canonical `json.dumps(sort_keys=True, separators=(",", ":"))` policy bytes.

## Download and verification

The [latest-release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) selects one release. Its uploaded assets are fetched by immutable asset ID using the [release-assets API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset). Public access requires no GitHub token. Release publication can precede asset upload; a missing or incomplete asset set gives a visible failure and can be checked again later.

The client validates HTTPS server certificates and hostnames using the bundled USERTrust ECC and ISRG Root X1 roots. Certificate validity requires a clock; a manual check allows up to 15 seconds for SNTP. No TLS request is made without a plausible clock. The root set may need a firmware update when GitHub changes its certificate chains; there is no insecure fallback.

Only `api.github.com`, `github.com`, `release-assets.githubusercontent.com` and `objects.githubusercontent.com` are allowed, over HTTPS on the default port. Up to three redirects are followed. HTTP/1.0 requests require an explicit `Content-Length`; ambiguous framing, transfer/content encodings, oversized headers or excess data are rejected. Limits are 64 KiB for release discovery, 16 KiB for the manifest, 1 KiB for authorization and 3 MiB for firmware. Metadata requests have a 30-second total budget and firmware has 180 seconds, with bounded TLS/connect waits and no automatic retries. A four-chunk queue separates networking from the main loop so touch and USB remain responsive.

The panel verifies authorization against its embedded policy before flash access. It then verifies the exact manifest digest, source repository/commit/tag, release ID, version, firmware digests/size and hardware/protocol compatibility. Firmware bytes are streamed into the inactive application slot, using the existing byte hash, ESP image hash, chip/profile marker and image validation before activation. Protocol-core and release-note assets are not installed on the panel.

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

## Persistent attempt and candidate boot

One CRC-protected NVS record stores attempt identity, expected image hash/version, phase and outcome. The record is committed before starting flash and before activation. Failed persistence prevents activation. Routine updates do not replace NVS, the bootloader or partition table.

A network interruption aborts the inactive-slot handle and records a failed outcome. After power loss during downloading, the next boot records an interrupted attempt. Checking and installing again revalidates the release and starts at byte zero; a flash handle is never reused across a reboot. Only one attempt owns flash, and control messages cannot interrupt an independent update.

After activation, the panel reconciles the actual running hash and OTA state with the stored candidate. A matching candidate must pass local display/touch startup checks continuously for three seconds before the panel marks it VALID. Wi-Fi, a host handshake and `ota_confirm` are not prerequisites. The existing 90-second rollback timer remains armed until confirmation. On rollback, the restored image records and displays **Vorige firmware hersteld**. Update success and interrupted/failed outcomes are also shown locally after restart.

## Bench tools and key rotation

The diagnostic host route still supports:

```sh
uv run panel wifi update --release-bundle <downloaded-assets> --trusted-keys <pinned-public-policy.json> --board-revision <verified-revision>
```

That route retains paired TLS delivery and host confirmation. A signed policy rejects the legacy unsigned `ota_begin` operation. Bench builds explicitly advertise `bench_unsigned`; they are not production trust.

For planned rotation, deploy an A-signed A+B policy before a B-signed B-only policy. The running panel must already trust the signer. A minimum counter is an embedded floor, not an automatically persisted highest-installed counter. Older correctly signed releases above that floor remain permitted. Rollback can restore old policies; this mechanism does not provide permanent revocation, hardware antirollback, expiry/freeze protection, Secure Boot or physical-write protection.

## Validation boundary

Native tests run the actual updater, OTA handler and pinned mbedTLS verifier with ephemeral signing keys and fake network/NVS/flash boundaries. They cover independent success without network during boot confirmation, rejected signatures/manifests, unsigned releases, busy admission, storage/flash failures, interruption, restart from byte zero, rollback and unhealthy startup. Firmware compilation verifies the ESP32 transport integration. These checks do not establish physical Wi-Fi timing, power-loss recovery or rollback on the display. Those remain the hardware acceptance for #14, #15 and #16.
