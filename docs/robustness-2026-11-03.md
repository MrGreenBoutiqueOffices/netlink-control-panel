# Fysieke robuustheidscontrole — 2026-11-03

> Dit rapport beschrijft de eerdere diagnosefase tot en met timeoutfix 0.3.1. De vervolgfix en huidige eindstatus 0.3.3 staan in [het OTA-herstelrapport](ota-recovery-2026-11-03.md); daar is een volledige update met echt verbindingsverlies en automatisch hervatten geslaagd.

## Oordeel van deze eerdere fase

De basisbediening, reconnect en terugval werken in de uitgevoerde proeven. De normale wifi-updateoverdracht is **nog niet voldoende betrouwbaar**: twee eerdere updatepogingen en de eenmalig toegestane proef met timeoutfix 0.3.1 braken vóór activatie af. Dit is geen productieacceptatie.

Na expliciete toestemming is de timeoutcorrectie `0.3.1` eenmaal via USB geïnstalleerd; esptool verifieerde de geschreven hash. Daarna is precies één wifi-overdracht van dezelfde image geprobeerd. Die brak na minstens 40% af met `ConnectionResetError`, vóór `ota_finish`, herstart of bootbevestiging. Er is geen upload herhaald. Het display draait nog de geldige via USB geïnstalleerde `0.3.1`; de wifi-koppeling bleef behouden en `receiving` was bij controle `false`.

## Gemeten resultaten

| Proef | Resultaat |
| --- | --- |
| Antwoord op hello vóór wijziging | 589 bytes verdeeld over 559 TLS-reads; mediaan 1,069 s over 8 aanvragen |
| Antwoord na pakketverbetering | Meestal 1 TLS-read, eenmaal 2; mediaan 0,07465 s over 8 aanvragen, circa 14 keer sneller |
| Doorlopende sessie | 30 s, alle 30 heartbeats ontvangen, 0 afgekeurde frames |
| Opnieuw verbinden | 5 van 5 geslaagd; gemeten 0,32–5,47 s |
| Serverpoort gesloten | Na 5 s onbereikbaarheid vanzelf terug; circa 5 s na heropenen |
| Host stuurt geen heartbeats | Paneel beëindigde de verouderde sessie na 3,76 s |
| Ongeldige/grote invoer | Na 10010 bytes ongeldige/te grote invoer werkte een geldig commando weer |
| Touch | Zitten-, Staan- en Monitor-events ontvangen; gebruiker bevestigde de knoppen aan te raken |
| Afgebroken flashoverdracht | Na 4096 geschreven bytes TLS verbroken; vorige image bleef VALID en actief |
| Volledige kandidaat | 902768 bytes in 91,44 s over wifi; juiste kandidaat startte als PENDING_VERIFY |
| Bewust niet bevestigen | Automatisch terug naar de vorige VALID-image na 90,56 s vanaf de waargenomen pending-boot |
| Normale updatepogingen | Twee afgebroken overdrachten, na minstens 60% respectievelijk 90%; geen activatie |
| Eenmalige proef met timeoutfix | USB-installatie en hashverificatie geslaagd; wifi-overdracht van dezelfde image na minstens 40% afgebroken vóór activatie |
| Huidige toestand | 0.3.1 draait VALID, zelftest geslaagd, geen actieve gedeeltelijke overdracht; aanvullende read-only sessie van 10 s geslaagd |
| Lokale tests | 36 tests geslaagd, zonder overgeslagen tests; lint en formattering geslaagd |

De responstijdmeting is een kleine voor/na-meting, geen gestandaardiseerde radiobenchmark. RSSI wisselde tijdens de proeven van ongeveer -79 tot -89 dBm. De latencyverbetering bewijst niet op zichzelf de oorzaak van iedere verbroken verbinding.

## Aangetoonde verbetering

`serializeJson` schreef rechtstreeks naar WiFiClientSecure en veroorzaakte vrijwel een TLS-record per byte. De native regressietest ging rood met 96 writes voor een frame van 96 bytes. De firmware bouwt nu eerst een begrensd JSON-frame op en verstuurt dat in één write. De regressietest en fysieke meting bevestigen dit effect. Een te groot frame wordt geweigerd; een onvolledige write sluit de verbinding.

