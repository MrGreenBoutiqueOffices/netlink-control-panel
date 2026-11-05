# Onderdelen van derden

`LICENSE` geldt voor de eigen projectcode. Bestaande auteursrechten, licenties en eventuele aanvullende voorwaarden van derden blijven gelden. Deze inventaris is geen volledige verzameling van alle licentieteksten van een firmwarebuild en geeft geen nieuwe rechten op upstream-code.

## In deze repository opgenomen

- **Inter**: Copyright 2020 The Inter Project Authors. Het font `preview/assets/inter.ttf` en de daarvan gegenereerde embedded glyphs blijven onder de SIL Open Font License 1.1. De volledige licentie staat in [preview/assets/OFL.txt](preview/assets/OFL.txt).
- **Ontwerpen en pictogrammen**: aangeleverd voor dit project; de herkomst en uitsneden zijn beschreven in [preview/assets/README.md](preview/assets/README.md). Deze vermelding kent geen rechten toe op eventuele merken of materiaal van derden in de ontwerpen.

## Door de build opgehaalde software

De build haalt dependencies op; `firmware/.vendor/` en `firmware/.pio/` worden niet in Git opgenomen. Downloaden maakt hun licentievoorwaarden niet gelijk aan die van deze repository.

| Onderdeel | Vastgestelde informatie / te behouden vermelding |
| --- | --- |
| ArduinoJson 6.21.5 | MIT, Benoit BLANCHON; volledige upstream-licentietekst bij distributie behouden |
| Arduino ESP32 core 2.0.14 | De geraadpleegde core-header vermeldt LGPL-2.1-or-later; SDK, libraries en andere componenten hebben eigen voorwaarden |
| ESP-IDF / mbedTLS | Componentlicenties en notices uit de exacte gebruikte SDK behouden; de applicatie-GPL vervangt ze niet |
| Arduino_GFX 1.3.7 uit de gepinde LILYGO-bron | Upstream-maintainer en licentiecommit bevestigen een BSD-basis; de exacte vendorcopy heeft aanpassingen en extra bestanden. Zie [GFX-onderzoek](docs/gfx-license-research.md) en de [upstream-BSD-tekst](licenses/Arduino_GFX-BSD-2-Clause.txt); rechten/notices voor vendorwijzigingen blijven open |
| Hynitron-touchdriver uit de gepinde LILYGO-bron | Geen sluitende toestemming voor de volledige exacte copy gevonden. Twee bestanden matchen officiële GPL-source; de andere gelinkte bestanden blijven onopgelost. Zie [driveronderzoek](docs/touchdriver-license-research.md) |
| Python `cryptography` 50.0.2 | Package metadata: `Apache-2.0 OR BSD-3-Clause`; eigen notices en eventuele meegeleverde componentlicenties behouden |
| Python `pyserial` 3.5 | Package metadata: BSD; de licentie en vermeldingen uit de gebruikte distributie behouden |

De exacte LILYGO-bron is commit `3deece89098f25e7d155e41e4e0f5dd8b368ab02`. Zie [prepare_firmware.py](scripts/prepare_firmware.py) en [platformio.ini](firmware/platformio.ini) voor de selectie en vaste versies. Build- en ontwikkeltools hebben daarnaast hun eigen licenties; ze worden hiermee niet opnieuw gelicentieerd.

Voor publieke firmwaredistributie moeten volledige toepasselijke notices, corresponderende broncode, buildinformatie en waar van toepassing installatie-informatie beschikbaar zijn. De lijst hierboven vervangt die leveringsplicht niet. De concrete open punten staan in [open-source-readiness](docs/open-source-readiness.md).
