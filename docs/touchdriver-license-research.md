# Onderzoek licentie Hynitron-touchdriver van NetLink Panel

Onderzocht op 5 november 2026. Alleen bronpublicaties, GitHub-historie, bestaande issues en lokale bron-/buildbestanden gebruikt. Geen maintainer benaderd, geen issue geplaatst, niets gepubliceerd en geen hardware aangeraakt.

## Uitkomst

**Unknown: er is geen expliciete licentie of distributietoestemming vastgesteld die de volledige exacte NetLink-input `Xinyuan-LilyGO/T-Display-S3-Long@3deece89098f25e7d155e41e4e0f5dd8b368ab02/lib/hyn_driver_for_esp32` dekt.** De vindbare verwante GPL- en Apache-publicaties leveren nuttig herkomstbewijs, maar sluiten deze vraag niet.

Er zijn twee rechtstreekse byte-identieke koppelingen met een andere officiële LilyGO-repository met GPLv3-rootlicentie: `hyn_ts_ext.c` en de lokaal gepatchte `hyn_cfg.h`. Dat is sterker dan alleen een overeenkomstige chipnaam, maar geeft geen licentiebewijs voor de overige exacte bestanden, de complete driver of de meegeleverde firmwareblobheaders. Een claim dat de hele NetLink-driver GPL-3.0-only of Apache-2.0 is, wordt door dit onderzoek niet gedragen.

## 1. Exacte NetLink-input en herkomst

