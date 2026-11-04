# Read-only status — native QA

Resultaat: passed voor software/native weergave; geen fysieke NetLink-acceptatie.

Dezelfde C++-renderer als de firmware is gecompileerd en op 640 × 180 gerenderd. De synthetische metingen komen uit de testfixture, niet uit een aangesloten bureau. Alle vijf beelden zijn geopend en gecontroleerd:

- [Gemeten hoogte](design/evidence/read-only/height-current.png): 108,6 cm, expliciet Alleen-lezen; pijlen/presets geven geen opdrachten of simulatie.
- [Laatst bekende hoogte](design/evidence/read-only/height-last-known.png): dezelfde gemeten waarde met tekst LAATST BEKEND, zonder fictieve actualiteitsclaim.
- [Onbekende hoogte](design/evidence/read-only/height-unknown.png): streepjes, geen 0/74-cm-default of oude glyphresten.
- [Monitorstatus](design/evidence/read-only/monitor-current.png): 83%, Uit en USB-C uit de fixture; controls zijn niet actief.
- [Onbekende monitorstatus](design/evidence/read-only/monitor-unknown.png): streepjes/Onbekend, geen fictieve helderheid/power/ingang.

Een gevonden glyphrest bij onbekende hoogte is verwijderd door de hele oorspronkelijke waardezone te wissen. Daarna is opnieuw gerenderd en het onbekende beeld opnieuw geopend. Typografie/kleuren volgen de bestaande Inter/RGB565-weergave; de aangeleverde referentieontwerpen zijn niet gewijzigd.

De native tests controleren daarnaast de echte protocolvalidatie, vervallen datalease, onbekende status, niet-klemmen van waarnemingen op commandogrenzen en geblokkeerde read-only aanrakingen. De aparte webserverproef dekt de Waveshare met vaste HDMI1 en een ontbrekende verwachte Dell. Firmware 0.7.0 is gebouwd maar niet fysiek geïnstalleerd; werking en leesbaarheid op een echte NetLink/werkplek volgen na expliciete installatie.
