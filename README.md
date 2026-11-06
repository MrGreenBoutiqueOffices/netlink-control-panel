# NetLink Panel

A working prototype for the LILYGO T-Display S3 Long: a compact desk and monitor control panel. A direct USB connection to a NetLink will be the default; Wi-Fi remains optional. Independent signed updates over Wi-Fi are planned in the firmware. This is future work and does not work in the current build.

## Current status — 4 November 2026

Firmware **0.8.0 from source commit `e8d2232` is installed on the prototype over USB**. The flash hash and subsequently the running version, image hash, VALID boot state and display/touch startup check were verified. USB worked again after reconnecting the cable. The factory backup is preserved. The user is testing arrow feedback and settings; full physical acceptance remains open. A new CI build or merge does not install anything on the display.

| Component | Status |
| --- | --- |
| Native display demo | 25 supplied designs, entirely local simulation without a NetLink |
| Height controls | Tap selects 1 cm; hold repeats; release retains the target height; only Confirm starts the simulation; limits 62–127 cm |
| Panel | Brightness, dim timeout, 180° rotation and version number under More → Panel (`Meer` → `Paneel`); since 0.8.0 local settings are validated and retained across restarts; physical user acceptance is ongoing |
| Firmware 0.8.0 | Restores the arrow press color after release and adds persistent local panel settings |
| USB/Wi-Fi bench | Mac/Linux host program, bounded JSON protocol, simulator and authenticated encrypted Wi-Fi connection |
| OTA | Dual slots, resume and boot confirmation/rollback implemented; larger firmware transfers remain insufficiently reliable; USB is the current installation route |
| Real controls | No NetLink panel service, MQTT integration or real desk/monitor commands yet |
| Management and releases | PR/main checks and commit-bound firmware/protocol artifacts; Release Drafter manages the draft and notes; publishing triggers firmware asset builds for that release. No automatic flashing or fleet deployment; see the [release procedure](docs/releases.md) |

The local demo remains usable without a management session. Monitor functions, preferences, errors and calibration are examples, with no control or detection of real equipment. The panel brightness setting scales rendered pixels; physical backlight control has not been demonstrated.

See [controls and installation history](docs/display-demo.md), [visual QA](design-qa.md) and [the designs](docs/design/netlink-bedienpaneel.pdf). Earlier bench and OTA reports contain historical results; the table above describes the current project status.

## Read-only status path (0.7.0 merged)

The new firmware capability can display real height and selected monitor status from `netlink-webserver`. A Dell monitor is not required; a Waveshare or a desk without a monitor remains supported. Observations, last-known values and unknown status are distinguished. All device controls remain blocked. The installed 0.8.0 includes firmware support; the webserver integration awaits review and has not passed physical NetLink acceptance. See the [status contract](docs/production-protocol.md).

## Local panel settings in 0.8.0

Arrow buttons show the pressed color only during touch; the selected target height and confirmation remain after release. Physical brightness, dim timeout and rotation changes are saved on release, with a schema, revision and previous valid configuration as a recovery point. Failed storage restores the previously saved settings. Production status contains only the saved configuration and any storage error; managed changes remain blocked. Desk presets and Wi-Fi credentials are outside this UI configuration. See [storage, ownership and verification](docs/panel-settings.md).

## Try the demo

On the display, More (`Meer`) opens Monitor, Preferences (`Voorkeuren`) and Panel (`Paneel`). Arrows and presets select only a target height. Cancel (`Annuleren`) discards the selection; Confirm (`Bevestigen`) starts a local movement. Touching during that movement stops the simulation. The first touch after idle only wakes the screen.

Additional design scenarios: in More, hold the empty bottom-right area for at least one second. In the status examples, hold the left side to advance. There is no automatic screen carousel.

Without a display, serve the repository root and open `/preview/`. The browser preview includes all 25 supplied screens and a simulated update flow; it is separate from USB, firmware and real equipment. The native display renderer uses the same design source.

## Development and checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run from the project directory:

```sh
uv sync --locked --group dev
uv run panel bench --simulate
uv run python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked ruff format --check .
node --check preview/app.js
```

CI runs the same path with [validated artifacts and a webserver version boundary](docs/releases.md). Generated assets can be checked without changing the checkout using `uv run --locked python scripts/generate_demo_assets.py --check`.

Tests cover framing, sessions, TLS, update recovery and the actual native C++ state machine/renderer. The simulator uses a pseudo-terminal pair and sends no hardware commands. Passing software tests do not replace physical acceptance of power, touch, movement, radio or recovery.

## Build the firmware

```sh
uv run python scripts/prepare_firmware.py
uv run --locked pio run --project-dir firmware
```

Preparation fetches the board definition, GFX library and CST3530 driver from a pinned [official LILYGO revision](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02). Automatic touch-controller firmware updates are disabled. The implementation uses Arduino/ESP-IDF with a custom native renderer; no LVGL migration is required to use the current demo.

