# NetLink Panel

Een werkprototype voor de LILYGO T-Display S3 Long: een compact bedienpaneel voor bureau en monitor. De directe USB-koppeling met een NetLink wordt de standaard; wifi blijft optioneel. Beheer en updates op afstand zijn onderdeel van het vervolgwerk.

## Actuele stand — 4 november 2026

Firmware **0.5.2 is via USB geïnstalleerd op het prototype**. De geschreven flashhash is geverifieerd; daarna zijn de draaiende versie, verwachte imagehash, VALID-bootstatus en geslaagde startup-self-check via USB teruggelezen. De fabrieksbackup is bewaard. Dit is bewijs voor installatie en boot, geen volledige fysieke gebruikersacceptatie.

| Onderdeel | Stand |
| --- | --- |
| Native displaydemo | 17 aangeleverde ontwerpen, volledig lokale simulatie zonder NetLink |
| Hoogtebediening | Tik kiest 1 cm; hold herhaalt; release houdt de doelhoogte vast; pas Bevestigen start de simulatie; grenzen 62–127 cm |
| Paneel | Helderheid, dimtijd, 180°-rotatie en versienummer onder Meer → Paneel; instellingen zijn nog tijdelijk in RAM |
| Firmware 0.5.2 | Herstelt slepen op de helderheidsslider bij 180°-rotatie; regressietest geslaagd |
| USB/wifi-bench | Mac/Linux-hostprogramma, begrensd JSON-protocol, simulator en geauthenticeerde versleutelde wifi-verbinding |
| OTA | Dual-slot, hervatten en bootbevestiging/rollback geïmplementeerd; grotere firmwareoverdracht nog onvoldoende betrouwbaar; USB is de huidige installatieroute |
| Echte bediening | Nog geen NetLink panel-service, MQTT-koppeling of echte bureau-/monitorcommando’s |
| Beheer en releases | Nog geen productiebeheerlaag of CI; lokale suite van 46 tests, lint, syntaxcontrole en firmwarebuild zijn geslaagd voor de gemergde code |

De lokale demo blijft bedienbaar zonder beheersessie. Monitorfuncties, voorkeuren, fouten en afstellen zijn voorbeeldgedrag, geen aansturing of detectie van echte apparatuur. De ingestelde paneelhelderheid schaalt de gerenderde pixels; fysieke backlightregeling is nog niet aangetoond.

Zie [bediening en installatiegeschiedenis](docs/display-demo.md), [visuele QA](design-qa.md) en [de ontwerpen](docs/design/netlink-bedienpaneel.pdf). Eerdere bench- en OTA-rapporten bevatten historische resultaten; de tabel hierboven geeft de actuele projectstatus.

## Demo proberen

Op het display: Meer opent Monitor, Voorkeuren en Paneel. Pijlen en presets kiezen alleen een doelhoogte. Annuleren verwerpt de keuze; Bevestigen start een lokale beweging. Een aanraking tijdens die beweging stopt de simulatie. De eerste aanraking na ruststand wekt alleen het scherm.

Extra ontwerpscenario’s: houd in Meer het lege vak rechtsonder minimaal één seconde vast. Houd in de statusvoorbeelden links vast om verder te bladeren. Er is geen automatische schermcarrousel.

Zonder display: open `preview/index.html`. De browserpreview bevat de eerdere acht schermen en staat los van USB, firmware en echte apparatuur. De native displaydemo is de primaire implementatie van de nieuwste 17 schermen.

## Ontwikkelen en controleren

Installeer [uv](https://docs.astral.sh/uv/getting-started/installation/) en voer vanuit de projectmap uit:

```sh
uv sync
uv run panel bench --simulate
uv run python -m unittest discover -s tests -v
uv tool run --from ruff ruff check .
uv tool run --from ruff ruff format --check .
node --check preview/app.js
```

De tests omvatten framing, sessies, TLS, updateherstel en de echte native C++-toestandsmachine/renderer. De simulator gebruikt een pseudo-terminalpaar en verstuurt geen hardwarecommando’s. Geslaagde softwaretests vervangen geen fysieke acceptatie van voeding, touch, beweging, radio of herstel.

## Firmware bouwen

```sh
uv run python scripts/prepare_firmware.py
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

De voorbereiding haalt borddefinitie, GFX-library en CST3530-driver uit een vaste [officiële LILYGO-revisie](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02). Automatisch bijwerken van de touchcontrollerfirmware is uitgeschakeld. De huidige implementatie gebruikt Arduino/ESP-IDF met een eigen native renderer; er is geen LVGL-migratie nodig om de huidige demo te gebruiken.

De logische framebuffer is 640 × 180 en wordt in software naar het fysieke 180 × 640-frame vertaald. De CST3530-touchmapping is op het huidige prototype gebruikt en getest; andere boardrevisies vereisen eigen verificatie.

De firmwareversie staat in `firmware/src/panel_version.h`; scherm, handshake en image-marker gebruiken diezelfde bron. Generated assets staan in de repository. Alleen bij ontwerpwijzigingen opnieuw genereren:

```sh
uv run scripts/generate_demo_assets.py
```

## USB-installatie en herstel

```sh
uv run panel ports
```

Identificeer het bedoelde paneel via USB-identiteit én handshake. Poortnamen kunnen na reboot of programmeermodus veranderen; vertrouw niet op één vast poortnummer. Een seriële poort openen kan het apparaat resetten.

Voor het huidige prototype is alleen de applicatie in het vooraf gecontroleerde actieve slot geschreven. Controleer vóór schrijven apparaatidentiteit, fabrieksbackup, imageprofiel en bootselectie. Gebruik niet blind een volledig upload-/erasecommando: bootloader, partities en NVS behoren niet tot een gewone applicatie-update. De private backup, pairing en installatierapporten staan buiten Git.

USB-flashing is nu de gekozen installatie-/herstelroute. Een beheerde USB-app-update via de toekomstige NetLink panel-service moet nog worden gebouwd. Een merge of build installeert niets op het display.

## Optionele wifi en OTA

Wifi testen met de Mac kan al. Configureer eenmalig via USB:

```sh
uv run panel wifi setup --port <usb-poort> --host <ip-van-je-mac>
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

Netwerknaam en wachtwoord worden interactief gevraagd. De firmware bewaart configuratie in NVS; credentials komen niet in de firmwarebron. De bench gebruikt een eigen TLS-PSK-sleutel. NVS/flash is nog niet versleuteld. Zie [wifi-procedure en beperkingen](docs/wifi.md).

De bestaande `uv run panel wifi update` schrijft naar het inactieve applicatieslot en controleert na reboot de image en bootbevestiging. Hervatten na verbindingsverlies en rollback zijn fysiek aangetoond bij eerdere firmware. De grotere 0.4.1-overdracht bereikte echter het reconnectbudget rond 95%; dat eerdere bewijs is dus geen algemene OTA-acceptatie. Gebruik voorlopig USB voor installatie van de huidige demoimage. Zie [OTA-procedure](docs/ota.md) en de [actuele displayteststatus](docs/display-demo.md).

Onafhankelijke releasehandtekeningen, secure boot, herstel bij alle stroom-/netwerkfouten en onbeheerde recovery zijn nog niet geaccepteerd. Wifi naar een echte NetLink, transportwissel en beheer zonder Mac zijn vervolgwerk.

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
