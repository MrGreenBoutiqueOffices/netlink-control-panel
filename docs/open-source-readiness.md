# Voorbereiding van openbaarmaking

Status op 2026-11-05: gekozen licentie voor de eigen projectcode is **GPL-3.0-only**. De repository blijft privé totdat de onderstaande distributiepunten zijn opgelost. Deze documentatie en licentiewijziging veranderen de GitHub-zichtbaarheid niet.

De resterende punten worden gevolgd in [#34](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/34).

## Gecontroleerd

- De repository had nog geen projectlicentie. `LICENSE`, de README en de Python-package metadata leggen nu dezelfde keuze vast. Auteursrechten worden niet naar een andere persoon of rechtspersoon overgedragen.
- Een offline `detect-secrets` 1.5.0-scan van 178 unieke tekstblobs uit de toen opgehaalde lokale Git-geschiedenis vond geen mogelijke secrets. Er zijn geen netwerkverificaties van kandidaten uitgevoerd. Dit is een begrensde scan, geen garantie dat elk type geheim of gevoelige informatie afwezig is.
- `.secrets/`, `artifacts/`, `firmware/.vendor/` en `firmware/.pio/` zijn geen tracked repositorybestanden. GitHub heeft wel al release-assets en Actions-artifacts; die zijn afzonderlijke distributies en worden niet door `.gitignore` beschermd.
- Inter heeft een meegeleverde OFL-licentie. De build haalt daarnaast de gepinde LILYGO-bron en SDK/dependencies op; zie [third-party-vermeldingen](../THIRD_PARTY_NOTICES.md).

## Onderzoeksresultaten van #34

- [Exact driveronderzoek](touchdriver-license-research.md): 24 van 25 lokale upstreambestanden zijn identiek; de enige lokale patch schakelt touchcontroller-flashing uit. De bestaande build linkt vier Hyn-implementaties. Verwante officiële GPL-source dekt twee identieke bestanden als publicatiespoor, maar stelt de toestemming voor de volledige exacte copy niet vast. De firmwareblobheaders worden met de huidige patch niet gecompileerd; bronrechten voor de gebruikte drivercode blijven nodig.
- [GFX-onderzoek](gfx-license-research.md): de maintainer heeft aantoonbaar een upstream-BSD-licentie toegevoegd. De LILYGO-copy heeft inhoudelijke wijzigingen en toevoegingen; die worden niet automatisch opnieuw gelicentieerd.
- Remote momentopname: alle 42 bestaande afgeronde Actions-logarchieven, 19 niet-verlopen artifacts en 5 release-assets van v0.8.0 zijn succesvol opgehaald. Er waren geen onbeschikbare downloads. De detect-secrets 1.5.0-scan zonder netwerkverificatie vond 0 kandidaten in 402 tekstbestanden, inclusief uitgepakte protocolsource en `strings -a` van firmwarebinaries. De SHA256SUMS van alle 20 release/candidate-bundles zijn ook voor de volledige binaire/archivebytes geverifieerd. Zie de [inhoudsvrije inventaris met IDs, omvang en SHA-256](evidence/publication-remote-inventory.json). Dit is een secret-/integriteitscontrole, geen definitieve licentieclearance of bewijs dat elke mogelijke gevoelige inhoud afwezig is; afbeeldingen zijn niet met OCR gecontroleerd. De momentopname omvat niet de later voor deze onderzoeks-PR aangemaakte runs.
- Protocol-core 1.0.1 bevat voortaan GPL, third-party-inventaris en OFL met digests in `UPSTREAM.json`. Protocol-/transportcode en consumerdigests zijn ongewijzigd. De nieuwe archivehash en pakketversie vereisen expliciete consumeradoptie; bestaande releases zijn niet overschreven. Dit lost de volledige firmware-notices/source-/installatielevering nog niet op.
- De projectlicentie staat in de nog open PR #35. Deze onderzoekswijzigingen bouwen daarop voort; vóór openbaarmaking moet ook die licentie op main staan.

Er is een [concrete openbare vraag aan LILYGO voorbereid](lilygo-license-inquiry-draft.md), maar niet verstuurd. Een bericht namens het bedrijf vereist eerst een expliciete opdracht. Er is geen driver vervangen en geen fysieke firmwaretest uitgevoerd.

## Nog nodig vóór publiek zetten

1. Stel de licentie/distributietoestemming vast van de Hynitron-touchdriver in de gepinde LILYGO-bron. In de geraadpleegde root en drivermap ontbreekt een duidelijke licentievermelding. GPL voor onze eigen code lost dit niet op. Alternatieven zijn aantoonbare toestemming of een vervangende driver met passende licentie; er is nog geen upstream-bericht verstuurd.
2. Stel voor de exacte Arduino_GFX-vendorcopy de toepasselijke notices vast en verzamel de overige notices van de daadwerkelijk meegebouwde componenten. Een licentietekst van de huidige upstream is niet automatisch bewijs voor die vendorcopy.
3. Zorg bij de firmware-assets en het protocol-core-archive voor de toepasselijke licenties, corresponderende broncode en reproduceerbare buildinformatie; lever waar GPL dat vereist ook installatie-informatie om eigen aangepaste software te kunnen installeren. De bestaande USB-herstelroute en de OTA-signingpolicy moeten hierin expliciet worden meegenomen. Productiesigningkeys of pairinggegevens worden niet als vanzelf openbaar gemaakt.
4. Controleer ook de bestaande releases, Actions-artifacts en Actions-logs op distributievoorwaarden en gevoelige inhoud voordat de zichtbaarheid wijzigt. De remote momentopname hierboven vult de lokale Git-scan aan; de licentie-/distributiepunten van historische firmware zijn daarmee nog niet opgelost. Er zijn geen oude assets of runs verwijderd.

Wanneer deze punten zijn opgelost, kunnen releases van deze repository rechtstreeks als publieke updatebron dienen. Een aparte firmware-repository of updateserver is dan niet nodig. Het paneel moet nog steeds lokaal de onafhankelijke releasehandtekening en compatibiliteit controleren; openbaar downloaden verleent geen installatievertrouwen.

Bronnen: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html), [GPL-3.0-only SPDX-tekst](https://github.com/spdx/license-list-data/blob/main/text/GPL-3.0-only.txt), [GitHub-zichtbaarheid en openbare Actions-geschiedenis](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), [gepinde LILYGO-bron](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02).
