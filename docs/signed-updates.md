# Ondertekende updates — eerste deel van #15

Deze implementatie voegt onafhankelijke releaseautorisatie toe aan de bestaande wifi-bench-OTA. Host en paneel controleren dezelfde ECDSA P-256/SHA-256-handtekening. Zelfstandig downloaden en installeren via wifi is het doel van #15; dat is nog niet geïmplementeerd. De huidige bench-route vereist een host voor aanlevering en bootbevestiging. De paneeleigen update-lifecycle, downloadclient, lokale bediening, persistente pogingadministratie en opstartbevestiging zonder host blijven open. Fysieke full-image-OTA-acceptatie blijft #14.

## Trust en build

`release/update-trust.json` is de expliciete, gereviewde publieke buildpolicy. De standaard is `mode: bench`, zonder sleutels en met minimumcounter 0. De handshake meldt dan `bench_unsigned`; deze prototypebuild accepteert de bestaande unsigned update-start. Hij presenteert zich niet als ondertekend beheerd paneel.

Voor een signed build bevat de policy schema 1, `mode: signed`, een `minimum_counter` (uint64) en maximaal vier publieke sleutels. Een sleutel bevat `id` (de eerste 16 bytes van SHA-256 over canonieke SPKI DER, lowercase hex), `public_key` (canonieke base64 van P-256 SPKI DER) en een boolean `revoked`. De private key hoort hier nooit in. De build weigert ongeldige of dubbele sleutels, andere curves en ongeldige counters. `PANEL_BOARD_REVISION` is een gecontroleerd buildgegeven van maximaal 32 ASCII-identifiertekens; ontbrekend blijft het `unverified`.

De gegenereerde publieke policy en boardrevision worden in de applicatie ingebouwd. Een retained `NETLINK_PANEL_TRUST_V1|<mode>|<revision>|<policy_sha256>;`-marker identificeert de canonieke publieke policy (`json.dumps(sort_keys=True, separators=(",", ":"))`). De signer en host controleren dat deze marker bij hun publieke policy past. De marker is via het afzonderlijke `ota_policy`-diagnoseverzoek opvraagbaar, zodat de normale handshake binnen het bestaande frame blijft. De lokale verificatiepolicy van een al draaiend paneel wordt niet vervangen door velden uit een download.

Een signed policy weigert `ota_begin` altijd. Onbekende boardrevision, ontbrekende/ingetrokken sleutels of ongeldige handtekeningen maken signed updates onmogelijk; ze schakelen niet terug naar unsigned. De eerste bekende boardrevision en publieke trust moeten via een gecontroleerde USB-/factory-installatie worden voorzien en onafhankelijk geverifieerd. Deze PR doet dat niet en bevat geen productiesleutels.

## Ondertekende bytes

`authorization.json` heeft exact de twee velden `authorization` en `signature`. Beide zijn canonieke base64. De signature is canonieke ASN.1 DER ECDSA, maximaal 72 bytes, over de exacte recordbytes met SHA-256. Geen JSON-canonicalisatie is onderdeel van het wireprotocol.

| Recordveld in volgorde | Encoding |
| --- | --- |
| Domain/version | ASCII `NETLINK-PANEL-OTA`, gevolgd door `00 01` |
| Key-ID | 16 ruwe bytes |
| Releasecounter | uint64 big endian, minimaal 1 |
| Protocol minimum / maximum | elk uint16 big endian, inclusief grenzen |
| Firmwarelengte | uint32 big endian, 288 t/m 0x300000 |
| Firmwarebestand SHA-256 | 32 bytes |
| ESP-image SHA-256 | 32 bytes |
| Exact `manifest.json` SHA-256 | 32 bytes |
| Sourcecommit | 20 bytes |
| Versie / boardprofiel / boardrevision / partitielayout | elk één lengtebyte en ASCII `[A-Za-z0-9._:-]+`; maximaal respectievelijk 31/64/32/32 bytes |

Trailing bytes en ongeldige lengtes worden geweigerd. De decoder begrenst records op 340 bytes; requests passen binnen het bestaande 1024-byte-frame en de ArduinoJson-arena. De bekende combinatie is boardprofiel `lilygo-s3-long-cst3530`, layout `ota3m-v1`, protocol 2. De firmwareversiemarker blijft bovendien aan de bestaande imagecontroles onderworpen.

De host verifieert vóór netwerkcontact de handtekening, exacte manifestbytes, image-integriteit, versie, broncommit, compatibiliteit en de vereiste drie artifactdigests. De paneelverifier controleert de record, sleutel, boardrevision, protocol, layout, lengte en minimumcounter vóór `anchorRunning()` of `esp_ota_begin()`. De volledige recorddigest bindt hervatten; een andere autorisatie met dezelfde image kan een lopende transfer niet overnemen. Afgewezen autorisatie breekt die transfer niet af.

