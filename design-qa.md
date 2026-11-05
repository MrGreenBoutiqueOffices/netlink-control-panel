# Design QA: expanded display demo 0.5.2

final result: passed

The third PDF is installed as a native demo on the physical LILYGO display. No open P0/P1/P2 differences were found in compared states. Physical controls remain for user assessment; no camera photograph or actual NetLink actuation is claimed.

## Source and normalization

- Source visual truth: `docs/design/netlink-bedienpaneel.pdf`, 17 pages from the third supplied PDF.
- Sources: 1920 × 540 raster pixels per page in 480 × 135 pt; references `reference-01.png` through `reference-17.png` normalized to 640 × 180.
- Native implementation: the same C++ renderer as the firmware, 640 × 180 RGB565, density 1:1, no browser or hardware bezel. This is the embedded device viewport.
- Full-view paired evidence: [screens 1–8](docs/design/evidence/native-01-08.png) and [screens 9–17](docs/design/evidence/native-09-17.png); source and implementation compared side by side in the same images.
- Focused evidence: `scene-12.png` showed a duplicate percentage. `update-corrected-comparison.png` was opened and compared after the fix: one value at the same vertical position as the source.
- Physical implementation: [Panel on the device](docs/design/evidence/device-settings-0.5.0.png) shows source page 8 beside an atomic framebuffer capture from the real display. This image was opened and compared. A fixed snapshot was read without injecting UI actions; the live page changed from Paneel to Ruststand meanwhile without mixing the image.

## Comparison history and findings

- [Resolved P2] The update screen contained static 64% plus the new dynamic value. The entire original percentage region is now cleared and exactly one new value aligned with the progress bar. After the fix it was rendered and visually compared again.
- [Resolved P2] The earlier framebuffer stream could produce a mixed image during concurrent controls. Since 0.5.0 a complete PSRAM copy is made first; every chunk has a fixed snapshot ID and scene name. The actual USB capture confirmed coherence while live state changed.
- [P3] The original font is not available as a usable font in the raster PDF. Dynamic values use locally rasterized Inter with small glyph-width/optical-weight differences. This explicitly does not claim identical fonts.

## Five fidelity surfaces

- Typography: fixed source text and icons come from the design; changing values use appropriate Inter sizes and weights. No visible clipping or unintended wrapping in the compared pages.
- Layout: larger arrows, two-row menu, slider/settings regions, error actions and idle screen follow the source. Rotation is a full 180-degree pixel transformation with a corresponding touch transformation.
- Colors: RGB565 and limited palette cause small expected rounding. Green/orange semantic messages retain a broader palette. The source and actual Paneel capture have the same visual hierarchy and color distribution.
- Assets: the 17 screens and icons derive from the supplied raster source. No replacement hand-drawn web icons or invented photography. Source and earlier design set are preserved in the repository.
- Copy: labels and messages follow the PDF. An actual unconfirmed new boot shows Nieuwe firmware controleren; this deliberate content difference avoids implying a confirmed update. Error/calibration scenarios remain local demos.

## Verification

All 46 local regression tests, lint and formatting pass. The actual native class is extensively tested on 17 framebuffers with canaries, new menu hit areas, inverted pixels, inverted touch coordinates, sleep/wake, error buttons and bounded calibration/stopping on release. Existing target selection, tap/hold/release, confirm/cancel, preset and 62–127 cm tests continue to pass.

0.5.0 was written over USB into the verified active application slot; hash verification passed. Boot version, image hash, VALID, display/touch startup self-check, min/max and snapshot ID were read back on the real device. Actual physical touch calibration and feel remain user acceptance; USB verification injected no screen changes or movement.

## Completed

1. Compared all 17 native screens with the latest PDF and fixed the percentage difference.
2. Built firmware and installed it through the chosen cable route, without changing NVS/bootloader/partitions.
3. Verified current version and consistent screen readout on the physical panel.

The browser copy is not the primary implementation of this revision and still has the earlier design set. Older QA is preserved in `docs/design/v2/design-qa.md`.

## PR check 0.5.2

The added version label was visually checked natively: [Panel with firmware version](docs/design/evidence/version-label-0.5.1.png). Firmware 0.5.1 was installed over USB and version, image hash, VALID and startup self-check confirmed on-device. 0.5.2 also fixes brightness-slider dragging at 180° rotation, with a regression test that failed before the fix. This latest correction was tested and built locally; 0.5.2 is not physically installed yet. The screenshot therefore deliberately shows the previously verified 0.5.1.
