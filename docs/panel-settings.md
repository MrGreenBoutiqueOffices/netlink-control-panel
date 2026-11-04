# Blijvende lokale paneelinstellingen

Onderdeel van issue #12. Bronversie 0.8.0 bewaart rotatie, paneelhelderheid en dimtijd. Dit is geen installatie- of hardwareacceptatie en implementeert nog geen beheerde configuratiewrites.

## Schema en opslag

Schema 1 bevat `brightness` (integer 10–100), `rotated` (boolean), `dim_minutes` (0, 1, 2 of 5) en een monotone 32-bits `revision`. Defaults zijn 100%, niet gedraaid en 1 minuut; ontbrekende opslag heeft revisie 0. Wifi-credentials, bureaupresets, doelhoogte en echte apparaatstatus worden niet in deze configuratie bewaard. Bureaupresets blijven uitsluitend tijdelijke demo-instellingen; er worden geen persoonlijke/controllerpresets beheerd.

De eigen NVS-namespace `panel-ui` heeft twee vaste blobs `ui0`/`ui1`. Een record van 20 bytes bevat magic `NP`, schemaversie, little-endian revisie, waarden, nul-reservebytes en een FNV-1a-integriteitscontrole. Deze checksum detecteert beschadiging; het is geen cryptografische handtekening. Een write vervangt steeds het andere slot via de atomische NVS-blobwrite en wordt teruggelezen voor bevestiging. Pas daarna worden de opgeslagen waarden en revisie in RAM toegepast. De voorafgaande geldige configuratie blijft beschikbaar. Geen erase of wijziging van de wifi-namespace.

Bij boot wint het geldige schema-1-record met de hoogste revisie. Een beschadigd, afgebroken of ongeldig record wordt overgeslagen; zonder geldig record worden defaults gebruikt. Er bestaat geen eerder opgeslagen UI-schema om te migreren: vóór 0.8.0 leefden deze instellingen alleen in RAM. Een toekomstige schemaversie met herkenbare magic blokkeert writes vanuit deze oudere firmware; die gebruikt de vorige leesbare configuratie of defaults zonder de nieuwe configuratie stilzwijgend te overschrijven. Een volgende schemawijziging moet een expliciete migratie met tests toevoegen. Bij revisie-overflow worden wijzigingen geweigerd.

## Toepassing en eigenaarschap

Alleen een fysieke touchgesture kan opslag starten. De UI previewt een slider tijdens slepen; loslaten schrijft maximaal één record. Ongewijzigde waarden schrijven niets. Rotatie geldt voor zowel de complete framebuffer als touchcoördinaten. Dimtijd 0 schakelt de timer uit. De eerste aanraking na ruststand wekt alleen; zij verandert geen instelling en schrijft niets. Gewone navigatie en lokale demo-reset behouden de paneelinstellingen. Expliciete bench-scenes blijven voorspelbare tijdelijke voorbeelden en schrijven geen NVS.

Bij een opslagfout herstelt de UI direct de vorige opgeslagen configuratie. De fout verschijnt als `write_failed: true` in status; er wordt geen geslaagde nieuwe revisie gerapporteerd. Een volgende geslaagde gewijzigde opslag wist de fout. Als een complete write wel is gelukt maar de verificatie niet kan worden gelezen, blijft de huidige runtime op de vorige configuratie; na herstart kan het nieuwe volledig geldige record worden gekozen.

De lokale gebruiker is de enige huidige schrijver. Er is geen managed-configcapability of `config.set`: zulke verzoeken blijven `unsupported_message` en krijgen geen write-/bewegingsrechten. Zo kan een host geen lokale wijziging overschrijven. Een latere beheerde adapter vereist expliciete autorisatie en conflictcontrole op de verwachte opgeslagen revisie; die synchronisatie is resterend werk van #12. Credentials verschijnen niet in de UI-configuratiestatus.

## Status

De handshake adverteert aanvullend `panel.config.status.v1`. Een `state.get` bevat optioneel `state.panel_config`:

```json
{"schema":1,"revision":3,"brightness":35,"rotated":true,"dim_minutes":5,"writable":true,"write_failed":false}
```

Dit is de opgeslagen configuratie, geen wijzigingsopdracht. Een actieve drag heeft nog geen opgeslagen revisie en kan tijdelijk een andere previewwaarde tonen. Een oude host kan dit optionele statusveld negeren. De bestaande USB/wifi-benchstatus bevat hetzelfde `panel_config`-object. Revisie blijft over reboot bestaan en staat los van de status- en device-state-revisies per sessie.

## Verificatie en resterende acceptatie

`tests/test_panel_settings.py` compileert de echte C++-journal en UI. De test herstart de journal, onderbreekt writes op alle bytegrenzen, beschadigt ieder recordbyte, controleert defaults/validatie/future-schema/read-backfout en test gedraaide touch, dimmen, wake-only en behoud bij navigatie/reset. De bestaande volledige host-/C++-suite en firmwarebuild blijven van toepassing.

Nog fysiek te doen: meerdere lokale wijzigingen met herstarts en stroomonderbreking; gedraaide touch; dim/wake; unavailable/full NVS; beeld bij meerdere helderheidsniveaus. Helderheid schaalt op dit moment gerenderde pixels, niet bewezen de fysieke backlight. Er wordt geen backlight-/vermogensclaim gemaakt. Issue #12 blijft open voor hardwareacceptatie en geautoriseerde managed-configsynchronisatie.

## Pijlfeedback in dezelfde firmware

De Confirm-basisafbeelding bevatte een ingekleurde pijl. Die kleur bleef daardoor na een enkele tik staan, hoewel de aanraking al voorbij was. De renderer tekent nu standaard neutrale pijlen en past de drukkleur alleen toe zolang een geldige pijlgesture actief is. Loslaten, de knop verlaten of onderbreken herstelt de normale knopkleur; de geselecteerde hoogte blijft bewaard voor bevestiging. Presetselectie laat geen pijl ingedrukt lijken.

`tests/test_arrow_feedback.py` reproduceerde eerst het kleurverschil na loslaten en dekt nu omhoog/omlaag, tik, hold/release, uit de knop slepen, busy, presetselectie en rotatie. De vergelijking gebruikt de echte firmwarepixels. Dit is softwarebewijs, geen nieuwe fysieke installatie.

Native renders van dezelfde firmwareklasse met synthetische demohoogte, geen hardwarefoto’s:

| Tijdens aanraken | Na loslaten |
| --- | --- |
| ![Pijl ingedrukt](design/evidence/panel-settings/arrow-held.png) | ![Pijl losgelaten](design/evidence/panel-settings/arrow-released.png) |
