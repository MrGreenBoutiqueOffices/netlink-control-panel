# Zelfstandige ontwerp-preview op het LILYGO-display

De firmware simuleert een bureau en monitor volledig lokaal. Er is geen NetLink, MQTT, UART-bureau of DDC/CI-monitor aangesloten. De touchbediening is onafhankelijk van een USB- of wifi-beheersessie. Hoogtes en voorkeuren bestaan alleen in RAM en beginnen na herstart weer op de demowaarden.

## Versienummer op het display

Vanaf 0.5.1 toont Meer → Paneel onder HELDERHEID PANEEL de firmwareversie. De tekst gebruikt dezelfde versiebron als de beheer- en updateprotocollen en draait mee met het scherm.

0.5.2 herstelt daarnaast slepen op de helderheidsslider wanneer het paneel 180 graden gedraaid is. Deze correctie is lokaal getest; de laatste fysieke installatie is 0.5.1.

## Nieuwe ontwerpset in 0.5.0

De derde aangeleverde PDF bevat 17 schermen. 0.5.0 voegt grotere pijlen, het menu in twee rijen, normaal/180 graden draaien, het minimale rustscherm en de uitgewerkte opstart-, verbindings-, update-, fout-, obstakel- en afstelschermen toe. De doelhoogtebediening en 62–127-cm-grenzen blijven gelden.

Draaien verandert zowel de volledige framebuffer als de touchcoördinaten. Het blijft een RAM-instelling voor deze demo. Na de ingestelde inactiviteit verschijnt het rustige scherm met alleen de hoogte; de eerste aanraking wekt de eerdere pagina zonder actie uit te voeren.

Extra voorbeelden op het display: open Meer en houd het lege vak rechtsonder minimaal één seconde vast. In de statusvoorbeelden ga je verder door links minimaal één seconde vast te houden. Foutknoppen zoals Later en OK keren terug naar Bureau; Opnieuw opent het verbindingsvoorbeeld. In Afstellen verlaagt de grote vasthoudknop alleen de lokale voorbeeldhoogte, stopt op release en gaat nooit onder 62 cm. De scenariomodus laadt de voorbeeldwaarden uit het ontwerp.

Echte OTA-voortgang gebruikt het nieuwe updatebeeld met het werkelijke percentage. Een nieuwe, nog te bevestigen boot krijgt expliciet de tekst Nieuwe firmware controleren. Tijdens die echte beheeractie is de demo geblokkeerd. De andere fout-/obstakel-/afstelschermen zijn lokale ontwerpscenario's, geen NetLink-integratie.

0.5.0 is via USB geïnstalleerd op het geïdentificeerde display; esptool verifieerde de geschreven flashhash. Via USB zijn daarna versie, verwachte imagehash, VALID-status, startup-self-check en grenzen teruggelezen. Een coherente snapshot van Paneel bleef behouden terwijl de live UI naar Ruststand ging. Er zijn in die eindcontrole geen schermwissels geïnjecteerd. Bewijs: `artifacts/display-0.5.0/verification.json` en `comparison.png`.

## Bediening vanaf 0.4.3

- De ondergrens is 62 cm en de bovengrens 127 cm (620–1270 mm). Tikken, vasthouden, presets, demo-invoer en bevestigde bewegingen respecteren deze grenzen.
- Een korte tik op Hoger of Lager past alleen de doelhoogte met 1 cm aan.
- Vasthouden herhaalt die doelhoogtestap na 350 ms, vervolgens iedere 180 ms. Loslaten of buiten de pijl slepen stopt het aanpassen; het donkere bevestigingsscherm blijft staan.
- De huidige hoogte blijft tijdens het kiezen gelijk. Alleen Bevestigen start de gesimuleerde beweging. Annuleren verwerpt de keuze.
- Ook Zitten en Staan kiezen eerst een doelhoogte. Bevestigen start de simulatie naar die preset.
- Tijdens een bevestigde beweging stopt één aanraking ergens op het scherm de simulatie.
- Meer opent Monitor, Voorkeuren en Paneel. Monitor biedt demohelderheid, aan/uit en ingang; Voorkeuren bewaart de huidige demohoogte als preset; Paneel biedt helderheid, dimtijd en draaien. Sliders reageren op tikken en slepen.
- Houd Meer op het beginscherm ongeveer één seconde vast om de gesimuleerde verbinding te verbreken/herstellen. Bij die offline-status zijn bureauacties geblokkeerd; lokale paneelinstellingen blijven bruikbaar.
- Na de ingestelde dimtijd maakt de eerste aanraking het scherm wakker en voert nog geen andere actie uit.

