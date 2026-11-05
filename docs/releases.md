# Firmwarecontroles en herleidbare releases

Onderdeel van #23. Firmware/protocol blijven in `netlink-control-panel`; de bestaande webserver-container is de consumer. Er komt geen panel-service-image of extra deploymentpad. Release Drafter beheert de releasenotities en draft. Bij publicatie bouwt de firmwareworkflow assets voor die bestaande release; er wordt geen firmware geïnstalleerd.

## Controles op PR en main

De workflowstructuur volgt `python-netlink` en `python-balena-cloud`:

| Workflow | Trigger en verantwoordelijkheid |
| --- | --- |
| `linting.yaml` — Linting | Push, PR en handmatig; aparte Ruff-, yamllint- en asset/preview-jobs |
| `tests.yaml` — Testing | Push, PR en handmatig; Python-job met firmwarebuild, alle host/native tests en commitgebonden candidate-artifacts |
| `release-drafter.yaml` — Release Drafter | Main en handmatig; standaardactie met de centrale organisatieconfiguratie |
| `release.yaml` — Release | `release.published`; één firmware-releasejob in de `release`-environment |

De jobs gebruiken `DEFAULT_PYTHON`, `ubuntu-latest`, setup-uv, expliciet `uv python install` en `uv sync --locked`, zoals de packageprojecten. Lint/test gebruiken uv-cache; de releasejob schakelt die uit. `contents: read` is de standaard; alleen de draft- en releasejobs krijgen de benodigde schrijfrechten. De Actions zijn op dezelfde commit-SHA’s gepind als de voorbeelden. De huidige firmwaretestbaseline is Python 3.14 met TLS-PSK; de runner gebruikt de actuele patchversie van die Pythonreeks.

De functionele controles blijven firmwaregericht: vaste Python-/PlatformIO-/libraryversies, immutable LILYGO-bronnen met automatische touchcontrollerflash uitgeschakeld, echte C++-protocol/UI-tests, previewsyntax en geschoonde artifacts. Ontbrekende compiler/ArduinoJson/TLS-PSK of overgeslagen tests leveren geen groene testjob op. `tests.yaml` uploadt een artifact `panel-<commit>` met 30 dagen bewaartermijn.

De generator legt de BASIC-lettertypelayout expliciet vast op macOS en Linux. PNG-referenties worden op identieke afmetingen en RGBA-pixels gecontroleerd; de embedded C++-arrays moeten byte voor byte gelijk blijven.

De bestaande lokale systeemtests blijven bruikbaar op een machine zonder alle CI-voorwaarden, maar `scripts/check_tests.py` accepteert geen skips.

Lokaal hetzelfde controlepad:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked yamllint .github .yamllint
node --check preview/app.js
uv run --locked python scripts/generate_demo_assets.py --check
uv run --locked python scripts/prepare_firmware.py
uv run --locked python scripts/prepare_crypto_tests.py
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
| `RELEASE_NOTES.md` | Bij een release: de Release Drafter-body van de bestaande gepubliceerde release; bij PR/main: een CI-candidatemelding |
| `authorization.json` | Alleen bij signed releases: afzonderlijke ECDSA P-256-autorisatierecord en handtekening |
| `SHA256SUMS` | SHA-256 van alle voorgaande bestanden, inclusief het manifest |

De ESP-imageheader, segmentchecksums, appended imagehash en board-/partitiemarker worden gecontroleerd. Zonder release moeten image, projectversie en fallbackheader overeenkomen. Bij een gepubliceerde release is de gevalideerde tag `v<semver>` leidend: dezelfde versie wordt via een compilerdefine in scherm, handshake en image-marker verwerkt en moet in de gebouwde image terugkomen. De bronbestanden worden niet herschreven. De releasenotities komen uit GitHub; er is geen aparte handmatige changelog of verplichte versiecommit per release. Losse artifacts kunnen met `sha256sum --check SHA256SUMS` op overdrachtscorruptie worden gecontroleerd.

Voor dezelfde broncommit, firmwarebytes en releasenotities zijn packaging, manifest en protocolarchive deterministisch, inclusief archivevolgorde, metadata en gzip-tijdstip. De workflow claimt geen bitidentieke ESP-builds tussen verschillende besturingssystemen/toolchains; de daadwerkelijk gebouwde image wordt altijd met zijn eigen digests vastgelegd. Hashes zijn geen authenticiteitsbewijs en vervangen geen releasehandtekening.

## Protocolgrens en webserver

