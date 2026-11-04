# Firmwarecontroles en herleidbare releases

Onderdeel van #23. Firmware/protocol blijven in `netlink-control-panel`; de bestaande webserver-container is de consumer. Er komt geen panel-service-image of extra deploymentpad. Deze workflow bouwt en publiceert reviewbare artifacts, en installeert geen firmware.

## Controles op PR en main

`.github/workflows/firmware.yml` draait op PR’s, main, versietags en handmatige workflowstart. De verify-job heeft uitsluitend leesrechten en voert uit:

1. `uv sync --locked --group dev`: de exacte Pythonpackages uit `uv.lock`, met vaste Ruff/PlatformIO/Pillow/PyMuPDF-versies.
2. Ruff lint/format, Node-syntaxcontrole van de preview en niet-mutating regeneratie van de PDF/font-assets.
3. Voorbereiding van de immutable LILYGO-revisie met uitgeschakelde automatische touchcontrollerflash; firmwarebuild met vaste platform/library/framework/toolversies.
4. Alle Python- en native C++-tests. Een ontbrekende compiler, ArduinoJson-headers of TLS-PSK-capability mag niet in een groene CI met overgeslagen tests eindigen.
5. Packaging en contractcontrole van de firmware en het protocolpakket, gevolgd door een commitgebonden GitHub Actions-artifact `panel-<commit>` (30 dagen beschikbaar).

GitHub Actions zijn op commit-SHA gepind; uv, Python en Node hebben vaste versies. De runner is Ubuntu 24.04. De bestaande lokale systeemtests blijven bruikbaar op een machine zonder alle CI-voorwaarden, maar `scripts/check_tests.py` accepteert geen skips.

Lokaal hetzelfde controlepad:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
node --check preview/app.js
uv run --locked python scripts/generate_demo_assets.py --check
uv run --locked python scripts/prepare_firmware.py
uv run --locked pio run --project-dir firmware
uv run --locked python scripts/check_tests.py
uv run --locked python scripts/release_artifacts.py --output artifacts/candidate
```

De uitvoermap moet leeg zijn; de packaging-CLI weigert wijzigingen aan tracked bronbestanden. Bouw altijd opnieuw uit dezelfde schone checkout. Een bestaand bin-bestand met dezelfde versie bewijst op zichzelf niet uit welke commit het gebouwd is. De CI bouwt en verpakt daarom in dezelfde job, zonder een eerder firmwarebuildresultaat te cachen.

## Artifacts

| Bestand | Inhoud |
| --- | --- |
| `firmware.bin` | Gevalideerde ESP32-S3-applicatie; geen merged-flash, bootloader, partities of credentials |
| `manifest.json` | Bronrepo/commit/tag, firmwareversie, bestand- en imagehash, profiel/slotlimiet, protocol-/boardcompatibiliteit, inputdigests, artifactdigests en ondertekeningsstatus |
| `protocol-core.tar.gz` | Afgebakende versie van `protocol.py` en geselecteerde transportonafhankelijke hostsymbolen, met provenance/digests |
| `CHANGELOG.md` | Alleen de notities voor deze firmwareversie |
| `SHA256SUMS` | SHA-256 van alle voorgaande bestanden, inclusief het manifest |

De ESP-imageheader, segmentchecksums, appended imagehash, board-/partitiemarker, projectversie en firmwareheader worden gecontroleerd. Een tag moet exact `v<versie>` zijn. De versie moet een eigen changelogsectie hebben. Losse artifacts kunnen met `sha256sum --check SHA256SUMS` op overdrachtscorruptie worden gecontroleerd.

Voor dezelfde broncommit en dezelfde firmwarebytes zijn packaging, manifest en protocolarchive deterministisch, inclusief archivevolgorde, metadata en gzip-tijdstip. De workflow claimt geen bitidentieke ESP-builds tussen verschillende besturingssystemen/toolchains; de daadwerkelijk gebouwde image wordt altijd met zijn eigen digests vastgelegd. Hashes zijn geen authenticiteitsbewijs en vervangen geen releasehandtekening.

## Protocolgrens en webserver

`release/protocol-core.json` definieert pakketversie 1.0.0, toegestane symbols en uitgesloten serial-imports. Deze pakketversie is onafhankelijk van firmware 0.8.0 en wireprotocol v2. Het pakket bevat geen daemon, CLI, USB-opener of pySerial-import. De webserver blijft eigenaar van zijn SerialX-adapter, sessielifecycle en bestaande status-/commandolaag.

CI vergelijkt de gegenereerde bytes met de consumerselectie uit de gepinde webservercommit in dit contract. Het artifact bevat dezelfde `generated_sha256`-/`upstream_sha256`-grens die de bestaande webserver-vendoring controleert. Een test importeert het verpakte pakket en gebruikt de echte C++-firmwarehandler via een pseudo-terminal: handshake, read-only device-state, snapshot en geweigerde acties moeten werken. Een gewijzigde consumerdigest blokkeert packaging totdat pakketversie, contract en compatibiliteit bewust zijn beoordeeld.

Dit is een test van het protocolpakket en het vastgelegde consumercontract, geen volledige webserver-container-/fleettest. De private webserverrepository wordt niet met extra credentials vanuit PR-CI opgehaald. De webserver behoudt voorlopig zijn bestaande immutable broncommit en digestcontrole; overstappen op het releaseartifact vereist een eigen webserver-PR met commit/pakketversie/archivehash en bestaande consumer-/runtimechecks. De open webserver-PR’s en submodulepointers worden hier niet gewijzigd.

## Draftrelease en deployment

Na merge kan een maintainer bewust een tag `v<versie>` op een commit uit main pushen. Alle verify-stappen draaien opnieuw. De tag moet op main liggen en overeenkomen met de image/header/projectversie. Pas daarna downloadt een aparte job met `contents: write` het artifact, controleert `SHA256SUMS` en maakt een **draft-release** met de vijf bestanden. Bestaande releases worden niet overschreven. De maintainer controleert en publiceert de draft zelf; deze wijziging maakt geen tag of release aan.

De artifacts zijn expliciet **unsigned**. Er is geen signingkey in PR-CI. Ondertekening en verifier/keyprovisioning horen bij #15 en moeten gereed zijn voordat een beheerde updater zulke artifacts als vertrouwd kan installeren. Een draft/published release of groene CI is geen fysieke installatie, OTA-acceptatie of toestemming voor beweging.

De bestaande fleet-first route blijft leidend: een reviewbare consumerpin gaat via de webserver-image naar NetLink develop/dev, acceptance en stable production. Alleen de agent/webserverrollen uit de bestaande architectuur worden gebruikt; er is geen rechtstreeks firmwaredeploy vanuit deze workflow. Artifactadoptie in de webserver en die rolloutacceptatie blijven open binnen #23/#15, naast de afzonderlijke hardware-/OTA-issues.