Daarna blijven de bestaande chunk-, bestandhash-, ESP-imagehash-, profiel-, slot- en pending/confirm/VALID-controles actief. Alleen applicatieslots worden beschreven; NVS, bootloader en partitietabel vallen buiten routine-OTA.

## Release en hostgebruik

De bestaande `release.published`-job in environment `release` blijft eigenaar van de assets. Bij bewuste activering vereist hij:

- De gereviewde signed publieke policy in de releasetag.
- De bevestigde `PANEL_BOARD_REVISION` als environment variable in GitHub (`vars`).
- De private P-256 PEM als environment secret `PANEL_RELEASE_SIGNING_KEY`, uitsluitend beschikbaar in de signingstap.

De GitHub-release-ID wordt de releasecounter. `scripts/sign_release.py` tekent eerst in een tijdelijke stagingmap en valideert daar de bundle. Daarna schrijft hij signed manifestmetadata, `authorization.json` en bijgewerkte `SHA256SUMS`. Signed releases hebben zes assets. Een ontbrekende secret bij signed policy, verkeerde key, onbekende boardrevision of niet-passende firmwarepolicy laat de releasejob falen; er is geen unsigned fallback. PR-CI krijgt de private key niet. De standaard bench-policy zonder secret blijft vijf expliciet unsigned assets produceren.

Het bestaande prototype ondersteunt:

```sh
uv run panel wifi update --release-bundle <downloaded-assets> --trusted-keys <pinned-public-policy.json> --board-revision <verified-revision>
```

De publieke policy moet vooraf vertrouwd zijn; haal hem niet zonder onafhankelijke controle uit dezelfde download als de firmware. Alle vereiste assets moeten aanwezig zijn. Een paneel moet signed-required en dezelfde boardrevision melden. Het hostprototype valt niet terug op de oude unsigned start wanneer signed preflight of de paneelcontrole faalt. Bestaande pairing/TLS-authenticatie blijft daarnaast nodig.

Dit is de huidige bench-CLI; deze levert de bytes aan en bevestigt de boot. Het paneel kan met deze implementatie nog niet zelfstandig een release downloaden of zonder host een kandidaatboot bevestigen. De toekomstige verantwoordelijkheid staat hieronder.

## Besluit: het paneel beheert zijn updates

Besloten op 2026-11-05: het paneel moet via wifi zelfstandig een ondertekende release kunnen ophalen, installeren en beoordelen. Alleen voeding, geconfigureerde wifi en bereik tot de updatebron zijn daarvoor nodig. Een Mac, NetLink, gekoppelde bedieningssessie of draaiende webserver is geen voorwaarde. Wifi blijft optioneel voor normale USB-bediening; zonder wifi levert een optionele host de firmwarebytes aan.

| Onderdeel | Verantwoordelijkheid in het doelontwerp |
| --- | --- |
| Paneelfirmware | Eén update-toestandsmachine, toelating/idle, releaseverificatie, download of ontvangst, slotkeuze, voortgang/uitkomst, kandidaatboot, lokale self-check, VALID en rollback |
| Bestaande webserver | Optioneel starten, status tonen en bytes via USB/wifi aanleveren; geen verplichte eigenaar van de updatepoging |
| Centrale aansturing | Optioneel gewenst versienummer en uitrolmoment aanbieden binnen het lokale toelatingsbeleid |
| Releaseworkflow | Dezelfde ondertekende manifests, autorisatie en firmware-assets produceren; nooit rechtstreeks een paneel flashen |

De eerste zelfstandige gebruikersroute is op het paneel: controleren op een update, versie/status tonen en installatie expliciet starten. Automatisch controleren of uitrollen is afzonderlijk beleid en wordt hiermee niet standaard aangezet. De huidige pairing is voor de host-benchroute; de toekomstige zelfstandige download mag geen gekoppelde host vereisen.

De downloadclient haalt eerst het begrensde manifest en de autorisatie op, verifieert de onafhankelijke releasehandtekening tegen de reeds ingebouwde publieke trust en controleert boardrevision, versie, protocol, layout, lengte en counter vóór flash wordt gewist of geschreven. De firmwarestream wordt begrensd en gehasht vóór activatie. HTTPS moet de serveridentiteit valideren; redirects, retrybudget, tijdslimieten en maximale downloadgrootte moeten begrensd zijn. Uitval van de bron mag geen unsigned fallback of onbeperkte herstartlus veroorzaken. De concrete bron, kanaalkeuze en eventuele toegangsverlening moeten nog worden uitgewerkt. Een private GitHub-repository maakt assets niet vanzelf bereikbaar voor een paneel; er wordt geen langlevend GitHub-token in firmware ingebouwd en een publieke mirror wordt niet impliciet ingericht. De gepubliceerde assets blijven de bron voor de distributie.

