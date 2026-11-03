# Bench results

Date: 2026-11-03. Initial preparation had no connected hardware; see the physical-installation record below for subsequent measurements.

## Acceptance record

| Check | Status |
| --- | --- |
| Serial host session against pseudo-terminal simulator | Passed |
| Silence produces a timeout instead of success | Passed |
| Fragmented/combined frames, boot logs, invalid versions and IDs, oversized input | Passed |
| Firmware compilation | Passed: PlatformIO panel-bench build in the final project folder |
| Interactive browser preview | Passed: touch feedback and disconnect disables all panel buttons |
| Board revision and flash identity | ESP32-S3 rev 0.2, 16 MB flash, 8 MB PSRAM measured; physical board revision unverified |
| Physical display/touch/USB behavior | USB and Wi-Fi bench passed; user sees IP/status; touch coordinates pending |
| Remote update and unattended recovery | Physical full updates, automatic TLS-loss resume and confirmed 0.3.3 boot passed; unconfirmed-boot rollback measured earlier; electrical power-loss acceptance pending |
| Optional Wi-Fi | Actual paired TLS sessions, reconnect and interrupted-transfer recovery passed; AP/power-loss and multi-day stability pending |
| Real bureau/monitor commands | Intentionally absent from bench prototype |

Run the documented tests again after modifying the prototype. Update physical acceptance entries only from observed evidence on the identified board.

## Build evidence

- Target: ESP32-S3, manufacturer T-Display-Long board definition.
- PlatformIO 6.1.18, espressif32 6.5.0, Arduino core 2.0.14, ArduinoJson 6.21.5.
- Upstream manufacturer revision: `3deece89098f25e7d155e41e4e0f5dd8b368ab02`.
- Six Python tests passed; the five-second CLI simulator session passed with ten received heartbeats and no rejected frames.
- Ruff checks and formatting passed.
- Firmware program size: 328853 bytes; static RAM: 29284 bytes. These are compiler figures, not measured running memory or power use.
- The manufacturer libraries/framework emit warnings; the firmware links and produces an ESP32-S3 image successfully.
- Binary: `firmware/.pio/build/panel-bench/firmware.bin`, 329216 bytes, SHA-256 `298baa0cb3d112f58d351aa86b5f8aa24747fc9516528e9c0c4d2e6b57c03f6f`.
- No flashing, physical input/output, firmware update, or recovery acceptance has taken place.

## Wi-Fi bench update, 2026-11-03

- Firmware 0.2.0 compiles successfully: program size 895109 bytes, static RAM 57024 bytes. These are compiler figures.
- Mutual TLS-PSK with AES-128-GCM is exercised on local sockets; wrong keys, unpaired identities, mismatching application identities, and private pairing-file creation have regression coverage.
- The exact firmware USB-priority policy is host-compiled with static assertions. ESP32 scheduling, radio behavior, and real transport switching remain untested on hardware.
- USB provisioning, persistent NVS configuration, Wi-Fi reconnect, status/IP display, and USB-only credential clearing are compiled but not physically accepted.
- New binary SHA-256: `c9695530ec0306f110e0963e77491734eae29a2e159aa49271a0d01a50604712`; 895472 bytes. The earlier hash above belongs to the USB-only build.
- No physical display has been flashed. Wireless firmware updating and production NetLink integration remain unimplemented.
- Final validation from the project folder: all 15 tests passed without skips, including the actual local TLS server surviving an invalid client and accepting the paired simulator; Ruff checks and formatting passed.

## Application OTA update, 2026-11-03

