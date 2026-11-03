# NetLink Panel

Een zelfstandig werkprototype voor de LILYGO T-Display S3 Long. USB is de standaardverbinding; wifi is meteen beschikbaar voor draadloos testen met de Mac.

Dit project bevat een schermdemo, een USB/wifi-benchprogramma voor macOS/Linux, een pseudo-terminalsimulator en testfirmware. Het verstuurt **geen echte bureau- of monitorcommando's**. Wifi en applicatie-updates gebruiken dezelfde versleutelde, met een eigen sleutel geauthenticeerde verbinding. MQTT-integratie en een productiebeheerlaag zijn nog niet geïmplementeerd. Rollback en wifi-updates met automatisch hervatten na verbindingsverlies zijn fysiek getest; zie de teststatus hieronder.

## Actuele hardwareteststatus

Firmware **0.3.3** draait bevestigd geldig op het paneel. Een volledige wifi-update met echte verbindingsuitval, automatisch hervatten, herstart en bootbevestiging is geslaagd. Twee gerichte fysieke onderbrekingsproeven en 45 lokale regressietests ondersteunen dit. Een eerdere volledige proef vereiste nog herstel van de bootbevestiging; de gevonden rebootrace is daarna in de hosttool opgelost. Zie [het OTA-herstelrapport](docs/ota-recovery-2026-11-03.md) voor bewijs en grenzen. Stroomuitval tijdens schrijven/activeren en meerdaagse stabiliteit zijn nog niet getest.

## Firmware-updates zonder USB

Installeer de updater in firmware 0.3.0 één keer via USB. Daarna kun je nieuwe builds draadloos sturen:

```sh
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
uv run panel wifi update
```

Stop eerst een draaiende `panel wifi serve`. De updater wacht op het gekoppelde paneel, schrijft naar het andere applicatieslot en meldt pas succes na een geverifieerde reboot en bootbevestiging. Zie [docs/ota.md](docs/ota.md) voor de volledige procedure, beperkingen en herstelgedrag.

## Meteen via wifi testen

Na de eerste firmware-installatie stel je wifi eenmalig via USB in. Daarna heeft het paneel alleen voeding nodig:

```sh
uv run panel wifi setup --port <usb-poort> --host <ip-van-je-mac>
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

Wifi-naam en wachtwoord worden interactief gevraagd. Lees [docs/wifi.md](docs/wifi.md) voor de volledige stappen, pairing, USB-voorrang en het wissen van instellingen. Er worden geen credentials in de firmwarebron gezet.

## Beginnen zonder display

Open `preview/index.html` in een browser voor de interactieve schermdemo. De afmetingen van het paneel zijn 640 × 180 pixels. Verbreek de demoverbinding om de uitgeschakelde knoppen te bekijken. De preview staat los van USB en de simulator.

Installeer [uv](https://docs.astral.sh/uv/getting-started/installation/) als het nog niet beschikbaar is. Voer vanuit deze projectmap uit:

```sh
uv run panel bench --simulate
uv run python -m unittest discover -s tests -v
```

De simulator gebruikt een echt pseudo-terminalpaar, zodat ook de seriële hostcode wordt getest. Een geslaagde proef vereist een geldige identiteit/handshake, een bevestiging van de demostatus en ten minste één heartbeat. De uitvoer vermeldt expliciet `simulated: true` en `hardware_command_sent: false`.

## USB-apparaat bekijken

```sh
uv run panel ports
```

Dit toont beschikbare seriële apparaten zonder ze te openen. De fabrieksfirmware spreekt ons protocol nog niet: `bench` zal daarop geen geslaagde proef rapporteren. Eerst moeten we het bord identificeren, de fabrieksflash veiligstellen en display/touch-revisie controleren.

De LILYGO kan via USB-programmeermodus tijdelijk onder een andere poortnaam verschijnen. Kies altijd expliciet het bedoelde apparaat. Een seriële poort openen kan het bord resetten; het benchprogramma schrijft geen flash.

## Firmware bouwen

De benchfirmware gebruikt tijdelijk de Arduino/ESP-IDF-basis en GFX-driver van de fabrikant. Dat houdt de eerste hardwareproef dicht bij de referentievoorbeelden. Applicatie-updates en bootbevestiging/rollback zijn geïmplementeerd met ESP-IDF. LVGL en onafhankelijke releasehandtekeningen blijven vervolgwerk; dit is geen vervanging van de volledige productarchitectuur.

```sh
uv run python scripts/prepare_firmware.py
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

