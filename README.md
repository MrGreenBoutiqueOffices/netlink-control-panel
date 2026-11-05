# NetLink Panel

Een werkprototype voor de LILYGO T-Display S3 Long: een compact bedienpaneel voor bureau en monitor. De directe USB-koppeling met een NetLink wordt de standaard; wifi blijft optioneel. Zelfstandig ondertekend updaten via wifi wordt onderdeel van de firmware. Dit is vervolgwerk en werkt nog niet in de huidige build.

## Actuele stand — 4 november 2026

Firmware **0.8.0 uit broncommit `e8d2232` is via USB geïnstalleerd op het prototype**. De flashhash en daarna de draaiende versie, imagehash, VALID-bootstatus en display/touch-startupcontrole zijn geverifieerd. Na opnieuw aansluiten werkte USB weer. De fabrieksbackup is behouden. De gebruiker test de pijlfeedback en instellingen; volledige fysieke acceptatie staat nog open. Een nieuwe CI-build of merge installeert niets op het display.

| Onderdeel | Stand |
| --- | --- |
| Native displaydemo | 17 aangeleverde ontwerpen, volledig lokale simulatie zonder NetLink |
| Hoogtebediening | Tik kiest 1 cm; hold herhaalt; release houdt de doelhoogte vast; pas Bevestigen start de simulatie; grenzen 62–127 cm |
| Paneel | Helderheid, dimtijd, 180°-rotatie en versienummer onder Meer → Paneel; lokale instellingen worden vanaf 0.8.0 gevalideerd en over herstarts bewaard; fysieke gebruikersacceptatie loopt |
| Firmware 0.8.0 | Herstelt de pijl-drukkleur na loslaten en voegt blijvende lokale paneelinstellingen toe |
| USB/wifi-bench | Mac/Linux-hostprogramma, begrensd JSON-protocol, simulator en geauthenticeerde versleutelde wifi-verbinding |
| OTA | Dual-slot, hervatten en bootbevestiging/rollback geïmplementeerd; grotere firmwareoverdracht nog onvoldoende betrouwbaar; USB is de huidige installatieroute |
| Echte bediening | Nog geen NetLink panel-service, MQTT-koppeling of echte bureau-/monitorcommando’s |
| Beheer en releases | PR-/main-controles en commitgebonden firmware-/protocolartifacts; Release Drafter beheert de draft en notities; na publicatie krijgt die release de gebouwde firmware-assets. Geen automatische flash of fleetdeploy; zie [releaseprocedure](docs/releases.md) |

De lokale demo blijft bedienbaar zonder beheersessie. Monitorfuncties, voorkeuren, fouten en afstellen zijn voorbeeldgedrag, geen aansturing of detectie van echte apparatuur. De ingestelde paneelhelderheid schaalt de gerenderde pixels; fysieke backlightregeling is nog niet aangetoond.

Zie [bediening en installatiegeschiedenis](docs/display-demo.md), [visuele QA](design-qa.md) en [de ontwerpen](docs/design/netlink-bedienpaneel.pdf). Eerdere bench- en OTA-rapporten bevatten historische resultaten; de tabel hierboven geeft de actuele projectstatus.

## Read-only statuspad (0.7.0 gemerged)

De nieuwe firmwarecapability kan echte hoogte en geselecteerde monitorstatus vanuit `netlink-webserver` tonen. Er is geen Dell-monitor vereist; een Waveshare of een bureau zonder monitor blijft bruikbaar. Waarnemingen, laatst bekende waarden en onbekende status zijn onderscheiden. Alle apparaatbediening blijft geblokkeerd. De firmwareondersteuning zit in de geïnstalleerde 0.8.0; de webserverintegratie wacht nog op review en is niet fysiek met een NetLink geaccepteerd. Zie [het statuscontract](docs/production-protocol.md).

## Lokale paneelinstellingen in 0.8.0

Pijlknoppen tonen hun drukkleur alleen tijdens de aanraking; na loslaten blijven de gekozen doelhoogte en bevestiging staan. Fysieke wijzigingen van helderheid, dimtijd en rotatie worden bij loslaten opgeslagen, met schema, revisie en een vorige geldige configuratie als herstelpunt. Een mislukte opslag herstelt de eerder opgeslagen instellingen. De productie-status bevat alleen de opgeslagen configuratie en eventuele opslagfout; beheerde wijzigingen blijven geblokkeerd. Bureaupresets en wifi-credentials vallen buiten deze UI-configuratie. Zie [opslag, eigenaarschap en verificatie](docs/panel-settings.md).

