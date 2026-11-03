# Design QA: uitgebreide displaydemo 0.5.2

final result: passed

De derde PDF is als native demo op het fysieke LILYGO-display geïnstalleerd. Er zijn geen open P0/P1/P2-afwijkingen gevonden in de vergeleken toestanden. De fysieke bediening blijft ter beoordeling aan de gebruiker; er wordt geen camerafoto of echte NetLink-aansturing geclaimd.

## Bron en normalisatie

- Source visual truth: `docs/design/netlink-bedienpaneel.pdf`, 17 pagina's uit de derde aangeleverde PDF.
- Bronnen: 1920 × 540 rasterpixels per pagina in 480 × 135 pt; referenties `reference-01.png` t/m `reference-17.png` genormaliseerd naar 640 × 180.
- Native implementatie: dezelfde C++-renderer als de firmware, 640 × 180 RGB565, density 1:1, geen browser- of hardwarebezel. Dit is de viewport van het embedded apparaat.
- Full-view paired evidence: [schermen 1–8](docs/design/evidence/native-01-08.png) en [schermen 9–17](docs/design/evidence/native-09-17.png); bron en implementatie zijn in dezelfde beelden naast elkaar vergeleken.
- Focused evidence: `scene-12.png` toonde een dubbele percentagewaarde. `update-corrected-comparison.png` is na de fix geopend en vergeleken: één waarde op dezelfde verticale positie als de bron.
- Fysieke implementatie: [Paneel op het apparaat](docs/design/evidence/device-settings-0.5.0.png) toont bronpagina 8 naast een atomische framebufferopname van het echte display. Dit beeld is geopend en vergeleken. Er is een vaste snapshot uitgelezen zonder UI-acties te injecteren; de live pagina ging ondertussen van Paneel naar Ruststand, zonder een gemengd beeld te veroorzaken.

## Vergelijkingsgeschiedenis en bevindingen

- [Opgelost P2] Updatescherm bevatte de statische 64% plus de nieuwe dynamische waarde. De hele oorspronkelijke percentageregio wordt nu gewist en precies één nieuwe waarde wordt uitgelijnd met de voortgangsbalk. Na de fix is opnieuw gerenderd en visueel vergeleken.
- [Opgelost P2] De eerdere framebufferstream kon bij gelijktijdige bediening een gemengd beeld geven. Vanaf 0.5.0 wordt eerst een volledige kopie in PSRAM gemaakt; iedere chunk heeft een vaste snapshot-id en scenenaam. De echte USB-opname bevestigde coherentie terwijl de live toestand wijzigde.
- [P3] Het oorspronkelijke font is niet als bruikbaar font in de raster-PDF aanwezig. Dynamische waarden gebruiken lokaal gerasterde Inter met kleine verschillen in glyphbreedte/optisch gewicht. Dit is expliciet geen claim van exacte fontidentiteit.

## Vijf fidelity-oppervlakken

- Typografie: vaste brontekst en pictogrammen komen uit het ontwerp; veranderlijke waarden gebruiken passende Inter-grootten en gewichten. Geen zichtbare afkapping of onbedoelde regelafbreking in de vergeleken pagina's.
- Layout: grotere pijlen, tweerijenmenu, slider- en instellingenregio's, foutacties en rustbeeld volgen de bron. De rotatie is een volledige 180-graden-pixeltransformatie met corresponderende touchtransformatie.
- Kleuren: RGB565 en beperkt palette geven geringe verwachte afronding. Groen/oranje semantische meldingen behouden een ruimer palette. De bron en de echte Paneel-opname hebben dezelfde visuele hiërarchie en kleurverdeling.
- Assets: de 17 schermen en iconen zijn ontleend aan de aangeleverde rasterbron. Geen vervangende handgetekende webiconen of fictieve fotografie. Bron en eerdere ontwerpset zijn in de repository bewaard.
- Copy: labels en meldingen volgen de PDF. Tijdens een werkelijk onbevestigde nieuwe boot staat er Nieuwe firmware controleren; dat is een bewuste inhoudelijke afwijking om geen bevestigde update te suggereren. De fout-/afstelscenario's blijven lokale demo's.

## Verificatie

Alle 46 lokale regressietests, lint en formattering slagen. De echte native klasse is uitgebreid getest op 17 framebuffers met canaries, nieuwe menu-hitvlakken, omgekeerde pixels, omgekeerde touchcoördinaten, slapen/wakker worden, foutknoppen en begrensd afstellen/stoppen op release. De bestaande tests voor doelhoogte kiezen, tik/hold/release, bevestigen/annuleren, presets en 62–127 cm blijven slagen.

0.5.0 is via USB in het geverifieerde actieve applicatieslot geschreven; hashverificatie geslaagd. Bootversie, imagehash, VALID, display/touch-startup-self-check, min/max en snapshot-id zijn op het echte apparaat teruggelezen. De eigenlijke fysieke touch-calibratie en beoordeling van het gevoel blijven gebruikersacceptatie; de USB-verificatie injecteerde geen schermwissels of beweging.

## Afgerond

1. Alle 17 native schermen met de nieuwste PDF vergeleken en de percentageafwijking opgelost.
2. Firmware gebouwd en via de gekozen kabelroute geïnstalleerd, zonder NVS/bootloader/partitiewijziging.
3. Actuele versie en consistente schermuitlezing geverifieerd op het fysieke paneel.

De browserkopie is niet de primaire implementatie van deze revisie en heeft nog de eerdere ontwerpset. De oudere QA is bewaard onder `docs/design/v2/design-qa.md`.

## PR-controle 0.5.2

De toegevoegde versieaanduiding is native visueel gecontroleerd: [Paneel met firmwareversie](docs/design/evidence/version-label-0.5.1.png). Firmware 0.5.1 is via USB geïnstalleerd en versie, imagehash, VALID en startup-self-check zijn op het apparaat bevestigd. In 0.5.2 is ook slepen op de helderheidsslider bij 180°-rotatie hersteld, met een regressietest die vóór de fix faalde. Deze laatste correctie is lokaal getest en gebouwd; 0.5.2 is nog niet fysiek geïnstalleerd. De schermafbeelding toont daarom bewust de eerder gecontroleerde 0.5.1.
