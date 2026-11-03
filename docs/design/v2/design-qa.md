# Design QA: zelfstandige LILYGO-demo

final result: passed

De native visuele vergelijking en de uiteindelijke kabelinstallatie van 0.4.3 zijn voltooid. Geen open P0/P1/P2-afwijkingen bekend in de beoordeelde toestanden. De apparaatcontrole bevestigt doelbewerking met tikken/vasthouden, stabiel doel na release en onveranderde huidige hoogte vóór bevestigen. De gebruiker beoordeelt de fysieke look-and-feel.

## Bron en normalisatie

- Source visual truth: `docs/design/v2/netlink-bedienpaneel.pdf`, de bijgewerkte tweede PDF met acht schermen.
- Bronbeelden: 1920 × 540 rasterpixels per pagina, in een PDF van 480 × 135 pt. `docs/design/v2/reference-01.png` t/m `reference-08.png` zijn genormaliseerd naar 640 × 180.
- Implementatie: dezelfde native C++-renderer als in de firmware, framebuffer 640 × 180 RGB565, zonder browser- of apparaatbezel. Dit is de relevante viewport voor dit embedded display; de browserkopie is niet de primaire oplevering.
- Full-view paired evidence: `artifacts/design-native/comparison.png` en `comparison-v2.png`. De bron en native renderer staan in één beeld naast elkaar per toestand.
- Focused evidence: `artifacts/design-native/scene-1.png`, `scene-6.png` en `offline-fixed.png`; de typografie, numerieke waarden, knoplabels en sliderregio zijn op native schaal geopend en bekeken.
- Echte hardwareframebuffers van 0.4.0: `artifacts/display-demo/screen-01.ppm` t/m `screen-04.ppm`. Dit zijn uitgelezen schermbuffers, geen camerafoto's. De volgende capture is gestopt omdat een echte aanraking de toestand wijzigde; een incoherent beeld is niet als bewijs opgeslagen.

## Bevindingen en iteraties

- [Opgelost P1] De eerste palettecompressie gaf roze lichte vlakken en zichtbare achtergrondblokken. De compressie is gewijzigd naar median-cut zonder dithering; de tweede gepaarde vergelijking en afzonderlijke native captures bevestigen de correctie.
- [Opgelost P2] De zeldzame oranje offlinekleur ging bij een te klein palette verloren. De offline-scène gebruikt 256 kleuren; `offline-fixed.png` is geopend en heeft de oranje melding terug.
- [Opgelost P2] De Monitor-terugknop moet volgens de bron naar Bureau. De native interactie en browserkopie zijn gelijkgetrokken met het zichtbare label.
- [Opgelost P1] De aanvankelijke 4-cm-stap en daarna de directe manual-move-interpretatie waren niet de gewenste bediening. In de klaarstaande 0.4.3 veranderen een korte tik en vasthouden alleen het doel; release stopt de doelbewerking. Bevestigen is de enige ingang naar een beweging. De gerichte regressietest is eerst rood en na correctie groen geworden. Deze correctie staat nu als 0.4.3 op het apparaat en is via de gedeelde UI-handler gecontroleerd.

## Vijf fidelity-oppervlakken

- Fonts/typografie: oorspronkelijke UI is raster met een onzichtbare OCR-fontlaag. Dynamische tekst gebruikt lokaal gerasterde Inter; hiërarchie, grootten en baselines zijn afgestemd op de bron. Kleine glyphbreedteverschillen blijven P3; geen claim van exacte fontidentiteit.
- Spacing/layout: vaste 640 × 180-geometrie, zijvlakken, onderste knoppen, menu-indeling en instellingen zijn overgenomen; geen afgesneden controls in de native captures.
- Kleuren/tokens: bronkleuren, RGB565-uitvoer en offline-semantie zijn visueel gecontroleerd na compressiecorrecties. RGB565 en antialiasing leveren beperkte, verwachte kleurafronding op.
- Assets: originele schermillustraties/iconen uit de aangeleverde PDF; geen getekende vervangende pictogrammen. Bitmap- en fontassets worden reproduceerbaar gegenereerd uit repo-lokale bronbestanden.
- Copy: huidige/gekozen hoogte, presets, bevestigen/annuleren, stop, menu's en offline-status volgen de bron. Heldere demosemantiek staat in de projectdocumentatie; geen echte apparaatcommando's.

## Bediening en verificatie

De volledige lokale suite van 46 tests slaagde vóór de laatste bedieningsverduidelijking. Daarna is de gewijzigde echte native UI-toestandsmachine opnieuw gericht getest: korte tik +1 cm, herhalen tijdens hold, huidige hoogte onveranderd tijdens doelbewerking, bevriezen bij release, annuleren, bevestigen en stop, plus de overige UI-controles. De actuele volledige suite van 46 tests slaagt, inclusief korte tik, hold/release, presets en bevestigde bewegingen bij de grenzen 62 en 127 cm. Firmware 0.4.3 bouwt succesvol en gebruikt minder dan de helft van het applicatieslot. Lint en formattering slagen.

De browserkopie heeft een syntaxcheck en is eerder in de ingebouwde browser gerenderd; er wordt geen volledige browser-QA van de laatste interactievariant geclaimd. De kabelinstallatie is nu voltooid; versie 0.4.3, imagehash, VALID en startup-self-check zijn teruggelezen. De fysieke gebruiker kan het gecorrigeerde gedrag nu zelf beoordelen.

## Afgeronde eindcontrole

1. Dezelfde fysieke ESP32-S3 geïdentificeerd, actieve applicatieslot gecontroleerd en 0.4.3 via USB geïnstalleerd; flashhash geverifieerd.
2. Bootversie/hash en doel versus huidige hoogte op het apparaat gecontroleerd via USB, met één korte donkere instelcontrole en zonder automatische bewegingsdemo.
3. Het display op de rustige beginstand achtergelaten voor de gebruiker.


Actuele paired evidence: `artifacts/design-0.4.3-native/comparison.png` bevat bron en actuele native renderer voor Bureau en Bevestigen op dezelfde 640 × 180-schaal; dit beeld is geopend en vergeleken. De actuele native renderer heeft ook de acht referentiescènes opnieuw gerenderd. De kleine fontbreedte- en RGB565-verschillen blijven P3. De ruwe streaming-framebufferopname in `artifacts/display-0.4.3/comparison.png` heeft een gemengde bovenstrook en wordt daarom niet als coherente visuele QA-capture gebruikt; de framebuffer-API is geen atomische snapshot bij gelijktijdige UI-invoer. Dit verandert de geslaagde onafhankelijke boot- en interactieverificatie in `verification.json` niet. Er wordt geen fysieke camerafoto geclaimd.
