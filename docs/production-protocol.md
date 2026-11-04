# NetLink panel protocol v2

Dit is het contract voor de panel-service. Het is onafhankelijk van USB of een geauthenticeerde wifi-stream. Firmware 0.6.0 en host 0.6.0 implementeren de handshake en volledige paneelstatus. Echte bureau-/monitoracties, configuratiesynchronisatie en beheerde updates worden pas vrijgegeven met hun eigen capabilities en adapters. De firmware blijft een lokale demo; `desk` en `monitor` zijn daarom `null`.

Het bestaande [benchprotocol v1](protocol.md) blijft beschikbaar voor demo, USB-provisioning en diagnostiek/herstel. Een v2-sessie accepteert geen v1-berichten. Een v1-client kan een actieve v2-sessie niet overnemen; na disconnect verloopt de sessie binnen 3,5 seconden. Firmwareversie 0.6.0 in de bron betekent niet dat deze al op een fysiek paneel is geïnstalleerd.

## Framing en compatibiliteit

- UTF-8 JSON-objecten, één per newline; maximaal 1024 bytes exclusief newline. USB CDC gebruikt 115200 baud. Geen logging op de protocolstream.
- Elke v2-envelope heeft integer `v: 2` en een niet-lege `type`. Een request/response heeft integer `id` in 1..2147483647, uniek binnen de sessie. Bool is geen integer-ID.
- Host en paneel moeten een overlappend `protocol_min`/`protocol_max` hebben; deze implementatie ondersteunt alleen 2. De host weigert onbekende boardprofielen, andere paneelidentiteiten, andere boardrevisies, ongeldige bootstatus en ontbrekende capabilities.
- Framingversie 1 en 2 zijn geïsoleerd. Alleen v2 kan deze handshake onderhandelen; een onbekende envelopeversie wordt genegeerd en leidt op de host tot een begrensde timeout. Een v2-hello met een incompatibel bereik krijgt `incompatible_protocol`.
- Onbekende optionele velden mogen worden genegeerd; een betekeniswijziging van bestaande velden vereist een nieuwe contractversie/capability. Een frameoverschrijding wordt tot de volgende newline weggegooid; foutieve frames vernieuwen geen heartbeat.

## Handshake en identiteit

De host kiest per verbinding een cryptografisch willekeurige `session` van 32 lowercase hextekens. Responses, status en heartbeats horen bij die sessie; laat ontvangen frames uit een andere sessie worden niet toegepast.

```json
{"v":2,"type":"hello","id":1,"session":"0123456789abcdef0123456789abcdef","protocol_min":2,"protocol_max":2}
```

Het paneel antwoordt met dezelfde id en sessie, plus:

| Veld | Betekenis |
| --- | --- |
| `panel_id` | Stabiele paneelidentiteit, apart van de USB-seriecode |
| `board_profile` | `lilygo-s3-long-cst3530` voor deze build |
| `board_revision` | Voorlopig `unverified`: geen automatische detectie of claim van een vastgestelde PCB-revisie |
| `firmware` | Firmwareversie uit de gedeelde versiebron |
| `protocol_min`, `protocol_max` | Ondersteund contractbereik, nu beide 2 |
| `boot_id` | 16 willekeurige hextekens per boot; geen persistent apparaat-ID |
| `boot_state`, `self_test_ok` | De service accepteert uitsluitend `valid` en `true` |
| `capabilities` | Nu alleen `panel.status.v1` |
| `actions` | Nu leeg; de host heeft nog geen actuatieroute |

Een gezonde startup-self-check bevestigt initialisatie; het is geen test van fysieke touchkwaliteit of echte bureauveiligheid. Enrollment pinnt USB VID, PID, seriecode én handshake-identiteit/profiel/revisie. Het is een lokale autorisatie op de host, geen wederzijdse cryptografische USB-authenticatie. Alleen status wordt nu ontsloten; aansturingsrechten en enrolled-host-verificatie op het paneel moeten vóór echte besturing worden afgedwongen.

De firmwarehandler is voor beide streams identiek. De bestaande wifi-stream vereist zijn eigen TLS-PSK-authenticatie; de nieuwe Linux-service implementeert in deze PR uitsluitend USB. Transportselectie/fallback en wifi-enrollment blijven vervolgwerk. Een actieve andere sessie of OTA-procedure levert `busy`; deze handshake onderbreekt nooit een lopende OTA.