## Demo proberen

Op het display: Meer opent Monitor, Voorkeuren en Paneel. Pijlen en presets kiezen alleen een doelhoogte. Annuleren verwerpt de keuze; Bevestigen start een lokale beweging. Een aanraking tijdens die beweging stopt de simulatie. De eerste aanraking na ruststand wekt alleen het scherm.

Extra ontwerpscenario’s: houd in Meer het lege vak rechtsonder minimaal één seconde vast. Houd in de statusvoorbeelden links vast om verder te bladeren. Er is geen automatische schermcarrousel.

Zonder display: open `preview/index.html`. De browserpreview bevat de eerdere acht schermen en staat los van USB, firmware en echte apparatuur. De native displaydemo is de primaire implementatie van de nieuwste 17 schermen.

## Ontwikkelen en controleren

Installeer [uv](https://docs.astral.sh/uv/getting-started/installation/) en voer vanuit de projectmap uit:

```sh
uv sync --locked --group dev
uv run panel bench --simulate
uv run python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked ruff format --check .
node --check preview/app.js
```

De CI draait hetzelfde pad met [gevalideerde artifacts en een versiegrens voor de webserver](docs/releases.md). Generated assets kunnen zonder checkoutwijziging worden gecontroleerd met `uv run --locked python scripts/generate_demo_assets.py --check`.

De tests omvatten framing, sessies, TLS, updateherstel en de echte native C++-toestandsmachine/renderer. De simulator gebruikt een pseudo-terminalpaar en verstuurt geen hardwarecommando’s. Geslaagde softwaretests vervangen geen fysieke acceptatie van voeding, touch, beweging, radio of herstel.

## Firmware bouwen

```sh
uv run python scripts/prepare_firmware.py
uv run --locked pio run --project-dir firmware
```

De voorbereiding haalt borddefinitie, GFX-library en CST3530-driver uit een vaste [officiële LILYGO-revisie](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02). Automatisch bijwerken van de touchcontrollerfirmware is uitgeschakeld. De huidige implementatie gebruikt Arduino/ESP-IDF met een eigen native renderer; er is geen LVGL-migratie nodig om de huidige demo te gebruiken.

De logische framebuffer is 640 × 180 en wordt in software naar het fysieke 180 × 640-frame vertaald. De CST3530-touchmapping is op het huidige prototype gebruikt en getest; andere boardrevisies vereisen eigen verificatie.

De firmwareversie staat in `firmware/src/panel_version.h`; scherm, handshake en image-marker gebruiken diezelfde bron. Generated assets staan in de repository. Alleen bij ontwerpwijzigingen opnieuw genereren:

```sh
uv run --locked python scripts/generate_demo_assets.py
```

## USB-installatie en herstel

```sh
uv run panel ports
```

Identificeer het bedoelde paneel via USB-identiteit én handshake. Poortnamen kunnen na reboot of programmeermodus veranderen; vertrouw niet op één vast poortnummer. Een seriële poort openen kan het apparaat resetten.

Voor het huidige prototype is alleen de applicatie in het vooraf gecontroleerde actieve slot geschreven. Controleer vóór schrijven apparaatidentiteit, fabrieksbackup, imageprofiel en bootselectie. Gebruik niet blind een volledig upload-/erasecommando: bootloader, partities en NVS behoren niet tot een gewone applicatie-update. De private backup, pairing en installatierapporten staan buiten Git.

USB-flashing is nu de gekozen installatie-/herstelroute. Het paneel wordt eigenaar van wifi-download, installatie en lokale bootbevestiging. USB blijft beschikbaar voor installatie en herstel. Webserverintegratie voor updates valt buiten #15. Een merge of build installeert niets op het display.

## Optionele wifi en OTA

Wifi testen met de Mac kan al. Configureer eenmalig via USB:

```sh
uv run panel wifi setup --port <usb-poort> --host <ip-van-je-mac>
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

Netwerknaam en wachtwoord worden interactief gevraagd. De firmware bewaart configuratie in NVS; credentials komen niet in de firmwarebron. De bench gebruikt een eigen TLS-PSK-sleutel. NVS/flash is nog niet versleuteld. Zie [wifi-procedure en beperkingen](docs/wifi.md).

De bestaande `uv run panel wifi update` schrijft naar het inactieve applicatieslot en controleert na reboot de image en bootbevestiging. Hervatten na verbindingsverlies en rollback zijn fysiek aangetoond bij eerdere firmware. De grotere 0.4.1-overdracht bereikte echter het reconnectbudget rond 95%. De [full-image-hostfix](docs/ota-full-image.md) herstelt nu op basis van bevestigde voortgang en heeft TLS-foutinjectietests; fysieke acceptatie van de grotere image blijft open. Gebruik voorlopig USB voor installatie van de huidige demoimage. Zie [OTA-procedure](docs/ota.md) en de [actuele displayteststatus](docs/display-demo.md).

De [eerste ondertekeningslaag](docs/signed-updates.md) controleert releasehandtekeningen op host en paneel; de standaardbuild blijft unsigned bench. Zelfstandig downloaden via wifi en lokaal de boot bevestigen staan gepland in [#15](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/15). De webserver heeft hierin geen rol. Productiekeyprovisioning, secure boot, herstel bij alle stroom-/netwerkfouten en onbeheerde recovery zijn nog niet geaccepteerd. Wifi naar een echte NetLink, transportwissel en beheer zonder Mac zijn vervolgwerk.

## Vervolgwerk

De [GitHub-epics](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues?q=is%3Aissue%20is%3Aopen%20label%3Aepic) bevatten de concrete werkpakketten, acceptatiecriteria en afhankelijkheden:

1. [Directe USB-koppeling](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/2): productieprotocol, panel-service en bestaande lokale MQTT-services.
2. [Echte bediening](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/3): werkelijke status, blijvende instellingen en fysieke stop-/bedieningsacceptatie.
3. [Betrouwbare updates](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/4): grotere images, gecontroleerde ondertekende releases en herstelproeven.
4. [Optionele wifi](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/5): provisioning, pairing, transportkeuze en herstel zonder USB.
5. [Beheer op afstand](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/6): agentintegratie, geautoriseerde acties en bestaande logs/metrics.
6. [Releases en pilot](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/7): CI, installatie/montage en meerdaagse acceptatie op echte werkplekken.

Begin met het protocol en de USB-service; werk parallel aan OTA-diagnose en CI. Test daarna één echte werkplek voordat brede uitrol volgt. Boekingen, check-in en persoonlijke profielen vallen buiten deze eerste scope.

[De oorspronkelijke productplanning](docs/product-plan.md) is achtergrond bij de architectuur en bevat nog aannames uit de fase vóór het prototype. De actuele status en GitHub-issues gaan voor op die historische fasering. Integratie moet de bestaande NetLink desk/display-services en fleet-first Balena-releaseflow gebruiken. Stack-, agent- of desk-servicewijzigingen horen in hun eigen repositories; deze repository bevat firmware en hostprototype.

## Mappen

| Map | Inhoud |
| --- | --- |
| `firmware/` | ESP32-S3-firmware, native demo en updatecode |
| `host/netlink_panel/` | USB/wifi-bench, updater, protocoldecoder en simulator |
| `preview/` | Browserdemo van de eerdere ontwerpset |
| `tests/` | Python-, native renderer-, protocol- en hersteltests |
| `scripts/` | Firmwarevoorbereiding, assetgeneratie en diagnostische captures |
| `docs/` | Ontwerpen, gebruik, historische testresultaten en planning |

## Licentie

De eigen projectcode is gelicentieerd onder de [GNU General Public License versie 3](LICENSE), SPDX `GPL-3.0-only`. Bij verspreiding van afgeleide software moet de bijbehorende broncode onder dezelfde licentie beschikbaar worden gesteld; commercieel gebruik is toegestaan. Deze keuze draagt auteursrechten niet over.

Onderdelen van derden houden hun eigen licenties en auteursrechtvermeldingen. Inter blijft onder de SIL Open Font License; zie [third-party-vermeldingen](THIRD_PARTY_NOTICES.md). De licentie van de eigen code verklaart de volledige meegebouwde firmware niet automatisch vrij voor distributie. Zie de [voorbereiding van openbaarmaking](docs/open-source-readiness.md) voor de nog open punten.
