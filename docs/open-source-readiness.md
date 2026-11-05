# Voorbereiding van openbaarmaking

Status op 2026-11-05: gekozen licentie voor de eigen projectcode is **GPL-3.0-only**. De repository blijft privé totdat de onderstaande distributiepunten zijn opgelost. Deze documentatie en licentiewijziging veranderen de GitHub-zichtbaarheid niet.

De resterende punten worden gevolgd in [#34](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/34).

## Gecontroleerd

- De repository had nog geen projectlicentie. `LICENSE`, de README en de Python-package metadata leggen nu dezelfde keuze vast. Auteursrechten worden niet naar een andere persoon of rechtspersoon overgedragen.
- Een offline `detect-secrets` 1.5.0-scan van 178 unieke tekstblobs uit de toen opgehaalde lokale Git-geschiedenis vond geen mogelijke secrets. Er zijn geen netwerkverificaties van kandidaten uitgevoerd. Dit is een begrensde scan, geen garantie dat elk type geheim of gevoelige informatie afwezig is.
- `.secrets/`, `artifacts/`, `firmware/.vendor/` en `firmware/.pio/` zijn geen tracked repositorybestanden. GitHub heeft wel al release-assets en Actions-artifacts; die zijn afzonderlijke distributies en worden niet door `.gitignore` beschermd.
- Inter heeft een meegeleverde OFL-licentie. De build haalt daarnaast de gepinde LILYGO-bron en SDK/dependencies op; zie [third-party-vermeldingen](../THIRD_PARTY_NOTICES.md).

## Nog nodig vóór publiek zetten

1. Stel de licentie/distributietoestemming vast van de Hynitron-touchdriver in de gepinde LILYGO-bron. In de geraadpleegde root en drivermap ontbreekt een duidelijke licentievermelding. GPL voor onze eigen code lost dit niet op. Alternatieven zijn aantoonbare toestemming of een vervangende driver met passende licentie; er is nog geen upstream-bericht verstuurd.
2. Stel voor de exacte Arduino_GFX-vendorcopy de toepasselijke notices vast en verzamel de overige notices van de daadwerkelijk meegebouwde componenten. Een licentietekst van de huidige upstream is niet automatisch bewijs voor die vendorcopy.
3. Zorg bij de firmware-assets en het protocol-core-archive voor de toepasselijke licenties, corresponderende broncode en reproduceerbare buildinformatie; lever waar GPL dat vereist ook installatie-informatie om eigen aangepaste software te kunnen installeren. De bestaande USB-herstelroute en de OTA-signingpolicy moeten hierin expliciet worden meegenomen. Productiesigningkeys of pairinggegevens worden niet als vanzelf openbaar gemaakt.
4. Controleer ook de bestaande releases, Actions-artifacts en Actions-logs op distributievoorwaarden en gevoelige inhoud voordat de zichtbaarheid wijzigt. De lokale Git-scan omvatte deze externe bestanden en logs niet. Er zijn geen oude assets of runs verwijderd.

Wanneer deze punten zijn opgelost, kunnen releases van deze repository rechtstreeks als publieke updatebron dienen. Een aparte firmware-repository of updateserver is dan niet nodig. Het paneel moet nog steeds lokaal de onafhankelijke releasehandtekening en compatibiliteit controleren; openbaar downloaden verleent geen installatievertrouwen.

Bronnen: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html), [GPL-3.0-only SPDX-tekst](https://github.com/spdx/license-list-data/blob/main/text/GPL-3.0-only.txt), [GitHub-zichtbaarheid en openbare Actions-geschiedenis](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), [gepinde LILYGO-bron](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02).