**Confirmed.** De [vastgepinde upstreamboom](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02/lib/hyn_driver_for_esp32) bevat 25 bestanden. Een lokale Git-blobhashvergelijking van alle 25 bestanden met de [GitHub tree-API](https://api.github.com/repos/Xinyuan-LilyGO/T-Display-S3-Long/git/trees/3deece89098f25e7d155e41e4e0f5dd8b368ab02?recursive=1) bevestigt 24 identieke bestanden en precies één afwijking: `hyn_cfg.h`, waarin NetLink `HYN_POWER_ON_UPDATA` van 1 naar 0 zet. Het versielabel is `== Hynitron V2.10 20241111 ==`.

| Bestand | Upstream Git-blob SHA-1 |
|---|---|
| `hyn_core.c` | `728e45f5429d4a296d59efc0465c0708327dbb6e` |
| `hyn_core.h` | `2c69c43d067091b7a7644c0a557ddf0e6646c9a9` |
| `hyn_i2c.c` | `5f1d82f8570761d3bf15ae3ce0ddc48505d113a4` |
| `hyn_ts_ext.c` | `d2c51a583639add3c9f3fdd009da0b68b18ca6e3` |
| `hyn_chips/hyn_cst66xx.c` | `9adf049c0d033306d976e2cce24e4f5d4f6956b9` |
| `hyn_cfg.h`, upstream | `63f6ee6292853ae074f7c29d36aab4d7f7b0dd6b` |
| `hyn_cfg.h`, lokale patch | `f09af188f23b5ffb136a94ad1998048a1261c516` |
| `hyn_chips/cst3530_fw.h` | `87764bf805e7bf8b8819a28d170acb54c5b743e8` |

De SHA-256 van de lokale gepatchte `hyn_cfg.h` is `ea8e7770511aa5f0c1f4c5176c4b6ef682f33d598cd991b27cfa9ae029017a64`. Git-blobhashes zijn over het Git-objectformaat berekend, dus niet de gewone SHA-1 van alleen de bestandsbytes.

**Confirmed.** De [padgeschiedenis](https://api.github.com/repos/Xinyuan-LilyGO/T-Display-S3-Long/commits?path=lib/hyn_driver_for_esp32&per_page=100) heeft één commit: [b4a73aa306b753225c5c5430b76ed292670fdc96](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/commit/b4a73aa306b753225c5c5430b76ed292670fdc96), auteur `Lq`, 19 mei 2026, met bericht over software voor de nieuwe SCT3530-touchhardware. Deze import noemt geen oorspronkelijke download, contract of licentie. In de vastgepinde root en drivermap staat geen toepasselijke licentie; aanwezige licentiebestanden horen bij andere bibliotheken. Zoeken in alle lokale driverbestanden vond geen copyright-, SPDX- of licentietekst. `移植说明.txt` is een portinghandleiding met chipfamilies en I²C-interface-instructies, zonder distributiegrant.

**Inference.** Het Hynitron-versielabel, de generieke chipfamilietabel en de Chinese portinghandleiding wijzen op een leverancierspakket dat LilyGO heeft aangepast. Zij bewijzen niet wie alle rechten bezit of onder welke voorwaarden LilyGO dat pakket ontving. De exacte oorspronkelijke fabrikantrelease of een Hynitron-publicatie van deze ESP32-versie is niet gevonden.

## 2. Officiële LilyGO-varianten met licentiebestanden

### T-Deck-Pro: GPLv3 en beperkte exacte overlap

**Confirmed.** [T-Deck-Pro LICENSE.txt op onderzocht commit 53bcfa5](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/LICENSE.txt) bevat de GNU GPL versie 3. Volgens de [licentiegeschiedenis](https://api.github.com/repos/Xinyuan-LilyGO/T-Deck-Pro/commits?path=LICENSE.txt&per_page=100) werd deze toegevoegd in [c022cd0 op 15 oktober 2025](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/commit/c022cd006eec56af8781cfd011bd08d700eb6660). De [Hyn-driverimport ee92506](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/commit/ee92506452e3383c675799c9245d0c846327c5a8) volgde op 22 december 2025. Ook de twee eerste Hyn-importbomen zijn vergeleken.

De volgende exacte overeenkomsten zijn vastgesteld:

- NetLinks ongewijzigde `hyn_ts_ext.c`, blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`, is identiek aan [T-Deck-Pro ESP-IDF hyn_ts_ext.c](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/hyn_ts_ext.c). Het identieke bestand zat al in de eerste Hyn-import.
- NetLinks lokaal gepatchte `hyn_cfg.h`, blob `f09af188f23b5ffb136a94ad1998048a1261c516`, is identiek aan [T-Deck-Pro ESP-IDF hyn_cfg.h](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/include/hyn_cfg.h).

**Confirmed.** De overige exacte upstreambestanden matchen niet met blobs in de onderzochte T-Deck-Pro-boom. De [T-Deck-Pro hyn_cst66xx.c](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/blob/53bcfa593b1df064894a8efc5a7e15e4524b09d2/examples/touch_hyn_core/esp_idf/components/hyn_core/hyn_cst66xx.c) telt 275 regels tegenover 747 in S3-Long en mist veel firmware-upgrade-/diagnostiekcode. Alleen het gelijke versielabel rechtvaardigt dus geen licentieoverdracht naar het volledige S3-Long-bestand.

**Confirmed.** [Issue #22, License clarification](https://github.com/Xinyuan-LilyGO/T-Deck-Pro/issues/22), bevat een gebruikersvraag naar de codelicentie, een andere gebruiker die de latere GPL-toevoeging signaleert, en stale-botreacties. De [volledige comment-API](https://api.github.com/repos/Xinyuan-LilyGO/T-Deck-Pro/issues/22/comments) bevat geen maintainerantwoord dat Hynitron, derdepartijcode, firmwareblobs of de licentiescope verduidelijkt. De sluiting door een bot is geen bevestiging van rechten.

**Confirmed, scope van het document.** `LICENSE.txt` is de standaard volledige GPLv3-tekst, inclusief de generieke instructies om die licentie op nieuwe programma’s toe te passen. Er staat geen extra LilyGO- of Hynitron-specifieke scopeverklaring in. In de onderzochte README staan geen licentiescope of uitzonderingen voor deze driver. De twee bestanden liggen in de gewone voorbeeldsource onder de rootlicentie, zonder aangetroffen componentuitzondering.

**Inference.** Die rootlicentie is positief bewijs van GPL-publicatie en kan redelijkerwijs als de door LilyGO aangeboden grant voor eigen/default-source worden gelezen. De twee byte-identieke bestanden hoeven dus niet als volledig licentieloos te worden beschouwd. De overgebleven onzekerheid betreft de andere exacte bestanden en de ongedocumenteerde herkomst van de vendorcomponent; niet een algemene regel dat rootlicenties nooit zouden gelden. Een sluitende GPL-grant voor de complete S3-Long-driver volgt hier niet uit. De generieke toepassingsinstructies in de GPL-tekst alleen kiezen ook niet betrouwbaar `-only` versus `-or-later` voor deze driver.

| Werkelijk door NetLink gelinkt `.c`-bestand | Vergelijking met T-Deck-Pro ESP-IDF-bron op 53bcfa5 |
|---|---|
| `hyn_core.c` | Geen gelijknamig bestand in de Hyn-component; de voorbeeldinitialisatie zit in `esp_idf/main/touch.c`, dus geen identieke core-implementatie vastgesteld. |
| `hyn_i2c.c` | Andere blob `73fd15ba07ff7469c3b254561cbcc5ea33288fc3`; T-Deck heeft onderaan 17 extra regels met `hyn_delay_ms`, `gpio_set_value`, `gpio_get_value`; de overige regels matchen. Deze helpers staan bij S3-Long in `hyn_core.c`. |
| `hyn_ts_ext.c` | Byte-identiek; blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`. |
| `hyn_chips/hyn_cst66xx.c` | Andere blob `deba6c6b901c7ecfbb2fd7679a965baa9944aee3`; 275 versus 747 regels. Verschillen omvatten I²C-adres 0x1A versus 0x58, logging, optionele firmware-initialisatie, firmware-update-/checksum-/boot-/testcode en functiepointertabel. De volledige diff telt 573 regels. |

### T-Deck-MAX en T-Connection-P4-Pro

**Confirmed.** [T-Deck-MAX LICENSE.txt](https://github.com/Xinyuan-LilyGO/T-Deck-MAX/blob/165bf0e04e41c55ab4df88df3abd36a0ececa304/LICENSE.txt) bevat MIT met copyright Adafruit Industries 2018. De boom heeft dezelfde `hyn_ts_ext.c`, maar geen verdere exacte overeenkomst met de 25 S3-Long-upstreamblobs. Dit is dus MIT, niet GPL of BSD. Het bestand zat volgens de padgeschiedenis al in de eerste commit `a48d614037c84cec256886db64fe95565f8e9c2e` van 27 april 2026. De onderzochte README specificeert geen componentlicentie of uitzondering. Ook deze rootlicentie is positief publicatiebewijs voor de repository, maar de Adafruit-vermelding verklaart de oorsprong van deze Hynitron-component niet. De [HynTouch library.properties](https://github.com/Xinyuan-LilyGO/T-Deck-MAX/blob/165bf0e04e41c55ab4df88df3abd36a0ececa304/lib/HynTouch/library.properties) noemt `author=OpenAI` en `maintainer=OpenAI`; dat metadata-veld is geen verklaring over de oorspronkelijke Hynitronrechten en bewijst evenmin dezelfde ontwikkelaar als de S3-Long-import.

| Werkelijk door NetLink gelinkt `.c`-bestand | Vergelijking met T-Deck-MAX op 165bf0e |
|---|---|
| `hyn_core.c` | Ontbreekt als bestand; MAX heeft een andere `HynTouch.cpp`-wrapper en `hyn_platform.cpp`, dus geen identieke core. |
| `hyn_i2c.c` | Andere blob `83be1b745c91c49acbad356707759755eeb6fbda`; 92 versus 67 regels. MAX gebruikt `esp32-hal-i2c.h`, `i2cIsInit`/`i2cInit`, andere foutnormalisatie en virtuele GPIO-afhandeling; volledige diff 66 regels. |
| `hyn_ts_ext.c` | Byte-identiek; blob `d2c51a583639add3c9f3fdd009da0b68b18ca6e3`. |
| `hyn_chips/hyn_cst66xx.c` | Andere blob `68edcc970f4ddc1fea396e0034629af6faf4776e`; 276 versus 747 regels. Zelfde soort uitgeklede variant als T-Deck-Pro, met extra kleine aanpassingen; volledige diff 578 regels. |

**Confirmed.** De [T-Connection-P4-Pro-boom](https://github.com/Xinyuan-LilyGO/T-Connection-P4-Pro/tree/bb3912510f9ec7622e951b5786763613bdfc6fdf/lib/hyn_driver_for_esp32) bevat 22 van de 25 exacte S3-Long-blobs, inclusief `hyn_cst66xx.c` en alle elf firmwareheaders. `hyn_core.c`, `hyn_core.h` en `hyn_cst226se.c` verschillen. Ook hier is geen root- of drivermaplicentie gevonden. Dit bevestigt verdere officiële verspreiding, zonder de toestemming vast te stellen.

## 3. VIEWESMART: expliciet Apache-component, bijna dezelfde driver

**Confirmed.** De moduleleverancier VIEWESMART publiceert [esp_lcd_touch_cst3530](https://github.com/VIEWESMART/Viewe-esp32-components/tree/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530), met een [componentgebonden Apache-2.0-licentiebestand](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/LICENSE) en een [README met organisatie, auteur, copyright en Apache-2.0](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/README.md). De component verscheen in [5f1b1d9 op 11 augustus 2026](https://github.com/VIEWESMART/Viewe-esp32-components/commit/5f1b1d9e273d71adafe807b2cceab2acced8cbf5).

**Confirmed.** De private HYN-laag gebruikt hetzelfde Hynitron-versielabel. Het [Viewe hyn_cst66xx.c](https://github.com/VIEWESMART/Viewe-esp32-components/blob/c9c6134456101a7d04c0fc2138f861f1f5d59359/touch/esp_lcd_touch_cst3530/private/hyn/hyn_cst66xx.c) is sterk verwant: 756 versus 747 regels; Python `difflib.SequenceMatcher` op regels geeft 0,9794. De verschillen zitten onder meer in compilerpragma's, prototypevolgorde, firmwareheaderkeuze, touch-releaseadministratie en één factory-testparameter. Geen van de 25 exacte S3-Long-blobs komt identiek voor in deze repositoryboom.

**Inference.** Dit is een serieus spoor voor een mogelijke vervangende component met expliciete licentiescope, maar geen rechtstreekse Apache-grant voor de exacte LilyGO-source. Evenmin is vastgesteld of Viewe zelf toestemming van Hynitron heeft voor alle overgenomen private HYN-code. De overeenkomst geeft geen vrijbrief om Apache op de huidige NetLink-input te plakken.

## 4. Linux-driver is geen exact licentiebewijs

De [Rockchip hyn_cst66xx.c](https://github.com/rockchip-linux/kernel/blob/77168c8d5ab82399f65a80e9f807b50ba37cf483/drivers/input/touchscreen/hyn/hyn_chips/hyn_cst66xx.c) bevat expliciet Hynitron-copyright en GPL versie 2. Een opgehaalde huidige `develop-6.1`-variant heeft verwante constanten en functies, maar verschilt sterk in opmaak, platform en inhoud. Dat onderbouwt hoogstens verwantschap. **Geen GPLv2-conclusie voor de exacte ESP32-bestanden**: daarvoor ontbreekt een sluitende herkomst-/licentieketen. Ook onafhankelijke CST3530-, CST328- of CST816-drivers bewijzen niets over deze exacte bestanden.

## 5. Buildinput, gelinkte code en firmwareheaders apart

**Confirmed, lokaal bestaand buildbewijs; geen nieuwe build uitgevoerd.** `scripts/prepare_firmware.py` haalt de hele drivermap op. De bestaande PlatformIO-build heeft objectbestanden van alle acht chipimplementaties plus de drie gewone `.c`-bestanden. De bestaande `panel-bench/firmware.map` noemt als uit de Hyn-archive opgenomen objecten `hyn_core.c.o`, `hyn_i2c.c.o`, `hyn_cst66xx.c.o` en `hyn_ts_ext.c.o`. Dat is concreter dan aannemen dat alle beschikbare drivers in het uiteindelijke executable zitten; objectopname betekent nog niet dat iedere functie na garbage collection behouden blijft.

**Confirmed.** Met `HYN_POWER_ON_UPDATA=0` valt de `#include` van `cst3530_fw.h`, `cst66xx_fw1.h` en `cst66xx_fw2.h` in `hyn_cst66xx.c` weg. Geen van de aanwezige Hyn `.d`-dependencybestanden vermeldt een `_fw`-header. De blobheaders zitten wel in de opgehaalde bronmap, maar dit bestaande buildbewijs laat geen compilatie van hun inhoud zien.

**Unknown.** Distributierechten voor de firmwareheaders zelf blijven open. Ook zonder die blobs blijven de bronrechten van de vier gelinkte implementaties en gebruikte headers onopgelost. De 1→0-patch verhindert de automatische flashingroute, maar creëert geen licentiegrant en verwijdert niet alle updatefuncties uit de driverbron.

## Wat de resterende vraag precies zou sluiten

Nodig is een herleidbare licentie/toestemming van de rechthebbende voor de exacte bestanden of een expliciete, bevoegde bevestiging van de scope van de LilyGO-/Hynitronpublicatie, inclusief broncode, aanpassingen, source- en binarydistributie en eventueel de firmwareheaders. Een alternatief is een aantoonbaar passend gelicentieerde vervangende implementatie met eigen herkomstbewijs en aparte technische validatie. Dat alternatief is hier niet geïmplementeerd of getest.

Dit rapport stelt dus **publicatie/licentie niet vrij**; het documenteert waarom de exacte toestemming ondanks bruikbare nieuwe primaire bronnen onbekend blijft.
