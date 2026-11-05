# Updating firmware over Wi-Fi — current host bench route

This document describes the existing host-driven bench route. The [decision for #15](signed-updates.md#decision-the-panel-owns-its-updates) is independent download and installation on the panel with local boot confirmation. Webserver integration is outside that update scope. This does not work in current firmware yet: the procedure below requires a paired host, including `ota_confirm` after reboot.

See the [full-image diagnosis for issue #14](ota-full-image.md) for the progress-based host fix and remaining physical matrix.

Since firmware 0.3.2, an ongoing transfer can resume after temporary connection loss. Use the corresponding current host tool. See the [recovery check](ota-recovery-2026-11-03.md) for physical trials actually performed and remaining limitations.

## Install once, then update wirelessly

Firmware 0.1/0.2 and factory firmware do not contain this updater. Therefore **install version 0.3.0 once over USB**, including its bootloader and partition layout. Preserve factory flash and check board revision first, following the README. The host tool does not do this automatically.

Then configure Wi-Fi with `panel wifi setup` as described in [wifi.md](wifi.md). An existing 0.2 Wi-Fi configuration uses the same NVS format; a normal flash preserving NVS can retain it. After a complete flash erase, configure it again.

For subsequent versions, from the project directory:

```sh
uv run --locked pio run --project-dir firmware
uv run panel wifi update
```

The updater defaults to `firmware/.pio/build/panel-bench/firmware.bin` and `.secrets/panel.json`. For another file or pairing:

```sh
uv run panel wifi update --firmware <firmware.bin> --pairing .secrets/panel-nieuw.json
```

First stop any running `panel wifi serve`: both programs use the same local address and port 8769. The panel needs only power and connectivity to the Mac. No additional update port or public access point is added.

## What happens?

1. The Mac checks ESP32-S3 chip identity, application descriptor, segment lengths, checksum, SHA-256 and the embedded NetLink board/protocol/partition identity. A bootloader, merged flash dump, corrupt image or wrong board is rejected before the network server starts.
2. Only the paired panel can connect over the existing mutually authenticated TLS-PSK connection. The Mac also checks panel identity, update support and startup self-check.
3. If the initial USB flash had no OTA selection, the panel registers the running image as a known valid fallback. It then writes only the other application slot. NVS, bootloader, partitions and Wi-Fi details are not updated.
4. Each block of at most 512 bytes must be acknowledged at the expected position. With capability `ota_resume_v1`, the panel retains the flash handle, write position and running hash after Wi-Fi/TLS loss for at most 60 seconds without transfer activity. The host allows at most five recovery attempts without newly confirmed bytes. Only a higher confirmed offset replenishes recovery allowance; equal or reset offsets do not. Total reconnections may therefore exceed five within the same fixed deadline (600 seconds by default). Repeatedly lost activation requests use the same bounded budget. Repeating `ota_begin` for exactly the same size, both hashes, profile and version returns the actual written position without erasing again. The host validates it and sends only the remainder. After lease expiry or panel restart, the image starts again from zero; the current valid boot remains selected. A different active image is rejected. USB takeover and explicit abort immediately clean up the transfer.
5. Boot selection changes and the panel restarts only after total length, SHA-256, embedded image identity and ESP image validation pass.
6. New firmware is initially unconfirmed. The panel must reconnect over TLS, report the expected image hash and version and pass startup self-check. The Mac then requests explicit boot confirmation and reads confirmed status again.

Startup self-check verifies buffer/display initialization and a read touch-controller identity. This does not prove correct pixels, screen orientation or touch coordinates; those remain physical tests.

The receipt stores phase, elapsed time, highest confirmed and current positions, net progress per second, total recoveries, stalled-budget state and at most 32 sanitized session measurements (firmware, uptime/reset reason, RSSI/Wi-Fi disconnect reason where available, TLS and hello duration). Omitted older session measurements are counted. Credentials, network name, IP and protocol frames are not copied.

Only `ota_confirmed` and exit code 0 mean the host observed the expected image and confirmed boot. The result is also in `artifacts/last-update.json`. Touch buttons are blocked during upload. This prototype does not control a real desk or monitor yet.

## On interruption

- **During upload:** the current slot remains selected. The host resumes only after a fresh authenticated handshake and an exactly matching manifest. After a lost block acknowledgement it requests the current position rather than blindly rewriting the block. Legacy firmware without `ota_resume_v1` gets no automatic upload retry.
- **After activation without confirmation:** new firmware waits at most about 90 seconds and then restarts. With the supplied rollback-enabled bootloader, an unconfirmed image is rejected at reset and the known previous version is selected. This automatic fallback was measured on this board; power loss during activation has not been tested.
- **After a lost `ota_finish` acknowledgement:** the host checks the actual running hash on the next connection. If the old image is still running and explicitly reports a retained transfer, that same complete transfer can still be finished. An old image without a retained transfer is not reinstalled: it may indicate rollback. A lost response alone proves neither success nor failure. Lost boot confirmation is resolved by checking the same hash again and confirming idempotently.
- **If the host stops before boot confirmation:** the outcome is unconfirmed. Reconnect it in time with the same image using `panel wifi update`; the desired image can still be checked and confirmed. Without confirmation, the boot deadline may cause rollback.
- **Different image after reboot:** the tool reports no success; rollback may have occurred. There is no automatic reinstall.
- **Same file already running:** the tool checks and confirms the existing boot without sending the same image to flash again. A changed build with the same version number is distinguished by image hash.
- **Application disables the scheduler/USB or writes unusable network configuration:** the prototype updater does not guarantee recovery from every software or hardware fault. Retain USB as a recovery route; remote recovery remains a physical acceptance requirement.

A confirmed but functionally unwanted version can be replaced by uploading a compatible older 0.3+ application image. There is no generic rollback button that arbitrarily switches to the other slot: it may contain an interrupted upload.

## Developing the screen

Retain OTA hooks when changing screen code. `firmware/src/panel_ota.h` contains `PANEL_FIRMWARE_VERSION` and the fixed profile identity. Builds with the same version number can be tested repeatedly; the updater compares the cryptographic image hash. Another hardware board, application protocol version or partition layout requires a deliberate profile change and is outside this application updater.

## Security and physical acceptance

Authorization uses the unique pairing key and TLS. SHA-256 and ESP image validation protect transfer integrity and enforce image identity. This is **not an independent release signature, secure boot or anti-rollback protection**; someone with the pairing key can offer their own compatible firmware. `.secrets/panel.json` therefore remains a management credential.

Locally tested: actual host code over TLS with simulated panel reboot, lost begin/block/finish/boot acknowledgements, wrong post-reboot image, image format/corruption, strict resume positions and boot confirmation. The actual firmware OTA handler is also compiled against fake SDK flash calls to test same-manifest resume, handle preservation, no duplicate writes, manifest rejection and lease expiry. Firmware uses ESP-IDF OTA operations and the exact native transfer guard is compiled and tested on the Mac. This is not ESP flash emulation or a physical rollback test.

Current physical results are in the [recovery report](ota-recovery-2026-11-03.md); earlier trials and demonstrated unconfirmed-boot rollback are in the [earlier robustness report](robustness-2026-11-03.md). Still open: electrical power loss during writing/activation, actual USB takeover during transfer, access point outage and multi-day stability. Wi-Fi/TLS resume does not survive panel reset; it then safely restarts from zero. Never treat a Balena rollout or local simulator as physical acceptance.

Sources: [ESP-IDF 4.4.6 OTA and rollback](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html), [ESP-IDF OTA operations](https://github.com/espressif/esp-idf/blob/v4.4.6/components/app_update/esp_ota_ops.c), [Arduino startup/rollback hooks](https://github.com/espressif/arduino-esp32/blob/2.0.14/cores/esp32/esp32-hal-misc.c).


## Repeatable physical recovery check

Use only with explicit permission for two partial physical firmware writes, while the specified image is already running on the panel:

```sh
uv run python scripts/hardware_ota_recovery.py --firmware firmware/.pio/build/panel-bench/firmware.bin --write-inactive-slot
```

This tests five seconds of server outage and an unread block acknowledgement. It writes the other slot, checks resume and explicitly aborts afterwards; it does not activate an image. Stop other servers/updaters first. The result is in `artifacts/ota-recovery-faults.json`.
