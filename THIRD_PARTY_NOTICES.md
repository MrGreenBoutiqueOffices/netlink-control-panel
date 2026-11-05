# Third-party components

`LICENSE` applies to the project's own code. Existing third-party copyrights, licenses and any additional conditions remain in effect. This inventory is not a complete collection of all license texts for a firmware build and grants no new rights to upstream code.

## Included in this repository

- **Inter**: Copyright 2020 The Inter Project Authors. The font `preview/assets/inter.ttf` and its generated embedded glyphs remain under the SIL Open Font License 1.1. The full license is in [preview/assets/OFL.txt](preview/assets/OFL.txt).
- **Designs and icons**: supplied for this project; their origins and crops are described in [preview/assets/README.md](preview/assets/README.md). This notice grants no rights to any trademarks or third-party material in the designs.

## Software fetched by the build

The build downloads dependencies; `firmware/.vendor/` and `firmware/.pio/` are not tracked in Git. Downloading them does not make their license terms identical to this repository's terms.

| Component | Established information / notices to retain |
| --- | --- |
| ArduinoJson 6.21.5 | MIT, Benoit BLANCHON; retain the full upstream license text when distributing |
| Arduino ESP32 core 2.0.14 | The inspected core header states LGPL-2.1-or-later; the SDK, libraries and other components have their own terms |
| ESP-IDF / mbedTLS | Retain component licenses and notices from the exact SDK used; the application's GPL does not replace them |
| Arduino_GFX 1.3.7 from the pinned LILYGO source | Current standalone upstream has a BSD license text; it has not yet been established as evidence for this exact vendor copy. Exact provenance and notices to supply remain a publication item |
| Hynitron touch driver from the pinned LILYGO source | No clear license notice was found in the inspected pinned repository root and driver directory. Distribution permission has not been established yet |
| Python `cryptography` 50.0.2 | Package metadata: `Apache-2.0 OR BSD-3-Clause`; retain its notices and any bundled component licenses |
| Python `pyserial` 3.5 | Package metadata: BSD; retain the license and notices from the distribution used |

The exact LILYGO source is commit `3deece89098f25e7d155e41e4e0f5dd8b368ab02`. See [prepare_firmware.py](scripts/prepare_firmware.py) and [platformio.ini](firmware/platformio.ini) for the selection and pinned versions. Build and development tools also have their own licenses; they are not relicensed here.

Public firmware distribution requires the full applicable notices, corresponding source, build information and, where applicable, installation information. This list does not replace those delivery obligations. The specific outstanding items are in [publication readiness](docs/open-source-readiness.md).