## Liveness en status

Beide peers sturen elke seconde `heartbeat` met `session`; het paneel voegt `uptime_ms` toe. Alleen een geldige heartbeat uit de actieve sessie of een geaccepteerd request vernieuwt firmwareliveness. De host hanteert 3,5 seconden en een afzonderlijke requestdeadline. Handshake mag maximaal acht seconden duren om USB-reset/boot op te vangen; binnen die periode worden alleen hello-pogingen herhaald.

Na iedere handshake vraagt de host een volledige snapshot en daarna periodiek opnieuw:

```json
{"v":2,"type":"state.get","id":2,"session":"0123456789abcdef0123456789abcdef"}
```

```json
{"v":2,"type":"state.snapshot","id":2,"session":"0123456789abcdef0123456789abcdef","revision":1,"sampled_uptime_ms":1234,"valid_for_ms":3500,"state":{"self_test_ok":true,"mode":"standalone_demo","desk":null,"monitor":null}}
```

`revision` stijgt per snapshot binnen één sessie, vanaf 1. Dit is een observatierevisie, ook als de waarden gelijk blijven. `sampled_uptime_ms` is het 32-bits lokale paneeltijdstip; het is geen klok die met de host gesynchroniseerd wordt. Nieuwe boot/sessie betekent een nieuwe revisiereeks. Deltas zijn nog niet geïmplementeerd; volledige snapshots zijn voor dit kleine contract de enige statusvorm.

De host vermindert `valid_for_ms` met de gemeten requestduur en publiceert een eigen ontvangsttijd. Consumers mogen een snapshot alleen gebruiken zolang die resterende lease geldig is. `panel-service status` berekent dat opnieuw, ook na een gecrashte service of teruggezette klok. Een verlopen snapshot wordt als stale zonder paneel-/apparaatstatus teruggegeven. Een heartbeat alleen maakt oude status niet actueel.

## Actiecontract voor volgende adapters

Voor latere echte bediening geldt normatief:

1. `action.request` bevat sessie, unieke request-id, `action`, gevalideerde `args` en `ttl_ms` (1..3500). TTL loopt bij de ontvangende adapter vanaf ontvangst; de host gebruikt daarnaast zijn eigen deadline en verstuurt nooit een vooraf verlopen opdracht.
2. `action.result` gebruikt dezelfde sessie en id. `stage: received` bevestigt alleen syntactische ontvangst; `accepted` alleen toelating door de bevoegde actuatoradapter; `completed` alleen een aantoonbare fysieke uitkomst. Ontbreekt uitkomstfeedback, dan volgt `unknown`, nooit een verzonnen `completed`.
3. `rejected`, `failed`, `expired` en `unknown` zijn expliciete einduitkomsten met een vaste `code`. Een TCP/USB-write of MQTT-publish is geen voltooiing.
4. Binnen een sessie behandelt de toekomstige adapter duplicaat-id's idempotent: zelfde inhoud geeft dezelfde bekende uitkomst, andere inhoud wordt geweigerd. Hij mag dezelfde actie niet nogmaals uitvoeren. Een sessie heeft geen overneembare pending acties; reconnect start met lege autorisatie en snapshot.
5. Reconnect, transportwissel, stop, update of verlopen liveness wist pending bewegingen. Geen automatische retry of replay van beweging. Stopgedrag moet ook bij hostcrash bij de component die nog kan stoppen worden geborgd.

De huidige handler retourneert voor elke `action.request` alleen `action.result` met `stage: rejected` en `code: unsupported_action`; hij voert niets uit en adverteert geen acties. Deze toekomstige stages/deadlines zijn een contract, nog geen geïmplementeerde MQTT-action-engine. Zie issue #10 voor capability- en idempotentiehandhaving op de echte commandoroute.

## Afbakening en fouten

Demo-, provisioning- en updatecommando's zijn geen productieacties. Ze worden in een v2-sessie geweigerd. `state.get` is de enige huidige productierequest na hello. Onbekende berichten leveren `unsupported_message`; ontbrekende/andere sessie levert `session_required`; ongeldig request levert `invalid_request`. Geen fouttekst bevat credentials of vrije peerdata.