De eerste draadloze installatiepoging van deze verbetering brak af. De oude image bleef intact. De verbetering is vervolgens eenmalig via USB in hetzelfde applicatieslot geplaatst, zonder NVS, bootloader of partities te vervangen. De wifi-koppeling bleef behouden.

## Tweede correctie: geïnstalleerd, wifi-overdracht nog niet betrouwbaar

De firmware sloot ook een lopende OTA-sessie na 3,5 s zonder verwerkte hostactiviteit, terwijl de OTA-overdracht een eigen inactiviteitsbudget van 15 s had. Een native test tegen de echte beleidsfunctie reproduceert dit verschil.

De geïnstalleerde correctie gebruikt 15 s uitsluitend tijdens een actieve OTA-overdracht en behoudt 3,5 s voor gewone bediening. Touchbediening blijft tijdens OTA geblokkeerd. De transferguard en sessie delen één constante om toekomstige afwijking te voorkomen. Dit kan onderbrekingen bij tijdelijke vertraging helpen voorkomen; dat deze timeout de waargenomen fysieke verbreking veroorzaakte, is nog niet bewezen.

De latere read-only uptimecontrole past binnen circa 3,3 s op de bekende bewuste rollback-herstart. Er is daarmee geen aanwijzing voor nog een onverwachte herstart tijdens de laatste mislukte overdracht. Radioproblemen en het exacte verbreekmoment moeten nog van de sessietimeout worden onderscheiden.

Geïnstalleerde image: `artifacts/releases/panel-0.3.1-ota-lease-fix.bin`. Hele-bestand-SHA-256: `0efb702697ea3de16592c43cbb80bd5948e1cb2739af0e4adcfec9e6701aadaa`; ESP-content-SHA-256: `9292af414b67fa2bd41afb4d0b985e00fd1d2fda24f2b261ec9fa5ac67e070de`. Deze hash is na de USB-installatie én na de mislukte wifi-overdracht op het echte paneel teruggelezen met status VALID. De wifi-overdracht blijft ondanks deze correctie falen; de timeoutafwijking is daarmee geen voldoende verklaring of oplossing voor de fysieke resets. Bij de herstelcontrole was RSSI -81 dBm. De volledige succesvolle OTA-route met deze image is niet aangetoond.

## Bewijs en herhalen

- `artifacts/tls-before.json`: voor-meting en regressiegegevens.
- `artifacts/hardware-after-batching.json`: reconnect-, heartbeat-, parser- en latencyproeven.
- `artifacts/hardware-ota-faults.json`: fysieke onderbreking, volledige kandidaat en echte rollback.
- `artifacts/failed-ota-recovery.json` en `artifacts/current-after-update-failures.json`: geldige toestand na afgebroken overdrachten.
- `artifacts/robust-rc1-install.json` en `artifacts/robust-final-0.3.1.json`: de mislukte normale pogingen; deze zijn geen succesbewijzen.
- `artifacts/read-only-reset-check.json`: eerdere uptime/statuscontrole.
- `artifacts/hardware-0.3.1-approved-once.json`: geverifieerde USB-boot en de eenmalige mislukte wifi-overdracht met timeoutfix.
- `artifacts/hardware-0.3.1-after-approved-failure.json`: behouden geldige 0.3.1, zelftest, wifi en opgeruimde transferstatus na die poging.
- De volledige fabrieksbackup en wifi-credentials blijven privé onder `.secrets/`.

Niet-schadelijke softwarechecks:

```sh
uv run python -m unittest discover -s tests -v
uv tool run --from ruff ruff check .
uv tool run --from ruff ruff format --check .
```

`scripts/hardware_robustness.py` gebruikt het echte gekoppelde paneel. Zonder kandidaat test het verbindingen en inputfouten; met `--candidate` schrijft het daadwerkelijk naar het ongebruikte flashslot en veroorzaakt het herstarts. Niet parallel met `panel wifi serve` of een andere updater starten. De expliciet toegestane USB-installatie en ene wifi-overdracht zijn uitgevoerd. Verdere fysieke firmwarewrites vallen buiten die eenmalige toestemming.

Nog niet getest: elektrische stroomuitval midden in schrijven/activatie, een echte accesspointuitval, slaapstand van de Mac, meerdaagse stabiliteit en een succesvolle volledige update met de aanvullende timeoutcorrectie. De bestaande koppeling gebruikt een vast Mac-adres; een gewijzigd adres vraagt nu nog om opnieuw instellen.
