# USB panel-service

De service in deze repository vervangt voor discovery, enrollment en statusbewaking het Mac-benchprogramma. Hij draait op Linux zonder wifi of internet en bewaakt één expliciet gekoppeld paneel. Hij publiceert alleen lokale geschoonde status; MQTT-actuatie, agentintegratie, firmwaretransfer en een HTTP-beheerinterface zijn nog niet aanwezig.

Voorwaarde is firmware 0.6.0 met [protocol v2](production-protocol.md). Een paneel met de eerder geïnstalleerde 0.5.2 krijgt geen geslaagde productiehandshake. De firmware is inmiddels afzonderlijk via USB op het prototype geïnstalleerd en met de service getest; de procedure hieronder installeert niets automatisch. De bestaande v1-tools blijven bruikbaar wanneer er geen actieve v2-sessie is.

## Lokaal starten

```sh
uv sync --locked
uv run panel ports
uv run panel-service --enrollment .secrets/service-enrollment.json enroll \
  --port <huidige-usb-poort> \
  --panel-id <bewust-gecontroleerde-paneelidentiteit> \
  --usb-serial <seriecode-uit-usb-inventaris> \
  --board-revision unverified
uv run panel-service --enrollment .secrets/service-enrollment.json run --status .secrets/service-status.json
```

Gebruik `unverified` alleen zolang de firmware die revisie expliciet rapporteert. Dit is geen bewijs van de PCB-revisie; registreer de werkelijke hardware bij fysieke commissioning vóór een pilot. Een ondersteund boardprofiel is nog geen acceptatie van alle boards met dezelfde USB-chip.

Enrollment is bewust: het commando vereist de verwachte paneelidentiteit en USB-seriecode, controleert VID/PID en de actuele poort, voert de v2-handshake uit en schrijft pas daarna de koppeling. Er wordt niet gescand naar een willekeurig paneel om dat automatisch te vertrouwen. Bestaande enrollment wordt nooit overschreven. Stop de service en verwijder de oude enrollment bewust bij een vervanging; identificeer daarna het nieuwe paneel opnieuw.

Een bestandlock voorkomt gelijktijdig enrollen/draaien op dezelfde configuratie. De serial-port wordt exclusief geopend. Configuratie en status worden atomisch met mode 0600 geschreven. De lock-directory en enrollment zijn lokaal beheerd; geef onbevoegden geen schrijfrecht. Eén installatie gebruikt één enrollmentpad; maak geen parallelle beheerders met eigen configpaden.

## Status en lifecycle

```sh
uv run panel-service status --status .secrets/service-status.json
```

Exitcode 0 betekent een niet-verlopen verbonden status; 1 betekent afwezig, stale, gestopt of een lees-/configuratiefout. Het statuscommando opent het paneel niet en heeft geen service-lock nodig.

`waiting` betekent dat discovery bezig is; `connected` volgt pas na gepinde handshake én actuele volledige snapshot. Een fout verwijdert bruikbare paneel-/apparaatstatus en geeft een vaste foutcode. Consumers moeten altijd de snapshotlease controleren; alleen het woord `connected` in een oud bestand is onvoldoende. `panel-service status` doet die controle ook als het serviceproces niet meer draait.

Requests en heartbeats zijn begrensd; discovery/reconnect heeft een backoff van 1 tot maximaal 15 seconden. Een ontbrekend paneel blijft in discovery. Re-enumeratie op een andere tty-naam is toegestaan als de gepinde USB-identiteit klopt. Elke geopende verbinding krijgt een nieuwe nonce en lege pending toestand, en vraagt een full snapshot. Na SIGTERM/SIGINT sluit de service de port en publiceert `stopped`; een geblokkeerde serial-read duurt maximaal 100 ms. De firmware laat een niet meer gevoede sessie binnen 3,5 seconden verlopen.

Er is geen commandowachtrij en geen retry van echte acties. Er wordt niets geflasht. Een gewone USB-open kan door de native USB-driver wel een reset veroorzaken. Laat niet tegelijk bench-/capture-/flashprogramma's op hetzelfde paneel draaien.

## Linux-container

```sh
docker build -t netlink-panel-service:0.6.0 .
```

[Het composevoorbeeld](../deploy/compose.usb.example.yml) is een los USB-only voorbeeld, geen fleetdeployment. Stel `PANEL_SERIAL_GID` in op de numerieke groep van het host-ttyACM-device. De image draait als UID/GID 65532, met alleen die aanvullende groep, zonder capabilities, zonder netwerk en met een read-only rootfilesystem. Alleen `/data` is schrijfbare persistente opslag. Een volume dat enrollment/status tussen recreaties bewaart is verplicht.

```sh
export PANEL_SERIAL_GID=<numerieke-device-groep>
docker compose -f deploy/compose.usb.example.yml run --rm panel enroll \
  --port <linux-ttyACM-poort> --panel-id <paneelidentiteit> \
  --usb-serial <usb-seriecode> --board-revision unverified
docker compose -f deploy/compose.usb.example.yml up -d
```

