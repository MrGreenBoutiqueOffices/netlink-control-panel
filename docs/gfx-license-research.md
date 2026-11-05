# Onderzoek licentie van de exacte Arduino_GFX-vendorcopy

Onderzocht op 2026-11-05. Geen firmware of dependency vervangen. De source is de door LILYGO meegeleverde map `lib/Arduino_GFX-1.3.7` uit commit `3deece89098f25e7d155e41e4e0f5dd8b368ab02`.

## Wat wel vaststaat

De eigen upstream-maintainer reageerde in [Arduino_GFX #240](https://github.com/moononournation/Arduino_GFX/issues/240) op de licentievraag en voegde op 22 augustus 2023 [commit 372094ccbf2579a5a568ca59e5315250bf1ae080](https://github.com/moononournation/Arduino_GFX/commit/372094ccbf2579a5a568ca59e5315250bf1ae080) toe. De [licentietekst op dat commit](https://github.com/moononournation/Arduino_GFX/blob/372094ccbf2579a5a568ca59e5315250bf1ae080/license.txt) is BSD met twee voorwaarden en copyright Adafruit Industries 2012. Een ongewijzigde kopie staat in [licenses/Arduino_GFX-BSD-2-Clause.txt](../licenses/Arduino_GFX-BSD-2-Clause.txt). Dit is primaire onderbouwing van de upstream-licentie, geen willekeurig gekozen licentie voor de hele vendorcopy.

De discussie benoemt dat upstream code uit andere projecten heeft gebruikt. Bestaande componentcopyrights/voorwaarden moeten daarom behouden blijven; de maintainerreactie kan andere rechthebbenden niet vervangen.

## Vergelijking met de vendorcopy

De officiële tag [v1.3.7](https://github.com/moononournation/Arduino_GFX/tree/597ad3e6da7aa6008b7ce69711f6c9ec78d4b635) bevat zelf nog geen rootlicentiebestand. Alle 274 vendorbestanden zijn per relatief pad vergeleken met officiële GitHub-archives van deze tag en het licentiecommit. `exact` betekent identieke bytes; `whitespace` betekent dat uitsluitend witruimte wegfilteren de bestanden gelijk maakt, geen bewijs van gelijke licentierechten.

| Referentie | Exact | Alleen whitespace verschillend | Inhoudelijk verschillend | Alleen in vendorcopy |
| --- | ---: | ---: | ---: | ---: |
| v1.3.7, `597ad3e6da7aa6008b7ce69711f6c9ec78d4b635` | 183 | 71 | 7 | 13 |
| Licentiecommit `372094ccbf2579a5a568ca59e5315250bf1ae080` | 164 | 45 | 52 | 13 |

Inhoudelijke sourceverschillen t.o.v. v1.3.7 zitten in `src/Arduino_GFX_Library.h`, `src/Arduino_DataBus.cpp`, `src/Arduino_GFX.cpp`, `src/Arduino_GFX.h`, `src/Arduino_TFT.cpp` en `src/databus/Arduino_ESP32QSPI.h`; de zevende afwijking is README. De 13 vendor-only bestanden omvatten onder andere extra displayimplementaties voor AXS15231, CO5300 en SH8601 en extra voorbeelden. Die verschillen zijn nog geen toegewezen licentie. De exacte vendorcopy is dus geen ongewijzigde herverpakking van de upstream-tag.

## Conclusie

De upstream-BSD-basis is vastgesteld en vastgelegd. De rechten/notices voor LILYGO-specifieke aanpassingen en toevoegingen blijven een concrete vraag voor LILYGO. De blanketclaim dat alle code in de vendorcopy aantoonbaar BSD-2-Clause is wordt niet gedaan. Deze vraag is opgenomen in de [nog niet verstuurde licentievraag](lilygo-license-inquiry-draft.md); #34 blijft hiervoor open.
