# Herstelbare OTA — 2026-11-03

## Vastgestelde oorzaak

De diagnostische firmware registreerde op het echte paneel eerst een wifi-disconnect met reden 3 (`WIFI_REASON_AUTH_LEAVE`) bij uptime 14004 ms. Daarna meldde TLS `data_to_read` fout -76 en werd de sessie vrijgegeven bij uptime 14071 ms. De laatste geldige hostactiviteit was toen slechts 120 ms geleden. De upload brak af op offset 73216, ruim vóór activatie. De daaropvolgende handshake gaf dezelfde geldige image en koppeling terug.

Dit toont voor deze gereproduceerde fout dat wifi-verlies vóór de TLS-reset kwam; de control/OTA-deadline was niet verstreken. Waarom de associatie werd verbroken (station/accesspoint/radio) is niet vastgesteld. De connect-call van één seconde beïnvloedt ook het TLS-writebudget in Arduino 2.0.14, maar deze meting bewijst geen write-timeout. Dat budget is daarom niet als onbewezen oorzaak aangepast.

De applicatiefout die OTA fataal maakte is wel vastgesteld: `releaseSession()` riep altijd `ota.abort()` aan en de host stopte bij de eerste transportfout. Zelfs een geschreven blok met verloren bevestiging kon daardoor niet worden hervat. De vorige 15-seconden-timeoutcorrectie loste dat niet op.

## Wijziging

- Het geldige actieve slot blijft tijdens de volledige overdracht geselecteerd. Een transferhandle en lopende SHA-256 in RAM overleven wifi/TLS-verlies maximaal 60 seconden zonder transferactiviteit.
- Een nieuwe wederzijds geauthenticeerde sessie kan alleen hetzelfde volledige manifest hervatten. Grootte, profiel, versie en beide SHA-256-waarden moeten overeenkomen. De werkelijk geschreven positie wordt geretourneerd; er wordt niet opnieuw gewist of dubbel geschreven. Een andere image wordt geweigerd.
- De host valideert de positie, herstelt maximaal vijf keer binnen zijn deadline van standaard 600 seconden en meldt herstel. Geen automatische retry op een inhoudelijke weigering of bij legacy-firmware zonder hervatcapability.
- USB-overname, expliciet afbreken en leaseverloop ruimen de transfer op. Een paneelreset verliest de RAM-transfer; opnieuw beginnen vanaf nul is dan veilig. Normale bediening behoudt de 3,5-seconden-timeout en bediening blijft tijdens OTA geblokkeerd.
- Activatie vereist nog steeds lengte, beide hashes, image-identiteit en ESP-imagevalidatie. Succes vereist een nieuwe sessie met de gewenste boot, startup-self-check en teruggelezen VALID-bootbevestiging. Verloren finish- en confirm-antwoorden worden door statuscontrole opgelost.
- Hello bevat uptime, resetreden en de laatste wifi-disconnectreden. Tijdelijke debugprints en extra SDK-logniveau zijn uit de definitieve firmware verwijderd. Overbodige schermredraws op tientallen opeenvolgende chunks met hetzelfde procentbereik zijn beperkt tot één per 10%-stap.

## Validatie

- De volledige suite van 43 lokale tests slaagde zonder skips; twee daarna gevonden hostproblemen zijn met twee aanvullende TLS-regressies afgedekt en de betrokken suite van 10 TLS-tests slaagt (45 unieke tests in totaal). Lint en formattering slagen. Dekking: inclusief echt TLS, verloren begin-/blok-/finish-/confirm-antwoorden, ongeldige resume-offsets en de daadwerkelijke firmware-handler met getelde fake SDK-writes. De nieuwe TLS-test ging eerst rood met `ConnectionError`; de handler ging eerst rood op onvermogen te hervatten. Beide werden groen na de wijziging.
- Firmware 0.3.2 met herstelcode succesvol gebouwd en eenmaal via USB geïnstalleerd; geschreven flashhash geverifieerd. De aparte diagnostische build was daarvoor eenmaal geïnstalleerd. NVS en partitie-indeling zijn behouden.
- Fysieke serveruitval van 5 s: hervat op byte 4096, nieuwe verbinding na 4,28 s vanaf heropenen, geen paneelreset.
- Fysiek verzonden chunk zonder zijn ACK te lezen: hervat op byte 4608, nieuwe verbinding na 4,28 s, geen blinde herschrijving. Beide proeven eindigden met expliciet abort, oorspronkelijke image VALID en `receiving=false`.