Het voorbeeld maakt host-`/dev` alleen-lezen zichtbaar om nieuwe ttyACM-namen na hotplug te kunnen ontdekken. Een device-cgroupregel staat uitsluitend lezen/schrijven van USB-CDC-ACM major 166 toe; er is geen `privileged`, blockdevice-, raw-USB-, GPIO- of UART-toegang nodig. DAC/groepsrechten en enrollment beperken verder welke poort gebruikt wordt. Het proces kan wel device-namen zien; het kernelrecht bestrijkt alle ttyACM-minors, omdat een gereserveerd minor niet stabiel blijft na herstart/hotplug. Een vast `devices:`-inode mounten is strikter maar overleeft re-enumeratie niet betrouwbaar. Als een fleet die dynamische cgroupregel/mount niet ondersteunt, moet de hostintegratie devices gericht doorgeven en de container na een gewijzigde enumeratie recreëren; beweer dan geen transparant hotplugherstel.

Gebruik het voorbeeld op een cgroup-/Docker-host die de toegangsregel afdwingt; test die eigenschap op de doel-NetLink. Een andere USB-chip/drivermajor vereist een expliciet beoordeelde configuratie, geen bredere wildcard. `/sys/class/tty` en bijbehorende USB-identiteitsmetadata moeten read-only beschikbaar zijn voor pyserial discovery. Er is geen toegang tot het bureau-UART of DDC nodig.

## NetLink-integratie en fysieke gate

De service hoort later als eigen image/block in de bestaande fleet-first Balena-stack. Deze PR wijzigt geen `netlink_balena`-compose, bestaande submodulepointer of fleet. De panel-service wordt geen tweede agent: agenthealth, desired state en remote autorisatie zijn aparte issues.

Begin met een vrije USB-datahostpoort van de bedoelde NetLink, gescheiden van het bureau-UART-pad. Gebruik geen voeding-only kabel. Het werkelijke voedingsbudget, beschikbare poort en gedrag bij inpluggen/reboot moeten op die hardware worden gemeten en geregistreerd; het Mac-prototype bewijst dat niet. Als USB-voeding tekortschiet moet de oplossing expliciet worden gevalideerd; geen stille afhankelijkheid van wifi of ongeteste hub.

Nog fysiek te bewijzen op de doel-NetLink (issues #9 en #24): voeding, juiste port/group/cgroup-toegang, identificatie, enrollen, de container lifecycle en hotplug/reboot met nieuwe tty-naam. De test moet aantonen dat bureau- en monitorservices ongestoord blijven. De bestaande pseudoterminaltests bewijzen het servicepad en de nieuwe handshake, niet de fysieke Linux-device/permissie- of voedingslaag.

## Checks

```sh
uv run python -m unittest discover -s tests -v
uv tool run --from ruff ruff check .
uv tool run --from ruff ruff format --check .
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

De firmwarebuild moet eerst één keer gedaan zijn om de gepinde ArduinoJson-headers voor de native protocoltests beschikbaar te maken. Tests gebruiken eigen pseudoterminals en schrijven niet naar het echte paneel.

## Fysieke USB-proef op de Mac — 4 november 2026

Firmware 0.6.0 uit broncommit `684205f` is na controle van USB-identiteit, fabrieksbackup en actieve slot app-only via USB geschreven. Esptool verifieerde de flashhash. Daarna bevestigde de v1-hello de verwachte imagehash, versie 0.6.0, VALID en geslaagde startup-self-check.

Op hetzelfde fysieke paneel slaagden de v2-handshake, boardprofiel-/identiteitscontrole, snapshots met revisies 1/2/3 en het afwijzen van niet-ondersteunde acties. De gerapporteerde boardrevisie blijft bewust `unverified`; bureau en monitor bleven onbekend. Er zijn geen UI-acties geïnjecteerd of echte apparaatcommando’s verstuurd.

De eerste directe overgang na een v1-hello leverde terecht `busy`: een open USB-client sluiten beëindigt de applicatiesessie niet meteen. Na de 3,5-seconden-livenessgrens slaagde v2. Wacht bij handmatige enrollment na het stoppen van een benchclient minimaal vier seconden; de daemon probeert bij busy zelf opnieuw met backoff. Dit vereist geen firmwarewijziging.

De echte CLI-enrollment slaagde, schreef mode 0600 en weigerde overschrijven. Een serviceproef van 15 seconden leverde 14 verschillende actuele revisies; na nette stop en herstart volgden opnieuw revisie 1 en vijf actuele revisies in vijf seconden. Een tweede gelijktijdige service werd in beide proeven geweigerd. SIGTERM sloot de service en publiceerde `stopped`. Na een afzonderlijke geforceerde hostprocesstop (SIGKILL) werd de oude snapshot na vier seconden als stale zonder bruikbare status gelezen. Een nieuwe service begon opnieuw bij revisie 1 en is na de controle netjes gestopt.

Dit bewijst USB-communicatie met het display vanaf macOS. Het is geen fysieke kabel-hotplug, stroomuitval-, duur- of doel-NetLink-permissietest. Het lokale bewijs staat onder `artifacts/display-0.6.0/verification.json` (bewust buiten Git); de bijbehorende image en manifest staan onder `artifacts/releases/`.