De voorbereidingsstap haalt alleen de benodigde borddefinitie, GFX-library en CST3530-touchdriver uit een vaste [officiële LILYGO-revisie](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02). Bronnen en licentievermeldingen blijven in de genegeerde map `firmware/.vendor/`. De enige lokale driverwijziging schakelt automatisch bijwerken van de **touchcontrollerfirmware** uit. Afhankelijkheden worden bij de eerste build lokaal gedownload.

De schermcontroller krijgt een volledig 180 × 640-frame, met softwarematige rotatie naar een horizontale bediening. Er wordt niet op hardwarematige rotatie vertrouwd. De CST3530-pinconfiguratie is een kandidaat op basis van de referentiebranch en moet op het aangekochte bord worden gecontroleerd.

Er wordt niets automatisch geflasht. Na identificatie en een backup kan de testfirmware handmatig worden geladen met de expliciete apparaatpoort:

```sh
uv tool run --from platformio==6.1.18 pio run --project-dir firmware --target upload --upload-port <poort>
uv run panel bench --port <poort> --duration 30 --height 740 --brightness 60
```

De firmware toont steeds dat de waarden demo zijn. `--brightness` verandert alleen de getoonde monitorwaarde; het regelt geen echte monitor of schermbacklight. Tikken op ZITTEN, STAAN en MONITOR levert diagnostische touch-events op. Na circa 3,5 seconden zonder host-heartbeat toont het scherm verbindingsverlies.

De partitie-indeling bevat twee applicatieslots. Firmware 0.3.0 voegt de app-updater en expliciete bootbevestiging toe. De build gebruikt een rollback-enabled bootloader en een uitgestelde Arduino-verificatiehook. Secure boot, onafhankelijke releasehandtekeningen en gegarandeerde recovery bij alle foutsoorten ontbreken. Eerste flash en wijzigingen aan bootloader/partities vragen om fysieke toegang en een gecontroleerde herstelprocedure.

## Mappen

| Map | Inhoud |
| --- | --- |
| `firmware/` | ESP32-S3 testfirmware, vaste buildconfiguratie en partities |
| `host/netlink_panel/` | USB-bench, begrensde protocoldecoder en simulator |
| `preview/` | Zelfstandige interactieve schermdemo |
| `tests/` | Framing-, foutafhandeling- en seriële integratietests |
| `docs/` | Protocol, status en eerstvolgende hardwareproeven |

## Vervolg

1. USB-identiteit, bordrevisie en fabrieksfirmware vastleggen; volledige flashbackup controleren voordat we overschrijven.
2. Testfirmware laden en schermoriëntatie, touchcoördinaten, USB-serial en hotplug fysiek testen.
3. De geïmplementeerde wifi-update en bootbevestiging fysiek aantonen, ook bij verbindingsverlies of stroomuitval.
4. Daarna pas capability-gebaseerde koppeling met bestaande NetLink MQTT-aansturing bouwen en stopgedrag op echte hardware testen.
5. Wifi gebruikt hetzelfde applicatieprotocol; test radioverbinding, transportwissel en herstel ook op het fysieke paneel. De app-updater gebruikt wifi; USB blijft de herstel- en installatieroute.

Een kopie van de volledige productplanning staat in [docs/product-plan.md](docs/product-plan.md); de oorspronkelijke planning staat in `netlink_balena/docs/planning/hardware/usb-control-panel.md`. Dit project wijzigt de NetLink-stack of bestaande submodulepointers niet.
