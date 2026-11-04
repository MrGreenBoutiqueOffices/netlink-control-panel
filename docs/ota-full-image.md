# Grote OTA-image: diagnose en voortgangsafhankelijk herstel

Onderdeel van #14. Dit verandert de bestaande bench-updater, geen deploymentarchitectuur. De NetLink-webserverintegratie, geautoriseerde managed updater en signing blijven #15. USB blijft de installatieroute totdat de fysieke full-image-matrix is geaccepteerd.

## Vastgestelde hostfout

Het bewaarde 0.4.1-rapport toont een image van 1.515.984 bytes en hervatten op offsets 420864, 729600, 1139200 en 1448960. De updater verbruikte desondanks zijn levenslange budget van vijf recoveries en stopte rond 95%. Het rapport bewaart de volledige imagehash en de expliciete eindfout `OTA reconnect budget exhausted`.

Een nieuwe test tegen de echte Python-updater over TLS-PSK reproduceerde dezelfde categorie: zes onderbrekingen, telkens ná een geschreven blok waarvan de ACK verloren gaat. Vóór de fix stopte de host na vijf recoveries met `ConnectionError`, terwijl de peer nog aantoonbaar verder kon hervatten. Eén commandoregel reproduceert deze regressie:

```sh
uv run --locked python -m unittest discover -s tests -p test_ota_network.py -k repeated_progressing -v
```

De fix maakt herstelruimte afhankelijk van een strikt hogere, gevalideerde schrijfpositie. Alleen die nieuwe voortgang zet de stilstandsteller terug. Gelijke posities, teruggezette posities na een paneelreset en alleen succesvolle handshakes leveren geen extra budget. Het totale aantal recoveries wordt apart bewaard. Vijf herstelpogingen zonder voortgang blijven toegestaan; daarna stopt de host expliciet. Dat geldt ook voor herhaald verloren `ota_finish`-verzoeken: geen eindeloos opnieuw activeren. Een mogelijke activatie blijft bij onvoldoende bewijs `unconfirmed`.

De globale deadline blijft dezelfde, standaard 600 seconden en maximaal 3600. Herstel verlengt haar niet. Het TLS-handshakebudget is begrensd door de resterende globale tijd. Firmwareleases, gewone bedieningstimeout, blokgrootte en het wireprotocol wijzigen niet. De bestaande 0.3.2+-firmware met `ota_resume_v1` kan deze hostfix al gebruiken. Legacy-firmware zonder capability krijgt geen blinde uploadretry.

De host valideert nog steeds offsets en hetzelfde manifest. Een inhoudelijk afgewezen manifest veroorzaakt geen automatische abort van een andere image. Succes vereist de verwachte nieuwe image, versie, startup-self-check en teruggelezen VALID-status; een socket-write of 100%-voortgang is onvoldoende.

## Metingen en oorzaakafbakening

Per geldige hello wordt uitsluitend een begrensde selectie bewaard: firmware-identificatie, uptime/resetreden en numerieke wifi-RSSI/disconnectreden indien aanwezig. Hostmetingen voegen TLS-duur, hello-duur en verstreken tijd toe. Het receipt bevat fase, `confirmed_bytes` (hoogste bevestigde positie), `current_bytes` (laatst gemelde positie van de huidige transfer), netto voortgang per seconde, totale recoveries en `failures_without_progress`. De netto snelheid gebruikt de hoogste positie gedeeld door de totale tijd, inclusief wachten/herstel; dit is geen kale radiosnelheid.

Maximaal 32 recente sessiemetingen worden bewaard, plus het aantal weggelaten metingen. Bij transportfouten wordt alleen fase en lokale exceptionklasse vastgelegd. TLS-afwijzingen worden geteld; alleen de eerste vijf krijgen een consolemelding. Geen vrije exceptionteksten, credentials, SSID, IP of volledige frames. De doelimagehash blijft in het bestaande manifest zichtbaar.