The logical framebuffer is 640 × 180 and is transformed in software to the physical 180 × 640 frame. CST3530 touch mapping has been used and tested on the current prototype; other board revisions require separate verification.

The firmware version is defined in `firmware/src/panel_version.h`; the display, handshake and image marker use that same source. Generated assets are tracked in the repository. Regenerate only after design changes:

```sh
uv run --locked python scripts/generate_demo_assets.py
```

## USB installation and recovery

```sh
uv run panel ports
```

Identify the intended panel using both USB identity and the handshake. Port names can change after reboot or programming mode; do not rely on a fixed port number. Opening a serial port can reset the device.

For the current prototype, only the application in the previously verified active slot was written. Before writing, verify device identity, factory backup, image profile and boot selection. Do not blindly use a complete upload/erase command: bootloader, partitions and NVS are outside a normal application update. The private backup, pairing and installation reports are kept outside Git.

USB flashing is the current installation/recovery route. The panel will own Wi-Fi downloads, installation and local boot confirmation. USB remains available for installation and recovery. Webserver update integration is outside #15. A merge or build installs nothing on the display.

## Optional Wi-Fi and OTA

Wi-Fi testing with the Mac is already available. Configure once over USB:

```sh
uv run panel wifi setup --port <usb-port> --host <mac-ip-address>
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

The network name and password are requested interactively. Firmware stores configuration in NVS; credentials are not embedded in firmware source. The bench uses a dedicated TLS-PSK key. NVS/flash is not encrypted yet. See the [Wi-Fi procedure and limitations](docs/wifi.md).

The existing `uv run panel wifi update` writes the inactive application slot and verifies the image and boot confirmation after reboot. Resume after connection loss and rollback have been demonstrated physically on earlier firmware. However, the larger 0.4.1 transfer exhausted its reconnect budget around 95%. The [full-image host fix](docs/ota-full-image.md) now recovers based on confirmed progress and has TLS fault-injection coverage; physical acceptance of the larger image remains open. Use USB to install the current demo image for now. See the [OTA procedure](docs/ota.md) and [current display test status](docs/display-demo.md).

The [initial signing layer](docs/signed-updates.md) checks release signatures on host and panel; the default build remains unsigned bench firmware. Independent Wi-Fi downloads and local boot confirmation are planned in [#15](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/15). The webserver has no role in this. Production key provisioning, secure boot, recovery from all power/network failures and unattended recovery have not been accepted. Wi-Fi to a real NetLink, transport switching and management without a Mac remain future work.

## Remaining work

The [GitHub epics](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues?q=is%3Aissue%20is%3Aopen%20label%3Aepic) contain the concrete work packages, acceptance criteria and dependencies:

1. [Direct USB connection](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/2): production protocol, panel service and existing local MQTT services.
2. [Real controls](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/3): actual status, persistent settings and physical stop/control acceptance.
3. [Reliable updates](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/4): larger images, controlled signed releases and recovery tests.
4. [Optional Wi-Fi](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/5): provisioning, pairing, transport selection and recovery without USB.
5. [Remote management](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/6): agent integration, authorized actions and existing logs/metrics.
6. [Releases and pilot](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/7): CI, installation/mounting and multi-day acceptance at real workplaces.

Start with the protocol and USB service; work on OTA diagnosis and CI in parallel. Then test one real workplace before a wider rollout. Bookings, check-in and personal profiles are outside this initial scope.

[The original product plan](docs/product-plan.md) provides architectural background and still contains assumptions from before the prototype. Current status and GitHub issues take precedence over that historical phasing. Integration must use the existing NetLink desk/display services and fleet-first Balena release flow. Stack, agent and desk-service changes belong in their own repositories; this repository contains firmware and the host prototype.

## Directories

| Directory | Contents |
| --- | --- |
| `firmware/` | ESP32-S3 firmware, native demo and update code |
| `host/netlink_panel/` | USB/Wi-Fi bench, updater, protocol decoder and simulator |
| `preview/` | Interactive browser demo of all 25 designs |
| `tests/` | Python, native renderer, protocol and recovery tests |
| `scripts/` | Firmware preparation, asset generation and diagnostic captures |
| `docs/` | Designs, usage, historical test results and planning |

## Independent Wi-Fi updates

On signed-policy firmware, open **Meer → Software** to check the latest stable GitHub release and explicitly install it. The panel downloads, verifies and confirms the update itself. For Wi-Fi without a bench server, use `uv run panel wifi setup --port <usb-port> --wifi-only`.

The default build still has no production signing key or verified board revision; activation and hardware acceptance remain required. See [signed updates](docs/signed-updates.md) for setup and recovery behavior.

## License

The project's own code is licensed under [GPL-3.0-only](LICENSE).

Third-party code, fonts and assets retain their original licenses and copyright notices; see [third-party notices](THIRD_PARTY_NOTICES.md).