De referentie is `docs/design/netlink-bedienpaneel.pdf` (de derde PDF; de vorige versie is bewaard in `docs/design/v2/`), met zeventien schermen op 640 × 180. De originele schermbeelden zijn compact als RGB565/RLE opgenomen; veranderlijke tekst gebruikt lokaal gegenereerde Inter-glyphs. Het oorspronkelijke font is niet beschikbaar als bruikbaar webfont in de raster-PDF; de beperkte typografische afwijking is gedocumenteerd in `design-qa.md`.

## Assets opnieuw genereren

```sh
uv run scripts/generate_demo_assets.py
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

De generator heeft gepinde optionele afhankelijkheden in zijn scriptmetadata. De gewone firmwarebuild gebruikt de ingecheckte gegenereerde bestanden en heeft die Python-pakketten niet nodig.

## Herhaalbare controles

`tests/test_panel_demo.py` compileert exact dezelfde C++-toestandsmachine en renderer als de firmware. Het test korte tik, vasthouden, release, doel versus huidige hoogte, bevestigen, annuleren, stop, offline-blokkering, voorkeuren, sliders, dimmen en framebuffergrenzen.

```sh
uv run python -m unittest discover -s tests -p test_panel_demo.py -v
```

`scripts/capture_panel_demo.py` leest de echte framebuffer uit en kan lokale demoschermen en voorbeeldinvoer kiezen. Dat verandert alleen RAM-demotoestand, nooit firmware of echte apparatuur. Start het niet tijdens een gebruikersbeoordeling: het wisselt schermen en kan botsen met echte aanrakingen.

## Vastgelegde beperkingen

0.4.0 is via wifi geïnstalleerd en bevestigd. De eerste vier schermbeelden zijn van het echte paneel uitgelezen; een volgende opname werd terecht gestopt doordat tijdens de opname een aanraking de toestand veranderde. De oude directe-move-interpretatie in 0.4.1 is vervangen door alleen-doelhoogte-bewerking in 0.4.2.

De grote 0.4.1-wifi-overdracht brak rond 95% af na het reconnectbudget. Hervatten werkt, maar wifi-OTA is met deze verbinding en grotere image nog niet voldoende betrouwbaar. USB is daarom de gekozen installatieroute. De bootselectie en fysieke ESP32-S3/MAC zijn vóór schrijven gecontroleerd; alleen het actieve applicatieslot wordt via de kabel bijgewerkt, zonder NVS/bootloader/partitievervanging.

0.4.3 is via USB geïnstalleerd en de geschreven flashhash is door esptool geverifieerd. Daarna zijn via dezelfde USB-verbinding de draaiende versie, verwachte imagehash, VALID-status en geslaagde display/touch-startup-self-check teruggelezen. De grotere USB-responsen werken nu met een TX-buffer van 4096 bytes.

Op het echte apparaat is via de gedeelde UI-handler gecontroleerd: korte tik omhoog kiest 75 cm, vasthouden koos daarna 80 cm, release hield het doel stabiel, één tik omlaag koos 79 cm, en de huidige hoogte bleef bij al die stappen 74 cm. Annuleren bracht het beginscherm terug. De firmware rapporteert min 620 en max 1270 mm. Endpointgedrag en bewegen tot de grens zijn afgedekt door de geslaagde native regressietest; er is tijdens deze eindcontrole geen automatische bewegingsdemo gestart.

Bewijs staat lokaal in `artifacts/display-0.4.3/verification.json` en de USB-installatielog. De volledige suite van 46 tests, lint en formattering zijn geslaagd voor deze release. Fysieke gebruikersbeoordeling van look-and-feel en touch blijft de volgende stap.


De atomische framebuffer-API vanaf 0.5.0 maakt bij offset nul één kopie in PSRAM en geeft iedere chunk dezelfde `snapshot_id` en `snapshot_screen`. Gelijktijdige bediening of automatisch dimmen kan die opname niet meer vermengen. De browserkopie houdt voorlopig de vorige ontwerpset; deze 17-schermenuitwerking is de native displaydemo.
