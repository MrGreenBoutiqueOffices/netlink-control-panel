# Draadloos testen met de Mac

Status 2026-11-03: wifi is geïmplementeerd vanaf benchfirmware 0.2.0; versie 0.3.0 voegt [applicatie-updates via wifi](ota.md) toe. De firmware is op het fysieke display getest; actuele OTA-resultaten staan in het [herstelrapport](ota-recovery-2026-11-03.md). USB blijft beschikbaar en heeft voorrang als een USB-testsessie actief is.

## Eenmalig via USB

De eerste installatie van onze firmware en het instellen van wifi vragen om een USB-datakabel. Daarna kan het paneel met alleen voeding draadloos testen. Eerst identificeren we het bord en bewaren we de fabrieksflash; zie de project-README voordat je de firmware overschrijft.

Bouw en laad de wifi-firmware met PlatformIO volgens de README. Open vervolgens een terminal in deze projectmap:

```sh
uv run panel ports
uv run panel wifi setup --port <usb-poort> --host <ip-van-je-mac>
```

Gebruik bij `--host` het lokale IPv4-adres van deze Mac, bijvoorbeeld `192.168.1.20`. Je vindt dat bij de netwerkdetails in macOS. Dit is het adres waarmee het paneel je Mac kan bereiken; `127.0.0.1`, `localhost` en `0.0.0.0` zijn daarvoor ongeschikt.

Het programma vraagt om de naam van het 2,4-GHz-wifinetwerk en daarna om het wachtwoord zonder zichtbare invoer. Het wachtwoord komt niet in de shellgeschiedenis of de loguitvoer en wordt niet op de Mac opgeslagen. De firmware bewaart de netwerkgegevens en de unieke verbindingssleutel in NVS, zodat het paneel na opnieuw inschakelen weer kan verbinden. NVS/flash is in deze benchfirmware niet versleuteld.

De Mac bewaart alleen de paneelidentiteit, het serveradres, de poort en een willekeurige sleutel in `.secrets/panel.json`, met bestandsrechten `0600`. Deze map staat in `.gitignore`. Deel of commit dit bestand niet. Het bestand wordt bewust vóór de configuratieoverdracht gemaakt: ook als de USB-bevestiging verloren gaat, blijft de nieuwe sleutel beschikbaar.

Bij gewijzigde wifi-instellingen of een veranderd Mac-adres kun je opnieuw instellen met een nieuw bestand:

```sh
uv run panel wifi setup --port <usb-poort> --host <ip-van-je-mac> --pairing .secrets/panel-nieuw.json
```

De firmware vervangt de oude configuratie zodra opslag is bevestigd. Een bestaand lokaal pairingbestand wordt niet stilzwijgend overschreven.

## Draadloze test starten

Zorg dat Mac en paneel elkaar op het lokale netwerk kunnen bereiken. Start:

```sh
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

Bij een ander pairingbestand:

```sh
uv run panel wifi serve --pairing .secrets/panel-nieuw.json --duration 300
```

Het programma luistert standaard alleen op het ingestelde Mac-adres en TCP-poort 8769. Indien macOS om toegang tot het lokale netwerk vraagt, is die nodig om het paneel te laten verbinden. Wifi-clientisolatie of een firewall kan lokaal verkeer blokkeren; er is geen internet- of cloudroute nodig.

Het paneel maakt een uitgaande TLS-verbinding naar de Mac. Het scherm toont de verbindingsstatus en het eigen lokale IP-adres. Zodra het Mac-programma de handshake heeft afgerond, verschijnen de demowaarden. Tikken op de knoppen geeft diagnostische events in de terminal; er worden geen bureau- of monitorcommando's verstuurd.

De server draait standaard vijf minuten; elke testsessie duurt standaard dertig seconden. Daarna mag het paneel opnieuw verbinden. Stop met Ctrl+C. Zonder heartbeat worden knoppen uitgeschakeld en vervalt de sessie na circa 3,5 seconden. Bij een gesloten TCP-verbinding kan dit eerder zijn.

Sluit geen gelijktijdige USB-bench aan als je wifi wilt testen. Alleen een actieve USB-handshake neemt de bediening over; een USB-kabel voor voeding alleen verhindert wifi niet. Een transportwissel vraagt altijd om een nieuwe handshake. Aanrakingen worden niet overgezet of opnieuw afgespeeld.

## USB behouden en wifi wissen

USB werkt ook als het wifinetwerk of de Mac onbereikbaar is:

```sh
uv run panel bench --port <usb-poort> --duration 30
uv run panel wifi forget --port <usb-poort>
```

`forget` wist de opgeslagen wifi- en TLS-sleutel op het paneel en zet wifi uit. Het lokale pairingbestand blijft bewaard; dat kun je zelf verwijderen zodra je het niet meer nodig hebt.

## Beveiliging en grenzen

- Beide kanten gebruiken een unieke willekeurige 256-bits sleutel voor TLS 1.2 PSK-authenticatie en AES-128-GCM-versleuteling. Er is geen anonieme/plaintext-modus of `setInsecure()`-route op het paneel. De PSK-suite heeft geen forward secrecy; dit is een lokale benchoplossing.
- Configuratie en wissen zijn alleen via USB toegestaan, niet via wifi. De server controleert ook de paneelidentiteit in het applicatieprotocol.
- Het Mac-programma heeft voor wifi Python 3.13+ met OpenSSL-PSK-ondersteuning nodig. De vastgelegde Python 3.14-omgeving op deze Mac ondersteunt dat. USB blijft werken op Python 3.11+.
- Instellen gebeurt niet via een open configuratie-accesspoint. Er worden geen productiecredentials uit Signing, Home Assistant of NetLink hergebruikt.
- Dit is de draadloze verbinding naar het Mac-testprogramma. [Draadloze applicatie-updates](ota.md) zijn geïmplementeerd vanaf 0.3.0. Een beheerde NetLink-service, automatische configuratierollback en volledige recovery zijn nog niet geïmplementeerd.
- TLS-handshakes, verkeerd ingestelde sleutels en het gedeelde protocol worden lokaal getest; radiobereik, wifiherstel, stroomuitval, touch en USB/wifi-voorrang op het echte paneel blijven fysieke acceptatietests.

Bronnen: [ESP32 Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html), [ESP32 Preferences/NVS](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/preferences.html), [WiFiClientSecure 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/WiFiClientSecure.h), [Python TLS-PSK callbacks](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.set_psk_server_callback).