| Volledige proef | Resultaat |
| --- | --- |
| 1: naar 0.3.3, 904144 bytes | Automatisch geslaagd, nieuwe boot en VALID teruggelezen; 0 herstelmoment(en). Circa 100.08 s vanaf serverstart tot bevestiging. |
| 2: naar 0.3.2, 904144 bytes | Alle bytes en reboot geslaagd; oude host stopte op rebootrace. Alleen bootbevestiging hersteld, zonder herupload. |
| 3: naar 0.3.3, 904144 bytes | Automatisch geslaagd, nieuwe boot en VALID teruggelezen; 2 herstelmoment(en). Circa 144.61 s vanaf serverstart tot bevestiging. |

De derde proef verloor echt de verbinding na het begin van de overdracht. De gewone updater hervatte automatisch vanaf byte 12800 en voltooide daarna de hele image en bootbevestiging. Dit is fysieke end-to-end-herstelvalidatie, aanvullend op de twee bewust onderbroken proeven. Er zijn exact zes OTA-overdrachtsproeven uitgevoerd: één diagnostische, twee gedeeltelijke herstelproeven en drie volledige transfers. Geen extra transfer na de rebootrace; alleen status en bootbevestiging.

Eindstatus: firmware **0.3.3**, verwachte imagehash `d7428a80fe06f3fe1423d089759011193efd6c0c3864afe30b19e2a7334166dd`, **VALID**, startup-self-check geslaagd en geen actieve transfer. Een extra read-only sessie van 30 seconden en drie herverbindingen slaagden. Hosttool en lockfile staan op 0.3.3; de lokale installatie is gesynchroniseerd.

Conclusie: de oorspronkelijke fatale transportonderbreking is hersteld en op hetzelfde paneel opnieuw beproefd. Volledige update, echt verbindingsverlies, automatisch hervatten, reboot en bevestiging zijn samen geslaagd. Dit is acceptatie van deze begrensde herstelroute; geen bewijs van meerdaagse of elektrische stroomuitvalbestendigheid.

## Aanvullende rebootrace

De tweede volledige transfer bereikte 100% en activeerde de kandidaat, maar de updater ontving op een te vroege handshake nog een negatieve ACK van de oude, al gecommitteerde firmware. De host behandelde die als `Unexpected OTA response type` en stopte. Een statuscontrole zag daarna exact de gewenste 0.3.2 als PENDING_VERIFY, met startup-self-check geslaagd. Alleen bootbevestiging is hersteld; er is geen transfer herhaald. Dat gebeurde vóór de bootdeadline, waarna dezelfde hash als VALID is teruggelezen.

De host onderscheidt nu een expliciet afgewezen hello (`HandshakeRejected`) van onverwachte protocoldata. Alleen tijdens een lopend herstel of verwachte reboot wordt dat binnen hetzelfde reconnectbudget opnieuw geprobeerd. Er wordt geen firmware blind opnieuw geschreven. Een echte TLS-regressie ging eerst rood op dit exacte negatieve ACK-pad en werd groen na de correctie.

Een andere gerichte TLS-regressie voorkwam dat de host na een inhoudelijk geweigerd `ota_begin` met `ota_abort` een al actieve andere image annuleerde. Die automatische abort is verwijderd; de firmware bewaakt zijn eigen transferlease en inhoudelijke foutafhandeling.

## Bewijs en grenzen

`artifacts/ota-reset-diagnostic.json` en `artifacts/ota-reset-diagnostic-usb.log` bevatten de gemeten fout. `artifacts/ota-resume-physical-faults.json` bevat de twee fysieke herstelproeven. `artifacts/ota-resume-full-1.json`, `ota-resume-full-2.json`, `ota-resume-full-2-recovery.json` en `ota-resume-full-3.json` bewaren de volledige updatepogingen, inclusief het oorspronkelijke onbevestigde resultaat van de tweede poging en de afzonderlijke bevestiging achteraf. `artifacts/ota-resume-final-status.json` en `artifacts/ota-resume-summary.json` bevatten de eindcontrole en het overzicht. Het herhaalbare opt-in script is `scripts/hardware_ota_recovery.py`; de gewone updater blijft `panel wifi update`.

Deze proeven geven geen garantie tegen iedere netwerkstoring. Buiten bereik of langer dan de herstelbudgetten geeft een gecontroleerde fout en blijft de bekende geldige image actief. Elektrische stroomuitval tijdens schrijven/activeren, echte accesspointuitval, USB-overname tijdens schrijven en meerdaagse stabiliteit zijn niet getest. De eerder fysiek bewezen 90-seconden-rollback blijft behouden; die proef is niet opnieuw uitgevoerd. De fabrieksbackup en pairing blijven privé.

Bronnen voor SDK-semantiek: [Arduino WiFiClientSecure 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/WiFiClientSecure.cpp), [TLS transport 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/ssl_client.cpp), [ESP-IDF 4.4.6 OTA](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html).
