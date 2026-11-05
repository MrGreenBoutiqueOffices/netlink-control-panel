# Standalone design preview on the LILYGO display

The firmware simulates a desk and monitor entirely locally. No NetLink, MQTT, desk UART or DDC/CI monitor is connected. Touch controls are independent of a USB or Wi-Fi management session. Heights and preferences exist only in RAM and return to demo values after restart.

## Version number on the display

Since 0.5.1, More → Panel (`Meer` → `Paneel`) shows the firmware version below HELDERHEID PANEEL. The text uses the same version source as the management and update protocols and rotates with the screen.

0.5.2 also fixes dragging the brightness slider when the panel is rotated 180 degrees. This fix was tested locally; the latest physical installation is 0.5.1.

## New design set in 0.5.0

The third supplied PDF contains 17 screens. 0.5.0 adds larger arrows, the two-row menu, normal/180-degree rotation, the minimal idle screen and the expanded startup, connection, update, error, obstacle and calibration screens. Target-height controls and the 62–127-cm limits remain in effect.

Rotation changes both the entire framebuffer and touch coordinates. It remains a RAM setting in this demo. After the configured inactivity period, a quiet height-only screen appears; the first touch wakes the previous page without performing an action.

Additional examples on the display: open More (`Meer`) and hold the empty bottom-right area for at least one second. In status examples, advance by holding the left side for at least one second. Error buttons such as Later and OK return to Desk (`Bureau`); Opnieuw opens the connection example. In Calibration (`Afstellen`), the large hold button lowers only the local example height, stops on release and never goes below 62 cm. Scenario mode loads the example values from the design.

Actual OTA progress uses the new update image with the real percentage. A new boot awaiting confirmation explicitly shows Nieuwe firmware controleren. The demo is blocked during that real management action. Other error/obstacle/calibration screens are local design scenarios, not NetLink integration.

0.5.0 was installed over USB on the identified display; esptool verified the written flash hash. USB was then used to read back version, expected image hash, VALID state, startup self-check and limits. A coherent snapshot of Panel (`Paneel`) was preserved while the live UI entered Idle (`Ruststand`). No screen changes were injected during that final check. Evidence: `artifacts/display-0.5.0/verification.json` and `comparison.png`.

## Controls since 0.4.3

- The lower limit is 62 cm and the upper limit 127 cm (620–1270 mm). Taps, holds, presets, demo input and confirmed movements respect these limits.
- A short tap on Hoger or Lager changes only the target height by 1 cm.
- Holding repeats that target-height step after 350 ms, then every 180 ms. Release or dragging outside the arrow stops adjustment; the dark confirmation screen remains.
- Current height stays unchanged while selecting. Only Bevestigen starts simulated movement. Annuleren discards the selection.
- Zitten and Staan also select a target height first. Bevestigen starts simulation toward that preset.
- During confirmed movement, one touch anywhere on the screen stops the simulation.
- Meer opens Monitor, Voorkeuren and Paneel. Monitor offers demo brightness, power and input; Voorkeuren saves the current demo height as a preset; Paneel offers brightness, dim timeout and rotation. Sliders respond to taps and drags.
- Hold Meer on the home screen for about one second to disconnect/reconnect the simulated connection. Desk actions are blocked in that offline state; local panel settings remain usable.
- After the configured dim timeout, the first touch wakes the screen without performing another action.

The reference is `docs/design/netlink-bedienpaneel.pdf` (the third PDF; the previous version is preserved in `docs/design/v2/`), with seventeen 640 × 180 screens. Original screen images are embedded compactly as RGB565/RLE; changing text uses locally generated Inter glyphs. The original font is unavailable as a usable webfont in the raster PDF; the limited typographic difference is documented in `design-qa.md`.

## Regenerate assets

```sh
uv run scripts/generate_demo_assets.py
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

The generator pins optional dependencies in its script metadata. A normal firmware build uses the checked-in generated files and does not need those Python packages.

## Repeatable checks

`tests/test_panel_demo.py` compiles exactly the same C++ state machine and renderer as the firmware. It tests short taps, hold, release, target versus current height, confirmation, cancellation, stop, offline blocking, preferences, sliders, dimming and framebuffer bounds.

```sh
uv run python -m unittest discover -s tests -p test_panel_demo.py -v
```

`scripts/capture_panel_demo.py` reads the actual framebuffer and can select local demo screens and example input. It changes only RAM demo state, never firmware or real equipment. Do not start it during a user review: it switches screens and may conflict with real touches.

## Recorded limitations

0.4.0 was installed and confirmed over Wi-Fi. The first four screen images were read from the actual panel; a later capture was correctly stopped because a touch changed state during capture. The old direct-move interpretation in 0.4.1 was replaced with target-height-only editing in 0.4.2.

The large 0.4.1 Wi-Fi transfer failed around 95% after exhausting the reconnect budget. Resume works, but Wi-Fi OTA on this connection and larger image is not reliable enough yet. USB is therefore the chosen installation route. Boot selection and physical ESP32-S3/MAC were checked before writing; only the active application slot is updated over the cable, without replacing NVS/bootloader/partitions.

0.4.3 was installed over USB and esptool verified the written flash hash. The same USB connection then reported running version, expected image hash, VALID state and a passing display/touch startup self-check. Larger USB responses now work with a 4096-byte TX buffer.

On the actual device, the shared UI handler verified: a short up tap selected 75 cm, holding then selected 80 cm, release kept the target stable, one down tap selected 79 cm, and current height remained 74 cm throughout. Annuleren returned to the home screen. Firmware reports min 620 and max 1270 mm. Endpoint behavior and movement to the limit are covered by the passing native regression test; no automatic movement demo was started during this final check.

Evidence is stored locally in `artifacts/display-0.4.3/verification.json` and the USB installation log. The full 46-test suite, lint and formatting passed for this release. Physical user assessment of look and feel and touch remains the next step.


The atomic framebuffer API since 0.5.0 makes one PSRAM copy at offset zero and gives every chunk the same `snapshot_id` and `snapshot_screen`. Concurrent operation or automatic dimming can no longer mix that capture. The browser copy retains the previous design set for now; this 17-screen implementation is the native display demo.

## Read-only status in 0.7.0

A new webserver adapter can send actual desk and monitor status with capability `device.state.v1`; see `production-protocol.md`. There is no Dell dependency: a Waveshare alone or a desk without a monitor is supported. The host selects one monitor; unknown or old values are explicitly indicated. In this mode, tap/hold/release does not change height or start simulation. Control commands follow later.

Native C++ tests cover atomic validation, data expiry, unknown status and blocked touch. Native screens were visually checked; this is not hardware/NetLink acceptance. The latest physically verified firmware remains 0.6.0; 0.7.0 has not been installed yet.