`release/protocol-core.json` definieert pakketversie 1.0.0, toegestane symbols en uitgesloten serial-imports. Deze pakketversie is onafhankelijk van firmware 0.8.0 en wireprotocol v2. Het pakket bevat geen daemon, CLI, USB-opener of pySerial-import. De webserver blijft eigenaar van zijn SerialX-adapter, sessielifecycle en bestaande status-/commandolaag.

CI vergelijkt de gegenereerde bytes met de consumerselectie uit de gepinde webservercommit in dit contract. Het artifact bevat dezelfde `generated_sha256`-/`upstream_sha256`-grens die de bestaande webserver-vendoring controleert. Een test importeert het verpakte pakket en gebruikt de echte C++-firmwarehandler via een pseudo-terminal: handshake, read-only device-state, snapshot en geweigerde acties moeten werken. Een gewijzigde consumerdigest blokkeert packaging totdat pakketversie, contract en compatibiliteit bewust zijn beoordeeld.

Dit is een test van het protocolpakket en het vastgelegde consumercontract, geen volledige webserver-container-/fleettest. De private webserverrepository wordt niet met extra credentials vanuit PR-CI opgehaald. De webserver behoudt voorlopig zijn bestaande immutable broncommit en digestcontrole; overstappen op het releaseartifact vereist een eigen webserver-PR met commit/pakketversie/archivehash en bestaande consumer-/runtimechecks. De open webserver-PR’s en submodulepointers worden hier niet gewijzigd.

## Release Drafter en release-assets

`release-drafter.yaml` gebruikt dezelfde minimale job als `python-balena-cloud`: één Release Drafter-actie op main of een handmatige run, met de geërfde centrale categorieën en versie-resolver. Er is geen checkout, eigen versie-initialisatie of lokale kopie van de configuratie. v0.8.0 is gepubliceerd; volgende drafts volgen de bestaande releasehistorie en PR-labels. Controleer vóór publicatie de voorgestelde versie en notities.

De maintainer controleert en publiceert de draft in GitHub. `release.yaml` start op `release.published`, zoals de package-releaseworkflow. De releasejob draait in de `release`-environment en checkt de **exacte releasetag** uit. Hij valideert main-ancestry en de versie, stelt de firmwareversie voor de build in, bouwt de image en draait de host/native tests. Er is geen tweede publicatie-/uploadjob en er is geen artifactoverdracht tussen workflows nodig.

De releasebody uit het publicatie-event wordt als `RELEASE_NOTES.md` meegenomen. De job verpakt de image, controleert `SHA256SUMS` en uploadt de vijf bench-assets of zes signed assets met `svenstaro/upload-release-action` naar de bestaande release-ID. De bestaande Release Drafter-titel en -body blijven behouden. Assets worden niet overschreven; dubbele namen laten de upload falen. Bij een gedeeltelijk mislukte upload blijven mogelijk assets staan; controleer die vóór een nieuwe poging. Een release heeft pas bruikbare firmware-assets als de releasejob geslaagd is. PR-/testworkflows maken geen tags of releases aan.

De standaardpolicy produceert expliciet **unsigned bench-artifacts**. De optionele ondertekening en verificatie op host/paneel staan in [ondertekende updates](signed-updates.md). Een signed release vereist vooraf gereviewde publieke trust, bekende boardrevision en een private secret in environment `release`; bij ontbrekende of ongeldige configuratie faalt de job. PR-CI gebruikt uitsluitend tijdelijke testsleutels. Productiekeyprovisioning en de zelfstandige wifi-lifecycle op het paneel blijven binnen #15 open; webserverintegratie voor updates valt buiten deze scope. Een Release Drafter-draft, gepubliceerde release of groene CI is geen fysieke installatie, OTA-acceptatie of toestemming voor beweging.

De bestaande fleet-first route blijft leidend voor de NetLink-hostsoftware: een reviewbare consumerpin gaat via de webserver-image naar NetLink develop/dev, acceptance en stable production. Paneelfirmware krijgt daarnaast zelfstandig downloaden en installeren via wifi, zonder verplichte webserver of Balena-deploy. Het paneel gebruikt de ondertekende release-assets en zijn lokale verificatiepolicy. De concrete distributiebron, bereikbaarheid en kanaalkeuze voor het paneel blijven nog uit te werken binnen #15; een private GitHub-release is niet vanzelf toegankelijk vanaf het paneel. Deze releaseworkflow bouwt en publiceert assets en start geen installatie op hardware. Adoptie van protocol-core-artifacts in de webserver en die rolloutacceptatie blijven afzonderlijk vervolgwerk binnen #23; een updatefunctie in de webserver hoort niet bij #15.
