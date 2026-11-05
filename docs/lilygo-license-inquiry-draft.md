# Conceptvraag aan LILYGO — nog niet verstuurd

Doelrepository: `Xinyuan-LilyGO/T-Display-S3-Long`. De vraag hieronder is gereed voor een openbare GitHub-issue. Er is nog geen bericht namens het bedrijf geplaatst.

## Title

Clarify redistribution license for the CST3530 Hynitron driver and bundled Arduino_GFX changes

## Body

We are preparing to publish our own GPLv3-licensed application firmware for the T-Display S3 Long with CST3530 touch. We use your repository at commit `3deece89098f25e7d155e41e4e0f5dd8b368ab02` and would like to preserve the correct upstream license notices.

Could you clarify the applicable license and the original copyright/licensing source for:

1. `lib/hyn_driver_for_esp32`, imported by commit `b4a73aa306b753225c5c5430b76ed292670fdc96`, version `Hynitron V2.10 20241111`, especially `hyn_core.c`, `hyn_i2c.c`, `hyn_ts_ext.c`, `hyn_chips/hyn_cst66xx.c` and their headers?
2. The bundled `*_fw.h` controller-firmware arrays: are they covered by the same terms or separate redistribution terms? We disable `HYN_POWER_ON_UPDATA`, so those arrays are currently not included in our compiled application.
3. The changes/additions in your bundled `lib/Arduino_GFX-1.3.7`, including `src/Arduino_GFX.cpp`, `src/Arduino_TFT.cpp`, `src/Arduino_DataBus.cpp`, `src/databus/Arduino_ESP32QSPI.h` and the additional display drivers? Upstream Arduino_GFX added a BSD license in commit `372094ccbf2579a5a568ca59e5315250bf1ae080` following issue #240, but the bundled copy differs from the upstream v1.3.7 tag.

We found related Hynitron source in T-Deck-Pro under its GPLv3 root license and a CST3530 component published by VIEWESMART under Apache-2.0. They are useful references, but do not establish the terms for every file in this exact S3-Long copy.

We did not find a root or component license covering these files in the pinned S3-Long tree. Please point us to the applicable license text or a statement from the relevant copyright holder covering modifications and source/binary redistribution. If possible, adding component-specific notices to the repository would make the intended scope clear for downstream users.

We have not assigned our project license to these third-party files or published our firmware assets while this remains unclear. Thank you for helping us attribute and distribute them correctly.