Dezelfde lokale toestandsmachine ontvangt bytes van een optionele USB-/wifi-host. Het paneel bewaakt één actieve poging, vereist idle bediening en blokkeert conflicterende acties tot afronding of veilig afbreken. Een tweede bron krijgt een busy-resultaat en kan een lopende poging niet overnemen. De webserver moet tijdens optionele aanlevering zijn eventloop vrijhouden, maar zijn beschikbaarheid bepaalt niet de lokale update-uitkomst.

Het paneel bewaart pogingidentiteit, geautoriseerde verwachte image, fase en uitkomst persistent. Na stroomverlies of een paneelrestart wordt de echte slot-/bootstatus vergeleken met die poging vóór een nieuwe poging wordt toegelaten. Een bestaand flashhandle overleeft geen reboot: hervatten of gecontroleerd opnieuw beginnen van het inactieve slot moet expliciet worden geïmplementeerd en getest. Bestaande instellingen en de laatst werkende image moeten behouden blijven.

Een nieuwe boot controleert lokaal de verwachte image en opstartgezondheid en bevestigt vervolgens zelf expliciet VALID. Een Mac, nieuwe hosthandshake of werkende webserver mag niet nodig zijn om een gezonde kandidaat te behouden. Lokale self-checks en netwerkbereikbaarheid zijn afzonderlijke signalen. Bij ongeldige image, self-checkfout of verlopen bevestigingstermijn blijft rollback gelden. De huidige hostgestuurde `ota_confirm`-route moet hiervoor nog worden aangepast; de signingbasis uit PR #32 levert dit gedrag niet. Een later verbonden host leest de opgeslagen uitkomst en maakt een verse handshake voor bediening, zonder de afgeronde installatie nog te hoeven bevestigen.

## Resterende acceptatie van #15

- Zelfstandige wifi-proef met alleen voeding en zonder Mac, NetLink of webserver: vanaf het paneel controleren, downloaden, installeren, herstarten, lokaal VALID bevestigen en resultaat tonen.
- Dezelfde verificatie en installatiepolicy bij zelfstandige downloads en optionele hostaanlevering; ongeldige handtekening, verkeerde hardware/protocol en conflicterende pogingen worden geweigerd.
- Netwerkonderbreking, bronuitval, stroomverlies, paneelrestart, self-checkfout en ontbrekende webserver leveren een begrensde, zichtbare uitkomst op; rollback en instellingenbehoud zijn fysiek aangetoond.
- Productietrust, bekende boardrevision, sleutelbeheer en bereikbare distributiebron zijn gecontroleerd ingericht. #14 blijft de fysieke full-image-/herstelgate; #9 is alleen relevant voor de optionele webserver-/USB-integratie.

## Rotatie en beperkingen

Bij geplande rotatie: begin met A, rol een met A getekende A+B-policy uit, bevestig de migratie en rol daarna een met B getekende B-policy uit waarin A verwijderd of revoked is. De hostpin wordt bewust met de verwachte kandidaatpolicy bijgewerkt; het draaiende paneel moet de signer reeds vertrouwen. Een releasecounter onder de ingebouwde floor wordt geweigerd. Die floor is geen automatisch opgeslagen hoogste geïnstalleerde versie: oudere geldige releases boven de floor blijven toegestaan.

Rollback kan een oudere keypolicy herstellen. Dit mechanisme levert geen permanente revocation, hardwarematige antirollback, expiry/freeze-bescherming, Secure Boot of bescherming tegen fysieke herprogrammering. Een gecompromitteerde enige signer kan zelf een verkeerde release of rotatie tekenen. Productiekey-eigenaarschap, veilige opslag, onafhankelijke recovery en beleidsacceptatie moeten vóór ingebruikname expliciet worden geregeld.

## Bewijs en open acceptatie

De tests gebruiken uitsluitend tijdelijke sleutels. Python-signatures worden met de echte, vastgepinde mbedTLS 2.28.4-bron uit het gebruikte SDK native geverifieerd; de daadwerkelijke `PanelOta`-handler draait met fake SDK-flashcalls. Tests controleren afwijzing vóór flash, geen unsigned bypass, ingetrokken keys, gewijzigde autorisatie, verkeerd board/protocol/layout/counter, formaatgrenzen, artifactmutatie en hervatten met uitsluitend dezelfde autorisatie. `scripts/prepare_crypto_tests.py` haalt de exacte bron met SHA-256-controle op en bouwt alleen de native testbibliotheek; productie gebruikt de PlatformIO/ESP-IDF-bibliotheek.

Compile- en native tests bewijzen nog geen cryptotiming/heapmarge op het display, de zelfstandige wifi-lifecycle, optionele USB-hostroute of fysieke herstelbaarheid. Er is voor deze wijziging geen paneel geflasht of productiekey aangemaakt, geïnstalleerd of gelezen. Zie [onderzoeksbronnen](signed-update-research.md) en [releaseprocedure](releases.md).