De fysieke diagnose uit [het eerdere rapport](ota-recovery-2026-11-03.md) mat wifi-verlies vóór de TLS-reset, zonder verstreken control/OTA-timeout. Waarom de associatie werd verbroken is nog niet bewezen. De hier aangetoonde hostbug verklaart waarom een grotere image na meerdere herstelbare storingen definitief faalde; hij bewijst geen oplossing van het radio-/AP-probleem zelf. De nieuwe diagnostiek moet die fysieke afbakening mogelijk maken.

## Softwarematrix

De tests bouwen een echte TLS-PSK-verbinding naar de updater. De paneelpeer simuleert applicatieflash/boot en is geen ESP-flash- of wifi-emulator. Vergelijking van alle ontvangen bytes, hashes en de bevestigde boot detecteert verkeerde offsets of dubbele data.

| Profiel | Verwachte uitkomst |
| --- | --- |
| Volledige gebouwde firmware, stabiel TLS | Alle bytes en bevestigde boot binnen 60 seconden |
| Dezelfde volledige image, 1 ms vertraging per blok, zes verloren ACK’s rond 27/48/75/95/96/99% | Hervatten op de werkelijk geschreven posities, volledige bytes en bevestigde boot binnen 60 seconden |
| Zes disconnects vóór een beginbevestiging, geen voortgang | Stop na maximaal vijf recoveries; geen activatie |
| Herhaald verloren finish-verzoeken, behouden complete transfer | Begrensd stoppen als unconfirmed; geen fictief succes |
| Doorgaande maar te trage overdracht, vaste totale deadline 10 seconden | Deadline stopt de overdracht ondanks voortgang; geen activatie |
| Verloren begin/chunk/finish/confirm-ACK en rebootrace | Een geverifieerde uitkomst of expliciete fout; geen blinde herschrijving |
| Andere actieve manifestimage | Weigering; de host verstuurt geen abort voor die andere image |

Het korte budget van 10 seconden uit de bestaande kleine TLS-fixtures was te klein voor de bewust vertraagde grote image op de ontwikkelmachine. De full-image-test gebruikt daarom 60 seconden; de productie-default is niet verhoogd. Een aparte deadline-test bewijst juist de eindgrens onder aanhoudende voortgang. De test-RSSI van -85 dBm is een synthetisch diagnostiekveld, geen RF-meting of bewijs van een zwakke fysieke verbinding.

```sh
uv sync --locked
uv run --locked python scripts/prepare_firmware.py
uv run --locked pio run --project-dir firmware
uv run --locked python scripts/check_tests.py
```

## Nog uit te voeren fysieke matrix

De softwaretests openen geen fysiek paneel. Start fysieke writes/herstarts alleen als bewust gekozen proef. Gebruik daarvoor een bewust gekozen kandidaat, bekende imagehash, actieve-slot/backupcontrole en één updater-eigenaar. Verander geen wifi-/AP-instellingen als onderdeel van een uploadtest.

| Conditie | Minimale acceptatie |
| --- | --- |
| Goed gemeten bereik | Twee volledige uploads met bekende hashes binnen 600 seconden, juiste nieuwe boot en VALID teruggelezen |
| Zwak gemeten bereik | Dezelfde matrix met vastgelegde RSSI en disconnect-/resetredenen; binnen deadline bevestigen of expliciet veilig falen, geen claim bij ontbrekend bewijs |
| Eén onderbroken verbinding en één verloren chunk-ACK | Hervatten zonder dubbele bytes; vorige geldige image blijft beschikbaar tot correcte activatie |
| Herstel-/deadlinebudget uitgeput | Geen succesmelding; daadwerkelijke draaiende image en transferstatus afzonderlijk teruglezen |

Bewaar per proef het geschoonde receipt, kandidaat-/huidige versie en hashes, duur, RSSI, recoveries en bootuitkomst. Een softwarematrix, gepubliceerde release of groen CI sluit #14 niet: fysieke full-image-/radiotests blijven vereist. Stroomuitval, alle defecte candidates en meerdaagse recovery blijven daarnaast #16/#19.
