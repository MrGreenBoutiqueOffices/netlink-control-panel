# Native display and interactive preview

The current source, `docs/design/netlink-bedienpaneel.pdf`, contains 25 screens. The firmware and browser preview cover desk controls, personal demo heights, confirmation, movement/stop, offline status, the two-row menu, monitor settings, preferences, panel settings/rotation, software updates, startup/connection, update outcomes, obstruction, calibration, sleep and welcome.

## Run the preview

Serve the repository root, then open `/preview/`:

```sh
python3 -m http.server 8768 --bind 127.0.0.1
```

The browser scenario selector contains all 25 PDF pages. Its check → download → installation → restart/success flow is entirely simulated; it does not contact GitHub, flash firmware or send device commands. Download cancellation and error/retry screens can also be tried. Personalization uses the supplied sample name and heights only in demo scenarios.

The native C++ renderer runs on the LILYGO at 640 × 180 pixels. The browser copy provides a separate local simulation. This revision has not been flashed onto the physical panel; native renders and browser checks are not device acceptance.

## Controls

- Heights stay within 62–127 cm (620–1270 mm).
- A short arrow tap changes only the target height by 1 cm. Holding repeats after 350 ms, then every 180 ms. Release or dragging outside stops target editing and clears the pressed color.
- Current height remains unchanged until **Bevestigen**. **Annuleren** discards the target. Sitting/standing presets and the welcome screen also select a target before confirmation.
- A touch anywhere during simulated movement stops it.
- **Meer** opens Monitor, Voorkeuren, Paneel and Software. The menu and desk notification reflect an available update.
- **Paneel** controls brightness, dim timeout and 180-degree rotation. Rotation applies to the framebuffer and touch coordinates. Settings are persisted by the panel settings journal; demo heights and presets remain in RAM.
- The first touch after dimming wakes the screen without an additional action.
- The calibration hold button lowers only the local demo height and stops on release, at or above 62 cm.

## Software

The version is now shown on **Meer → Software**, using the same version source as the protocol and release build. The screen distinguishes checking, available/current firmware, downloading with cancellation, installation, success and failure/retry. Actual signed Wi-Fi updates use these views; see [signed updates](signed-updates.md) for activation and verification.

During real installation or candidate boot checking, conflicting controls remain blocked. A download can be cancelled before activation. No cancellation or navigation can interrupt final verification or take ownership of an active update.

## Production status and profile examples

`device.state.v1` supplies real read-only desk/monitor status; see [production protocol](production-protocol.md). A Waveshare-only setup or desk without a monitor is supported. Unknown/stale readings remain explicit. Tapping arrows does not substitute simulated data or start movement in this mode.

The sample profile name, personal presets and welcome view do not establish an authenticated identity. Production status clears the sample profile. A real profile and preference integration requires a separate protocol contract.

## Assets and checks

Source PDF pages are normalized to `docs/design/reference-01.png` through `reference-25.png`. Generated RGB565/RLE frames preserve existing firmware scene IDs; extra scenes add the profile, update and welcome examples. Dynamic text uses locally rasterized Inter. RGB565 and font rendering can differ slightly from the original raster typography.

```sh
uv run --locked python scripts/generate_demo_assets.py
uv run --locked python scripts/generate_demo_assets.py --check
uv run --locked pio run --project-dir firmware
uv run --locked python scripts/check_tests.py
```

`tests/test_panel_demo.py` compiles the actual state machine/renderer and checks all 25 scene bounds, navigation, target editing, release, confirmation, limits, rotation, cancellation and demo-profile isolation. `tests/test_github_updates.py` exercises the real updater with temporary signatures and fake network/NVS/flash.

`scripts/capture_panel_demo.py` can read atomic framebuffer snapshots and select the 25 native scenes over USB or paired TLS. Do not run it during a user review: it switches local demo screens. It writes no firmware and sends no real equipment commands.
