# Read-only status — native QA

Result: passed for software/native rendering; no physical NetLink acceptance.

The same C++ renderer as the firmware was compiled and rendered at 640 × 180. Synthetic measurements come from the test fixture, not a connected desk. All five images were opened and inspected:

- [Measured height](design/evidence/read-only/height-current.png): 108.6 cm, explicitly read-only (`Alleen-lezen`); arrows/presets send no commands or simulation requests.
- [Last-known height](design/evidence/read-only/height-last-known.png): the same measurement with LAATST BEKEND, without a false freshness claim.
- [Unknown height](design/evidence/read-only/height-unknown.png): dashes, no 0/74-cm default or old glyph remnants.
- [Monitor status](design/evidence/read-only/monitor-current.png): 83%, Uit and USB-C from the fixture; controls are inactive.
- [Unknown monitor status](design/evidence/read-only/monitor-unknown.png): dashes/Onbekend, no invented brightness/power/input.

A glyph remnant found at unknown height was removed by clearing the entire original value region. The unknown image was then rendered and opened again. Typography/colors follow the existing Inter/RGB565 rendering; supplied reference designs were not changed.

Native tests also check actual protocol validation, expired data leases, unknown status, observations not being clamped to command limits and blocked read-only touches. The separate webserver trial covers a Waveshare with fixed HDMI1 and a missing expected Dell. Firmware 0.7.0 was built but not physically installed; operation and legibility on a real NetLink/workplace follow an explicitly authorized installation.