- Firmware and host tool 0.3.0 implement application-only OTA on the existing paired TLS connection. No physical device was flashed.
- Firmware build passed: 902829 bytes program size, 57584 bytes static RAM. These are compiler values, not measured runtime/power data.
- Host preflight accepted the actual compiled ESP32-S3 image, including its checksum, appended SHA-256, application descriptor and retained profile/version marker.
- The linked firmware ELF exports a strong `verifyRollbackLater` override, so Arduino does not automatically confirm the candidate before setup. The SDK build configuration enables bootloader app rollback. Actual bootloader rollback behavior remains physically unverified.
- All 34 tests passed without skips. Coverage includes exact native transfer admission policy, wrong/corrupted/oversized images, offsets, interruption before commit, true TLS connections across a simulated reboot, lost finish acknowledgement, wrong post-boot image, and explicit boot confirmation followed by an observed valid state.
- An existing TLS-server regression test had an insufficient total duration for its failed-handshake budget plus full bench session; its duration was corrected. Final tests and Ruff checks/formatting passed.
- `panel wifi update --help` passed. The actual update command has only been executed against temporary simulated peers, not a physical ESP device.
- SHA-256 authenticates image integrity; pairing/TLS authorizes the sender. Independent release signatures, secure boot, physical power-loss tests and full unattended hardware recovery remain outstanding.
- Latest application binary: 903200 bytes; SHA-256 `c98d400e5a2da76b88e07e2192ea675437bf343953c3f6e79148b55b539e6313`. Earlier hashes in this record are historical builds.

## First physical installation and Wi-Fi configuration, 2026-11-03

- Identified the attached ESP32-S3 revision 0.2 with 16 MB flash and 8 MB embedded PSRAM. Secure Boot and flash encryption were disabled; no eFuses or security configuration were changed.
- Made a private full 16 MB factory-flash backup with file mode 0600 and verified it against the device digest before writing.
- Flashed firmware 0.3.0, bootloader, partition table and initial OTA metadata over USB. All written regions passed esptool hash verification.
- Actual USB bench passed: firmware identity and expected image hash matched, display/touch startup self-check passed, six heartbeats and zero rejected frames. No desk/monitor commands were sent.
- User entered Wi-Fi credentials locally. Actual Wi-Fi TLS-PSK bench passed with acknowledged demo data, three heartbeats and zero rejected frames. The user reported a visible IP address and Wi-Fi-ready status.
- The update command observed the already-current image over Wi-Fi, confirmed boot state VALID and verified it again. This was action `already_current`, with no retransmission and no observed reboot. It is not evidence of a physical OTA transfer or rollback.
- Image content SHA-256: `7a98decfa66ec7fd7a2d1f7bc88d0a3ae1a35d3d03bf9004fbbce5b12d35fb3d`.
- Device identity, backup digest and local addressing are in the private installation receipt. Physical touch-coordinate, new-image OTA, power-loss and rollback tests remain outstanding.

## Robustness follow-up, 2026-11-03

See [the physical robustness report](robustness-2026-11-03.md). The packet-serialization fix improved median response time about 14-fold, and real reconnect, malformed-input, partial-flash and unconfirmed-boot rollback tests passed. Two ordinary OTA transfers failed before activation. After explicit approval, the additional OTA-session timeout fix 0.3.1 was installed once over USB with flash hash verification. Exactly one same-image Wi-Fi transfer was then attempted; it failed after at least 40% with a peer connection reset before finish/activation. No retry was performed. A read-only reconnect verified the expected 0.3.1 content hash, VALID state, passing startup self-check, preserved Wi-Fi pairing and no active partial transfer; a further 10-second read-only session passed. Do not interpret the successful deliberate rollback as reliable ordinary OTA delivery. All 36 local tests passed; the full successful Wi-Fi update path with this fix remains unproven. See the two `hardware-0.3.1-*` artifact reports for this authorized attempt and recovery.


## Recoverable OTA and final acceptance, 2026-11-03

See [the OTA recovery report](ota-recovery-2026-11-03.md). A captured Wi-Fi disconnect preceded the actual TLS failure with only 120 ms since host activity; changing the session deadline had not fixed the fatal-abort policy. Firmware now retains a matching inactive-slot transfer briefly, and the host reconnects and resumes using its verified offset. Two deliberate partial-transfer fault tests passed. Three full images were transferred between 0.3.2 and 0.3.3: first fully automatic, second with separate confirmation recovery due to a discovered reboot handshake race, third fully automatic after that race fix and an actual transport loss resumed at byte 12800. The original unconfirmed receipt is preserved separately from its recovery evidence.

Final device state is the expected 0.3.3 image VALID, startup self-check passed, transfer inactive. An additional 30-second read-only session and three reconnects passed. The initial full 43-test suite and the final focused 10-test TLS suite cover 45 unique passing cases; final lint/format checks passed. Exactly the six approved physical OTA-transfer trials and the two approved app-only USB installations were used. Electrical power-loss and multi-day acceptance remain open.
