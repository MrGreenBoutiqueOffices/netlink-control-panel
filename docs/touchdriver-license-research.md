# License research for NetLink Panel's Hynitron touch driver

Researched on 5 November 2026. Only source publications, GitHub history, existing issues and local source/build files were used. No maintainer was contacted, no issue was posted, nothing was published and no hardware was touched.

## Outcome

**Unknown: no explicit license or distribution permission has been established covering the complete exact NetLink input `Xinyuan-LilyGO/T-Display-S3-Long@3deece89098f25e7d155e41e4e0f5dd8b368ab02/lib/hyn_driver_for_esp32`.** Related GPL and Apache publications provide useful provenance evidence but do not resolve this question.

There are two direct byte-identical links to another official LilyGO repository with a GPLv3 root license: `hyn_ts_ext.c` and locally patched `hyn_cfg.h`. This is stronger than a matching chip name alone, but does not establish license evidence for the remaining exact files, complete driver or bundled firmware blob headers. This research does not support a claim that the entire NetLink driver is GPL-3.0-only or Apache-2.0.

## 1. Exact NetLink input and provenance

**Confirmed.** The [pinned upstream tree](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02/lib/hyn_driver_for_esp32) contains 25 files. A local Git blob hash comparison of all 25 files against the [GitHub tree API](https://api.github.com/repos/Xinyuan-LilyGO/T-Display-S3-Long/git/trees/3deece89098f25e7d155e41e4e0f5dd8b368ab02?recursive=1) confirms 24 identical files and exactly one difference: `hyn_cfg.h`, where NetLink changes `HYN_POWER_ON_UPDATA` from 1 to 0. The version label is `== Hynitron V2.10 20241111 ==`.

| File | Upstream Git blob SHA-1 |
|---|---|
| `hyn_core.c` | `728e45f5429d4a296d59efc0465c0708327dbb6e` |
| `hyn_core.h` | `2c69c43d067091b7a7644c0a557ddf0e6646c9a9` |
| `hyn_i2c.c` | `5f1d82f8570761d3bf15ae3ce0ddc48505d113a4` |
| `hyn_ts_ext.c` | `d2c51a583639add3c9f3fdd009da0b68b18ca6e3` |
| `hyn_chips/hyn_cst66xx.c` | `9adf049c0d033306d976e2cce24e4f5d4f6956b9` |
| `hyn_cfg.h`, upstream | `63f6ee6292853ae074f7c29d36aab4d7f7b0dd6b` |
| `hyn_cfg.h`, local patch | `f09af188f23b5ffb136a94ad1998048a1261c516` |
| `hyn_chips/cst3530_fw.h` | `87764bf805e7bf8b8819a28d170acb54c5b743e8` |

SHA-256 of locally patched `hyn_cfg.h` is `ea8e7770511aa5f0c1f4c5176c4b6ef682f33d598cd991b27cfa9ae029017a64`. Git blob hashes include the Git object format, so they are not plain SHA-1 of file bytes alone.

**Confirmed.** [Path history](https://api.github.com/repos/Xinyuan-LilyGO/T-Display-S3-Long/commits?path=lib/hyn_driver_for_esp32&per_page=100) has one commit: [b4a73aa306b753225c5c5430b76ed292670fdc96](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/commit/b4a73aa306b753225c5c5430b76ed292670fdc96), author `Lq`, 19 May 2026, with a message about software for the new SCT3530 touch hardware. This import names no original download, agreement or license. The pinned root and driver directory contain no applicable license; existing license files belong to other libraries. Searching all local driver files found no copyright, SPDX or license text. `移植说明.txt` is a porting guide with chip families and I²C interface instructions, without a distribution grant.

**Inference.** The Hynitron version label, generic chip-family table and Chinese porting guide suggest a supplier package modified by LilyGO. They do not prove who owns all rights or under what terms LilyGO received the package. The exact original manufacturer release or a Hynitron publication of this ESP32 version was not found.

## 2. Official LilyGO variants with license files

### T-Deck-Pro: GPLv3 and limited exact overlap

**Confirmed.** [T-Deck-Pro LICENSE.txt at inspected commit 53bcfa5](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/LICENSE.txt) contains GNU GPL version 3. According to [license history](https://api.github.com/repos/Xinyuan-LilyGO/T-Deck-Pro/commits?path=LICENSE.txt&per_page=100), it was added in [c022cd0 on 15 October 2025](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/commit/c022cd006eec56af8781cfd011bd08d700eb6660). [Hyn driver import ee92506](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/commit/ee92506452e3383c675799c9245d0c846327c5a8) followed on 22 December 2025. Both initial Hyn import trees were also compared.

The following exact matches were established:

- NetLink's unchanged `hyn_ts_ext.c`, blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`, is identical to [T-Deck-Pro ESP-IDF hyn_ts_ext.c](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/hyn_ts_ext.c). The identical file was already in the initial Hyn import.
- NetLink's locally patched `hyn_cfg.h`, blob `f09af188f23b5ffb136a94ad1998048a1261c516`, is identical to [T-Deck-Pro ESP-IDF hyn_cfg.h](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/include/hyn_cfg.h).

**Confirmed.** The remaining exact upstream files do not match blobs in the inspected T-Deck-Pro tree. [T-Deck-Pro hyn_cst66xx.c](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/hyn_cst66xx.c) has 275 lines versus S3-Long's 747 and lacks much firmware-upgrade/diagnostic code. A matching version label alone therefore does not justify transferring its license to the complete S3-Long file.

**Confirmed.** [Issue #22, License clarification](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/issues/22), contains a user's code-license question, another user noting the later GPL addition and stale-bot responses. The [complete comments API](https://api.github.com/repos/Xinyuan-LilyGO/T-Deck-Pro/issues/22/comments) contains no maintainer response clarifying Hynitron, third-party code, firmware blobs or license scope. Bot closure does not confirm rights.

**Confirmed, document scope.** `LICENSE.txt` is the standard complete GPLv3 text, including generic instructions for applying it to new programs. It contains no additional LilyGO- or Hynitron-specific scope statement. The inspected README specifies no license scope or exception for this driver. The two files are in normal example source under the root license, with no component exception found.

**Inference.** That root license is positive evidence of GPL publication and may reasonably be read as LilyGO's offered grant for its own/default source. The two byte-identical files therefore need not be treated as entirely unlicensed. Remaining uncertainty concerns the other exact files and undocumented provenance of the vendor component; it is not a general rule that root licenses never apply. This does not establish a conclusive GPL grant for the complete S3-Long driver. Generic application instructions in the GPL text alone also do not reliably choose `-only` versus `-or-later` for this driver.

| `.c` file actually linked by NetLink | Comparison with T-Deck-Pro ESP-IDF source at 53bcfa5 |
|---|---|
| `hyn_core.c` | No same-named file in the Hyn component; example initialization is in `esp_idf/main/touch.c`, so no identical core implementation established. |
| `hyn_i2c.c` | Different blob `73fd15ba07ff7469c3b254561cbcc5ea33288fc3`; T-Deck adds 17 lines at the end with `hyn_delay_ms`, `gpio_set_value`, `gpio_get_value`; other lines match. S3-Long places these helpers in `hyn_core.c`. |
| `hyn_ts_ext.c` | Byte-identical; blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`. |
| `hyn_chips/hyn_cst66xx.c` | Different blob `deba6c6b901c7ecfbb2fd7679a965baa9944aee3`; 275 versus 747 lines. Differences include I²C address 0x1A versus 0x58, logging, optional firmware initialization, firmware update/checksum/boot/test code and function-pointer table. Full diff has 573 lines. |

### T-Deck-MAX and T-Connection-P4-Pro

**Confirmed.** [T-Deck-MAX LICENSE.txt](https://github.com/Xinyuan-LilyGO/T-Deck-MAX/blob/165bf0e04e41c55ab4df88df3abd36a0ececa304/LICENSE.txt) contains MIT with copyright Adafruit Industries 2018. The tree has the same `hyn_ts_ext.c` but no other exact match against the 25 S3-Long upstream blobs. This is MIT, not GPL or BSD. Path history shows the file was already in initial commit `a48d614037c84cec256886db64fe95565f8e9c2e` of 27 April 2026. The inspected README specifies no component license or exception. This root license is also positive publication evidence for the repository, but the Adafruit notice does not explain this Hynitron component's origin. [HynTouch library.properties](https://github.com/Xinyuan-LilyGO/T-Deck-MAX/blob/165bf0e04e41c55ab4df88df3abd36a0ececa304/lib/HynTouch/library.properties) lists `author=OpenAI` and `maintainer=OpenAI`; that metadata field neither states original Hynitron rights nor proves the same developer as the S3-Long import.

| `.c` file actually linked by NetLink | Comparison with T-Deck-MAX at 165bf0e |
|---|---|
| `hyn_core.c` | Absent as a file; MAX has a different `HynTouch.cpp` wrapper and `hyn_platform.cpp`, so no identical core. |
| `hyn_i2c.c` | Different blob `83be1b745c91c49acbad356707759755eeb6fbda`; 92 versus 67 lines. MAX uses `esp32-hal-i2c.h`, `i2cIsInit`/`i2cInit`, different error normalization and virtual GPIO handling; full diff has 66 lines. |
| `hyn_ts_ext.c` | Byte-identical; blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`. |
| `hyn_chips/hyn_cst66xx.c` | Different blob `68edcc970f4ddc1fea396e0034629af6faf4776e`; 276 versus 747 lines. Same kind of reduced variant as T-Deck-Pro with minor additional changes; full diff has 578 lines. |

**Confirmed.** The [T-Connection-P4-Pro tree](https://github.com/Xinyuan-LilyGO/T-Connection-P4-Pro/tree/bb3912510f9ec7622e951b5786763613bdfc6fdf/lib/hyn_driver_for_esp32) contains 22 of the 25 exact S3-Long blobs, including `hyn_cst66xx.c` and all eleven firmware headers. `hyn_core.c`, `hyn_core.h` and `hyn_cst226se.c` differ. No root or driver-directory license was found here either. This confirms further official distribution without establishing permission.

## 3. VIEWESMART: explicit Apache component, nearly the same driver

**Confirmed.** Module supplier VIEWESMART publishes [esp_lcd_touch_cst3530](https://github.com/VIEWESMART/Viewe-esp32-components/tree/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530), with a [component-specific Apache-2.0 license file](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/LICENSE) and a [README stating organization, author, copyright and Apache-2.0](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/README.md). The component appeared in [5f1b1d9 on 11 August 2026](https://github.com/VIEWESMART/Viewe-esp32-components/commit/5f1b1d9e273d71adafe807b2cceab2acced8cbf5).

**Confirmed.** The private HYN layer uses the same Hynitron version label. [Viewe hyn_cst66xx.c](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/private/hyn/hyn_cst66xx.c) is closely related: 756 versus 747 lines; Python `difflib.SequenceMatcher` on lines gives 0.9794. Differences include compiler pragmas, prototype order, firmware header selection, touch-release bookkeeping and one factory-test parameter. None of the 25 exact S3-Long blobs occurs identically in this repository tree.

**Inference.** This is a serious lead for a possible replacement component with explicit license scope, but not a direct Apache grant for the exact LilyGO source. It also has not been established whether Viewe itself has Hynitron permission for all copied private HYN code. Similarity does not authorize attaching Apache to current NetLink input.

## 4. Linux driver is not exact license evidence

[Rockchip hyn_cst66xx.c](https://github.com/rockchip-linux/kernel/blob/77168c8d5ab82399f65a80e9f807b50ba37cf483/drivers/input/touchscreen/hyn/hyn_chips/hyn_cst66xx.c) explicitly contains Hynitron copyright and GPL version 2. A fetched current `develop-6.1` variant has related constants and functions but differs substantially in formatting, platform and content. That supports relatedness at most. **No GPLv2 conclusion for the exact ESP32 files**: a conclusive provenance/license chain is missing. Independent CST3530, CST328 or CST816 drivers also establish nothing about these exact files.

## 5. Build input, linked code and firmware headers separately

**Confirmed from existing local build evidence; no new build performed.** `scripts/prepare_firmware.py` fetches the entire driver directory. The existing PlatformIO build has object files for all eight chip implementations plus the three ordinary `.c` files. Existing `panel-bench/firmware.map` lists objects included from the Hyn archive as `hyn_core.c.o`, `hyn_i2c.c.o`, `hyn_cst66xx.c.o` and `hyn_ts_ext.c.o`. This is more concrete than assuming every available driver is in the final executable; object inclusion still does not mean every function survives garbage collection.

**Confirmed.** With `HYN_POWER_ON_UPDATA=0`, the `#include` of `cst3530_fw.h`, `cst66xx_fw1.h` and `cst66xx_fw2.h` in `hyn_cst66xx.c` is excluded. None of the existing Hyn `.d` dependency files mentions a `_fw` header. Blob headers are present in downloaded source, but this existing build evidence does not show their contents being compiled.

**Unknown.** Distribution rights for firmware headers themselves remain open. Even without those blobs, source rights for the four linked implementations and used headers remain unresolved. The 1→0 patch prevents automatic flashing but creates no license grant and does not remove all update functions from driver source.

## What would resolve the remaining question

A traceable license/permission from the copyright holder for the exact files, or an explicit authorized confirmation of the LilyGO/Hynitron publication's scope, is needed, covering source, modifications, source/binary distribution and potentially firmware headers. An alternative is a demonstrably suitably licensed replacement implementation with its own provenance evidence and separate technical validation. That alternative was neither implemented nor tested here.

This report therefore **does not clear publication/licensing**; it records why exact permission remains unknown despite useful new primary sources.