Bij disconnect gooit de host sessie, decoderbuffer en outstanding requests weg. Discovery begint opnieuw met de gepinde USB-identiteit, daarna volgen handshake en full snapshot. Een ander of vervangend paneel wordt niet automatisch enrolled.

## Verificatie

`tests/test_service.py` compileert de echte `ProductionSession`-handler met de gepinde ArduinoJson-library en verbindt die via pseudoterminals met de Python-service. De suite dekt identiteit/versies/health, revisies, statusfreshness, onbekende acties, framingisolatie en re-enumeratie. De firmwarebuild controleert de wiring voor USB en wifi. Dit is geen fysieke USB-, radio-, stroom- of NetLink-acceptatie.

## Read-only apparaatstatus vanaf 0.7.0

De nieuwe capability `device.state.v1` accepteert een hostrequest `device.state` met dezelfde sessie/id, oplopende `revision`, `valid_for_ms` (1–3000), `desk` en `monitor`. Beide apparaatvelden zijn expliciet object of `null`. Zonder capability verstuurt de host dit bericht niet. Alle `action.request` blijven afgewezen; er wordt geen bureau-/monitoractie uitgevoerd.

`desk` bevat integer `height_mm` (0–3000) en boolean `fresh`. Dit is een waarneming: de commandogrenzen 620–1270 mm worden niet op werkelijke metingen geklemd. `monitor` bevat de gekozen numerieke `bus` (maximaal 8 tekens), `brightness` (0–100 of null), `power` (`on`/`off`/`standby` of null), `source` (maximaal 24 zichtbare ASCII-tekens of null) en boolean `fresh`. Ontbrekende metingen worden niet vervangen door defaults. Een vaste HDMI-bron van een Waveshare is geldige read-only status, ook zonder source-switchcapability.

De firmware valideert de volledige snapshot vóór toepassing. Een ongeldige, dubbele of oudere revisie vervangt niets en vernieuwt de datalease niet. Antwoord is `device.state.ack` met dezelfde sessie/id en toegepaste revisie. Na verlopen lease, sessieverlies of nieuwe handshake worden alle apparaatwaarden onbekend. Een heartbeat alleen vernieuwt de datalease niet. Nieuwe waarden maken geen slapend scherm wakker.

Het display toont gemeten hoogte en helderheid/power/ingang; `fresh:false` krijgt de tekst LAATST BEKEND. Onbekende waarden verschijnen als `--`/Onbekend. Bureau-/monitorbediening, presets en fysieke demo-reset/scenariogebaren zijn in deze modus geblokkeerd; lokale paneelinstellingen en navigatie blijven beschikbaar. Een expliciete bench-scene kan de standalone demo opnieuw openen nadat de productie-eigenaar is gestopt. Geen automatische terugval naar demowaarden bij verlies van de host.

`state.snapshot.state.mode` blijft vóór de eerste `device.state` voor oude hosts `standalone_demo`; daarna is het `read_only`, ook na leaseverloop. De bijgewerkte hostcore accepteert beide modes. Nieuwe host plus oude firmware behoudt statusbewaking maar verstuurt geen apparaatstatus. Installeer host en firmware daarom als gekoppelde, capability-gecontroleerde wijzigingen.

De webserver blijft eigenaar van MQTT-status. De upstream hostmodule krijgt alleen generieke requestvelden en modecompatibiliteit; de webserver gebruikt daarvoor de bestaande SerialX-adapter, zonder pySerial terug toe te voegen. Firmware 0.7.0 wordt in deze wijziging gebouwd en native getest, niet automatisch op het fysieke paneel geïnstalleerd.

## Lokale paneelconfiguratiestatus vanaf 0.8.0

De optionele capability `panel.config.status.v1` voegt `state.panel_config` toe aan de bestaande snapshot. Deze bevat schema, opgeslagen revisie, paneelhelderheid, rotatie, dimtijd en begrensde opslagstatus. Geen credentials, bureaupresets of beheerde writes. Zie [het opslag- en eigenaarschapscontract](panel-settings.md). Onbekende configuratieverzoeken blijven geweigerd; dit verleent geen extra apparaat- of configuratierechten.
