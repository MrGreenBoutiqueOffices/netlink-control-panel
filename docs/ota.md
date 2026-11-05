# Firmware bijwerken via wifi — huidige host-benchroute

Dit document beschrijft de bestaande hostgestuurde benchroute. Het [besluit voor #15](signed-updates.md#besluit-het-paneel-beheert-zijn-updates) is zelfstandig downloaden en installeren vanaf het paneel, met lokale bootbevestiging. De webserver valt buiten die updatescope. Dat werkt nog niet in de huidige firmware: onderstaande procedure vereist een gekoppelde host, inclusief `ota_confirm` na reboot.

Zie [de full-image-diagnose van issue #14](ota-full-image.md) voor de voortgangsafhankelijke hostfix en de nog open fysieke matrix.

Vanaf firmware 0.3.2 kan een lopende overdracht na tijdelijk verbindingsverlies worden hervat. Gebruik de bijbehorende actuele hosttool. Zie [de herstelcontrole](ota-recovery-2026-11-03.md) voor de daadwerkelijk uitgevoerde fysieke proeven en de resterende grenzen.

## Eén keer installeren, daarna draadloos

Firmware 0.1/0.2 en de fabrieksfirmware bevatten deze updater nog niet. Installeer daarom **één keer versie 0.3.0 via USB**, inclusief de bijbehorende bootloader en partitie-indeling. Bewaar eerst de fabrieksflash en controleer de bordrevisie volgens de README. Dit is geen actie die de hosttool automatisch uitvoert.

Stel daarna wifi in met `panel wifi setup` zoals beschreven in [wifi.md](wifi.md). Een al ingestelde 0.2-wificonfiguratie gebruikt hetzelfde NVS-formaat; een normale flash die NVS bewaart kan die blijven gebruiken. Na een volledige flash-erase moet je opnieuw instellen.

Voor volgende versies, vanuit de projectmap:

```sh
uv run --locked pio run --project-dir firmware
uv run panel wifi update
```

De updater kiest standaard `firmware/.pio/build/panel-bench/firmware.bin` en `.secrets/panel.json`. Voor een ander bestand of pairing:

```sh
uv run panel wifi update --firmware <firmware.bin> --pairing .secrets/panel-nieuw.json
```

Stop eerst een eventueel draaiende `panel wifi serve`: beide programma's gebruiken hetzelfde lokale adres en poort 8769. Het paneel heeft alleen voeding en bereik tot de Mac nodig. Er komt geen extra updatepoort of openbaar accesspoint bij.

## Wat gebeurt er?

1. De Mac controleert de ESP32-S3-chipidentiteit, applicatiedescriptor, segmentlengtes, checksum, SHA-256 en de ingebouwde NetLink-bord/protocol/partitie-identiteit. Een bootloader, samengevoegde flashdump, beschadigde image of verkeerd bord wordt geweigerd voordat de netwerkserver start.
2. Alleen het gekoppelde paneel kan via de bestaande wederzijds geauthenticeerde TLS-PSK-verbinding verbinden. De Mac controleert ook paneelidentiteit, updateondersteuning en startup-self-check.
3. Het paneel registreert de draaiende image als bekende geldige terugvalversie als de initiële USB-flash nog geen OTA-selectie had. Het schrijft daarna uitsluitend naar het andere applicatieslot. NVS, bootloader, partities en wifigegevens worden niet bijgewerkt.
4. Elk blok van maximaal 512 bytes moet op de verwachte positie worden bevestigd. Vanaf capability `ota_resume_v1` bewaart het paneel bij wifi/TLS-verlies de flashhandle, schrijfpositie en lopende hash maximaal 60 seconden zonder transferactiviteit. De host staat maximaal vijf herstelpogingen zonder nieuwe bevestigde bytes toe. Alleen een hoger bevestigd offset geeft opnieuw herstelruimte; gelijke of teruggezette offsets doen dat niet. Het totale aantal herverbindingen mag daardoor hoger dan vijf zijn, binnen dezelfde vaste deadline (standaard 600 seconden). Herhaald verloren activatieverzoeken vallen onder hetzelfde begrensde budget. Een herhaald `ota_begin` voor exact dezelfde grootte, beide hashes, profiel en versie retourneert de werkelijk geschreven positie, zonder opnieuw te wissen. De host valideert die positie en verstuurt alleen het resterende deel. Bij een verlopen lease of paneelherstart begint de image opnieuw vanaf nul; de huidige geldige boot blijft geselecteerd. Een andere actieve image wordt geweigerd. USB-overname en expliciet afbreken ruimen de transfer direct op.
5. Pas na controle van de totale lengte, SHA-256, ingebouwde image-identiteit en ESP-imagevalidatie wordt de bootselectie gewijzigd en herstart het paneel.
6. De nieuwe firmware is eerst onbevestigd. Het paneel moet opnieuw via TLS verbinden, de verwachte imagehash en versie melden en de startup-self-check doorstaan. De Mac vraagt dan om expliciete bootbevestiging en leest de bevestigde status nogmaals uit.

De startup-self-check controleert buffer/display-initialisatie en een uitgelezen touchcontrolleridentiteit. Dit bewijst geen juiste pixels, schermoriëntatie of touchcoördinaten; die blijven fysieke tests.

Het ontvangstbewijs bewaart fase, verstreken tijd, hoogste bevestigde positie en huidige positie, netto voortgang per seconde, totaal aantal recoveries, de stilstandsbudgetstand en maximaal 32 geschoonde sessiemetingen (firmware, uptime/resetreden, RSSI/wifi-disconnectreden indien aanwezig, TLS- en hello-duur). Overgeslagen oudere sessiemetingen worden geteld. Credentials, netwerknaam, IP en protocolframes worden niet gekopieerd.

Alleen `ota_confirmed` en exitcode 0 betekenen dat de host de verwachte image en bevestigde boot heeft gezien. Het resultaat staat ook in `artifacts/last-update.json`. Tijdens uploaden zijn de touchknoppen geblokkeerd. Dit prototype bestuurt nog geen echt bureau of monitor.

## Bij een onderbreking

- **Tijdens uploaden:** het huidige slot blijft geselecteerd. De host hervat alleen na een nieuwe geauthenticeerde handshake en een manifest dat exact overeenkomt. Bij een verloren blokbevestiging vraagt hij de actuele positie op in plaats van dat blok blind opnieuw te schrijven. Legacy-firmware zonder `ota_resume_v1` krijgt geen automatische uploadretry.
- **Na activatie maar zonder bevestiging:** de nieuwe firmware wacht maximaal circa 90 seconden en herstart dan. Met de meegeleverde rollback-enabled bootloader wordt een onbevestigde image bij reset verworpen en de bekende vorige versie gekozen. Deze automatische terugval is op het concrete bord gemeten; stroomuitval tijdens activatie is nog niet beproefd.
- **Na een verloren `ota_finish`-bevestiging:** de host controleert de werkelijk draaiende hash op de volgende verbinding. Als de oude image nog draait en expliciet een behouden transfer meldt, kan dezelfde complete transfer alsnog worden afgerond. Een oude image zonder behouden transfer wordt niet opnieuw geïnstalleerd: dat kan een rollback zijn. Alleen een verloren antwoord bewijst geen succes of mislukking. Een verloren bootbevestiging wordt door dezelfde hash opnieuw te controleren en idempotent te bevestigen opgelost.
- **Als de host stopt vóór bootbevestiging:** het resultaat is onbevestigd. Laat hem tijdig opnieuw met dezelfde image verbinden met `panel wifi update`; dezelfde gewenste image kan alsnog worden gecontroleerd en bevestigd. Zonder bevestiging kan de bootdeadline tot rollback leiden.
- **Andere image na reboot:** de tool meldt geen succes; er kan rollback hebben plaatsgevonden. Er volgt geen automatische herinstallatie.
- **Hetzelfde bestand draait al:** de tool controleert en bevestigt de bestaande boot zonder dezelfde image opnieuw naar flash te sturen. Een gewijzigde build met hetzelfde versienummer wordt via de imagehash onderscheiden.
- **App die de scheduler/USB uitschakelt of onbruikbare netwerkconfiguratie schrijft:** de prototype-updater garandeert geen herstel bij elke software- of hardwarefout. Bewaar USB als herstelroute; remote recovery blijft een fysieke acceptatie-eis.

Een bevestigde maar functioneel ongewenste versie kan worden vervangen door opnieuw een compatibele oudere 0.3+-applicatie-image te uploaden. Er is geen generieke rollbackknop die willekeurig naar het andere slot schakelt: dat slot kan een afgebroken upload bevatten.

## Ontwikkelen aan het scherm

Behoud de OTA-hooks bij wijzigingen aan de schermcode. `firmware/src/panel_ota.h` bevat `PANEL_FIRMWARE_VERSION` en de vaste profielidentiteit. Je mag herhaaldelijk builds met hetzelfde versienummer testen; de updater vergelijkt de cryptografische imagehash. Een ander hardwarebord, andere applicatieprotocolversie of partitie-indeling vereist een bewuste profielwijziging en valt buiten deze app-updater.

## Beveiliging en fysieke acceptatie

Autorisatie loopt via de unieke pairingkey en TLS. SHA-256 en ESP-imagevalidatie beschermen de overdracht en bewaken de image-identiteit. Dit is **geen onafhankelijke releasehandtekening, secure boot of anti-rollbackbeveiliging**; iemand met de pairingkey kan een compatibele eigen firmware aanbieden. `.secrets/panel.json` blijft daarom een beheercredential.

Lokaal getest: de echte hostcode over TLS met een gesimuleerde paneelreboot, verloren begin-/blok-/finish-/bootbevestigingen, foutieve image na reboot, imageformaat/corruptie, strikte hervatposities en bootbevestiging. De daadwerkelijke firmware-OTA-handler wordt daarnaast gecompileerd tegen fake SDK-flashcalls om dezelfde-manifest-hervatting, behoud van de handle, geen dubbele writes, manifestweigering en leaseverloop te toetsen. De firmware gebruikt ESP-IDF OTA-operaties en de exacte native transferguard wordt ook op de Mac gecompileerd en getest. Dit is geen emulatie van ESP-flash of een fysieke rollbacktest.

De actuele fysieke resultaten staan in [het herstelrapport](ota-recovery-2026-11-03.md); oudere proeven en de bewezen onbevestigde-bootrollback staan in [het eerdere robuustheidsrapport](robustness-2026-11-03.md). Nog open: elektrische stroomuitval tijdens schrijven/activeren, echte USB-overname tijdens een transfer, accesspointuitval en meerdaagse stabiliteit. Een wifi/TLS-resume overleeft geen paneelreset; dan wordt veilig opnieuw vanaf nul begonnen. Markeer een Balena-rollout of lokale simulator nooit als fysieke acceptatie.

Bronnen: [ESP-IDF 4.4.6 OTA en rollback](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html), [ESP-IDF OTA-operaties](https://github.com/espressif/esp-idf/blob/v4.4.6/components/app_update/esp_ota_ops.c), [Arduino startup/rollback-hooks](https://github.com/espressif/arduino-esp32/blob/2.0.14/cores/esp32/esp32-hal-misc.c).


## Herhaalbare fysieke herstelcontrole

Gebruik alleen met expliciete toestemming voor twee gedeeltelijke fysieke firmwarewrites, en terwijl de opgegeven image al op het paneel draait:

```sh
uv run python scripts/hardware_ota_recovery.py --firmware firmware/.pio/build/panel-bench/firmware.bin --write-inactive-slot
```

Dit test vijf seconden serveruitval en een ongelezen blokbevestiging. Het schrijft naar het andere slot, controleert hervatten en breekt daarna expliciet af; het activeert geen image. Stop andere servers/updaters vooraf. Het resultaat staat in `artifacts/ota-recovery-faults.json`.
