# Design QA: standalone LILYGO demo

final result: passed

Native visual comparison and final cable installation of 0.4.3 are complete. No known open P0/P1/P2 differences in reviewed states. Device checks confirm tap/hold target editing, stable target after release and unchanged current height before confirmation. The user assesses physical look and feel.

## Source and normalization

- Source visual truth: `docs/design/v2/netlink-bedienpaneel.pdf`, the updated second PDF with eight screens.
- Source images: 1920 × 540 raster pixels per page, in a 480 × 135 pt PDF. `docs/design/v2/reference-01.png` through `reference-08.png` are normalized to 640 × 180.
- Implementation: the same native C++ renderer as the firmware, 640 × 180 RGB565 framebuffer, without browser or device bezel. This is the relevant viewport for this embedded display; the browser copy is not the primary deliverable.
- Full-view paired evidence: `artifacts/design-native/comparison.png` and `comparison-v2.png`. Source and native renderer are side by side for each state in one image.
- Focused evidence: `artifacts/design-native/scene-1.png`, `scene-6.png` and `offline-fixed.png`; typography, numeric values, button labels and slider region were opened and inspected at native scale.
- Real hardware framebuffers from 0.4.0: `artifacts/display-demo/screen-01.ppm` through `screen-04.ppm`. These are read screen buffers, not camera photographs. The next capture stopped because a real touch changed state; no incoherent image was saved as evidence.

## Findings and iterations

- [Resolved P1] Initial palette compression produced pink light areas and visible background blocks. Compression changed to median-cut without dithering; the second paired comparison and individual native captures confirm the correction.
- [Resolved P2] The rare orange offline color was lost with an undersized palette. The offline scene uses 256 colors; `offline-fixed.png` was opened and restores the orange message.
- [Resolved P2] The Monitor back button should lead to Bureau according to the source. Native interaction and browser copy now match the visible label.
- [Resolved P1] The initial 4-cm step and subsequent direct manual-move interpretation were not the intended controls. In the prepared 0.4.3, short tap and hold change only the target; release stops target editing. Bevestigen is the only entry to movement. The focused regression failed first and passed after correction. This correction is now installed as 0.4.3 and verified through the shared UI handler.

## Five fidelity surfaces

- Fonts/typography: original UI is raster with an invisible OCR font layer. Dynamic text uses locally rasterized Inter; hierarchy, sizes and baselines match the source. Small glyph-width differences remain P3; no identical-font claim.
- Spacing/layout: fixed 640 × 180 geometry, side panels, bottom buttons, menu layout and settings were reproduced; no clipped controls in native captures.
- Colors/tokens: source colors, RGB565 output and offline semantics were visually checked after compression fixes. RGB565 and antialiasing cause limited expected color rounding.
- Assets: original screen illustrations/icons from the supplied PDF; no drawn replacement icons. Bitmap and font assets are generated reproducibly from repository-local sources.
- Copy: current/selected height, presets, confirm/cancel, stop, menus and offline status follow the source. Clear demo semantics are documented in the project; no real device commands.

## Controls and verification

The full local 46-test suite passed before the latest control clarification. The changed actual native UI state machine was then retested specifically: short tap +1 cm, hold repeat, unchanged current height during target editing, freeze on release, cancel, confirm and stop, plus other UI checks. The current full 46-test suite passes, including short tap, hold/release, presets and confirmed movements at the 62 and 127 cm limits. Firmware 0.4.3 builds successfully and uses less than half the application slot. Lint and formatting pass.

The browser copy has a syntax check and was previously rendered in the in-app browser; no full browser QA of the latest interaction variant is claimed. Cable installation is now complete; version 0.4.3, image hash, VALID and startup self-check were read back. The physical user can now assess the corrected behavior.

## Completed final check

1. Identified the same physical ESP32-S3, checked active application slot and installed 0.4.3 over USB; flash hash verified.
2. Checked boot version/hash and target versus current height on-device over USB, with one short dark adjustment check and no automatic movement demo.
3. Left the display in its quiet initial state for the user.


Current paired evidence: `artifacts/design-0.4.3-native/comparison.png` contains source and current native renderer for Bureau and Bevestigen at the same 640 × 180 scale; this image was opened and compared. The current native renderer also rerendered all eight reference scenes. Small font-width and RGB565 differences remain P3. The raw streaming framebuffer capture in `artifacts/display-0.4.3/comparison.png` has a mixed top strip and is therefore not used as a coherent visual QA capture; the framebuffer API is not an atomic snapshot during concurrent UI input. This does not change the successful independent boot and interaction verification in `verification.json`. No physical camera photograph is claimed.
