# Ondertekende paneelupdates: onderzoek voor #15

Onderzocht op 2026-11-05. Dit document legt het bronnenonderzoek vóór implementatie vast; de actuele implementatie en resterende grenzen staan in [ondertekende updates](signed-updates.md). Het onderzoek zelf heeft geen productiesleutels of hardware gewijzigd.

## Conclusie

Gebruik voor de bestaande toolchain **ECDSA P-256 met SHA-256**, een ingebouwde publieke sleutelset en een kleine afzonderlijk ondertekende OTA-autorisatierecord. Laat zowel de host als het paneel verifiëren. Het paneel moet dit doen vóór `anchorRunning()` en `esp_ota_begin()`. Behoud vervolgens alle bestaande image-, hash-, slot-, rollback- en opstartcontroles. Ondertekende updates zijn hier applicatiebeleid: ze leveren geen Secure Boot, fysieke bescherming, permanente revocation of hardwarematige anti-rollback.

## Vastgestelde uitgangssituatie

De repository pint in `firmware/platformio.ini` Arduino ESP32 package `3.20014.231204` en ArduinoJson `6.21.5`. Espressif bevestigt dat Arduino ESP32 2.0.14 op ESP-IDF 4.4.6 is gebaseerd. De geïnstalleerde package-identiteit komt overeen met die pin. [Arduino-release](https://github.com/espressif/arduino-esp32/releases/tag/2.0.14)

Lokale broncontrole: `firmware/src/panel_ota.cpp` accepteert nu door de afzender opgegeven SHA-256, versie en profiel, maar geen releasehandtekening. `scripts/release_artifacts.py` produceert expliciet een unsigned manifest met `board_revision: unverified`; `SHA256SUMS` is integriteitsmetadata, geen trust anchor. `host/netlink_panel/ota.py` inspecteert ruwe imagebytes en stuurt die metadata naar `ota_begin`. Het nieuwe managed pad moet daardoor een aparte ingang krijgen die een geverifieerde releasebundle vereist.

`host/netlink_panel/protocol.py` begrenst JSON-frames op 1024 bytes exclusief newline; `firmware/src/frame_writer.h` heeft dezelfde grens. `firmware/src/ota_policy.h` en de host gebruiken chunks van 512 bytes, oftewel maximaal 684 base64tekens. Het bestaande `StaticJsonDocument<1536>` in de ontvangstroute is geen bewijs dat ieder nieuw 1024-byte frame ook in de JSON-arena past. Meet beide grenzen afzonderlijk.

## Exacte SDK en crypto-API

De ESP-IDF 4.4.6 GitHub tree verwijst voor mbedTLS naar commit `1d7033af30e20ccb2a0c0a114d3a08e372430f34`; de header identificeert mbedTLS 2.28.4. Dit is ook de versie in de lokaal geïnstalleerde ESP32-S3 headers. [Exacte submoduleverwijzing](https://api.github.com/repos/espressif/esp-idf/contents/components/mbedtls/mbedtls?ref=v4.4.6), [versieheader](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/version.h)

De Arduino 2.0.14 ESP32-S3 `qio_opi` configuratie schakelt `CONFIG_MBEDTLS_ECDSA_C`, `CONFIG_MBEDTLS_ECP_DP_SECP256R1_ENABLED` en PEM parsing in. Deze waarden zijn ook lokaal aangetroffen. Dit onderbouwt implementatie met de aanwezige bibliotheek; voeg compile-time guards en een compile/link-proef voor de werkelijk gebruikte boardconfig toe. Verander niet alleen een sdkconfig-macro bij een vooraf gebouwde library. [Gepinde sdkconfig](https://github.com/espressif/arduino-esp32/blob/2.0.14/tools/sdk/esp32s3/qio_opi/include/sdkconfig.h)

Een geschikte paneelroute is `mbedtls_pk_init`, `mbedtls_pk_parse_public_key`, expliciete controle van EC-keytype en `MBEDTLS_ECP_DP_SECP256R1`, daarna SHA-256 van de exacte payloadbytes en `mbedtls_pk_verify(&ctx, MBEDTLS_MD_SHA256, digest, 32, signature, signature_len)`. Accepteer uitsluitend returnwaarde nul en geef resources op alle paden vrij. Het verify-argument is al een digest; hash die niet nog eens. [Exacte pk.h API](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/pk.h)

Gebruik publieke sleutels als DER SubjectPublicKeyInfo, of PEM `PUBLIC KEY` rond dezelfde structuur. DER-lengte is exact; bij PEM telt voor `mbedtls_pk_parse_public_key` de afsluitende NUL mee. Vertrouw uitsluitend geprovisioneerde keybytes: een meegestuurde public key of key-ID verleent geen vertrouwen. De genoemde header beschrijft ook de keytypecontrole; een parser kan meerdere keytypes ondersteunen.

ECDSA-signatures zijn ASN.1 `SEQUENCE(INTEGER r, INTEGER s)`, niet de vaste 64-byte `r || s` vorm. P-256 heeft maximaal 72 DER-bytes, dus maximaal 96 base64tekens. De exacte mbedTLS implementatie controleert de sequencegrens en twee integers en retourneert fouten bij achterblijvende bytes. Dit is geen algemene garantie van canonieke DER voor alle denkbare BER-varianten; specificeer canonical DER en test negatieve/non-minimale integers, truncatie en trailing bytes expliciet, zo nodig met een kleine strikte encodingcheck vóór de library. [Exacte ECDSA-parser](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/library/ecdsa.c)

Ed25519 vraagt in deze SDK een andere implementatie of toolchainwijziging. De 2.28.4 ECP-/PK-interfaces hebben geen EdDSA/Ed25519-keytype; de aanwezige Curve25519 is een Montgomerycurve en geen Ed25519-signature-API. De ECDSA-bron sluit Curve25519 ook expliciet uit. Daarom is P-256 de kleinste wijziging binnen de huidige pin. [Curve-API 2.28.4](https://github.com/Mbed-TLS/mbedtls/blob/v2.28.4/include/mbedtls/ecp.h), [exacte PK-types](https://github.com/espressif/mbedtls/blob/1d7033af30e20ccb2a0c0a114d3a08e372430f34/include/mbedtls/pk.h)

## Voorgesteld exact bytescontract

Onderstaand contract is een voorstel dat vóór implementatie één keer definitief moet worden vastgelegd met gedeelde golden vectors. Het vermijdt JSON-canonicalisatie volledig. Onderteken geen opnieuw geserialiseerde JSON-objecten en gebruik niet impliciet Python `sort_keys=True` als taaloverschrijdende standaard.

Maak `ota-authorization.bin` als opeenvolgende bytes, zonder padding of impliciete terminators:

| Volgorde | Encoding |
| --- | --- |
| Domein | Exact ASCII `NETLINK-PANEL-OTA` gevolgd door één NUL-byte |
| Formaat | Eén byte `0x01`; dit formaat fixeert ECDSA-P256-SHA256, geen vrije algoritmekeuze |
| Key-ID | 16 bytes: eerste 16 bytes van SHA-256 van de DER SPKI; collision-check in de ingebouwde keyring |
| Releasevolgnummer | Unsigned 64-bit big-endian |
| Protocol minimum, maximum | Twee unsigned 16-bit big-endian integers |
| Firmwarebestandgrootte | Unsigned 32-bit big-endian |
| Firmware SHA-256 | Exact 32 bytes van het volledige `firmware.bin` |
| ESP image SHA-256 | Exact 32 bytes volgens dezelfde bestaande image-inspectie/partition-hashsemantiek |
| Release manifest SHA-256 | Exact 32 bytes van de gepubliceerde `manifest.json` bytes |
| Broncommit | Exact 20 bytes van de Git commit-ID |
| Versie, boardprofiel, boardrevision, partitielayout | Elk één unsigned lengtebyte gevolgd door exact die hoeveelheid ASCII; respectievelijk maximaal 31, 64, 32, 32 bytes |

Alle strings zijn verplicht en niet leeg, uitsluitend `[A-Za-z0-9._:-]`, met veldspecifieke allowlists waar mogelijk. Afwijkende lengtes, onbekend formaat, buitenbereikwaarden en trailing bytes falen. De oude `profile` kan eenduidig uit boardprofiel, protocol en partitielayout worden afgeleid; laat deze niet als tweede onbeveiligde autoriteit bestaan. Koppel compatibiliteit aan lokale bekende eigenschappen, niet alleen aan echo van hostwaarden.

De signer signeert `ota-authorization.bin` rechtstreeks met ECDSA/SHA-256 en schrijft detached canonical DER naar `ota-authorization.sig`. De volledige release-JSON wordt als exacte bytes gehasht: whitespace wijzigen vereist herondertekening. Laat signaturebestanden en hun eigen digests buiten dit manifest om een cirkel te voorkomen. De host controleert dit manifestdigest én alle vermelde artifactdigests; autoriserende paneelvelden komen uitsluitend uit de geverifieerde binaire record. Een handtekening over een manifestdigest is geen bewijs dat de aangeboden firmware bij die manifest hoort zonder deze bindingcontroles.

Transportvoorstel: één nieuwe `ota_begin_signed` met base64 `authorization` en `signature`, naast de bestaande v2 session/id envelope. De maximale payload uit bovenstaande veldlimieten is kleiner dan 340 bytes; base64 blijft onder 456 tekens. Met maximaal 96 signaturetekens is er ruimte binnen 1024 bytes bij begrensde envelopevelden. Bevestig dit met de echte encoder, maximale session/id/velden en ArduinoJson-arena; verstuur het uitgebreide releasemanifest niet naar het paneel. Base64 decodeert strikt en begrensd. Vertrouw een losse buitenste `key_id`, `size`, `profile` of `version` nooit naast de signed record.

ArduinoJson muteert writable zero-copy input en kan escapes vervangen; hash daarom uitsluitend de eigen gedecodeerde binary-buffer, nooit het inputbuffer nadat JSON parsing eraan heeft gewerkt. Dit houdt het bytescontract onafhankelijk van objectvolgorde, whitespace, Unicode-escapes of duplicate JSON-members. [ArduinoJson 6 inputsemantiek](https://arduinojson.org/v6/api/json/deserializejson/)

## Preflight en legacygrens

1. Host: laad alleen een releasebundle, verifieer de record tegen een gepinde publieke keyring, controleer exact manifest-/artifactdigest, size, versie, releasevolgnummer en bekende hardwarecompatibiliteit, vóór netwerkcontact.
2. Paneel: decodeer en verifieer begrensd; controleer trust/keypolicy, lokale boardrevision, protocol, partitielayout en size, vóór enige mutatie inclusief `anchorRunning()` en vóór `esp_ota_begin`. Alle onbekende, ontbrekende of `unverified` boardrevision-waarden falen gesloten in het managed pad. Hostclaims maken een onbekende fysieke boardrevision niet bekend.
3. Bind hervatten aan de digest van de volledige geverifieerde record, niet alleen size/imagehash. Verifieer de autorisatie opnieuw bij begin/resume en houd de geldige record in RAM bij de transfer.
4. Behoud bytehash, imagehash, magic/chip/profilemarker, imagevalidatie, bootslotselectie en bestaande pending/confirm/rollback. De ESP-IDF API documenteert dat `esp_ota_begin` flash wist en dat applicatie-rollback een apart mechanisme is. [OTA API 4.4.6](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html)
5. De oude `ota_begin` en bench CLI mogen op managed firmware niet als unsigned bypass blijven werken. Een expliciet afgescheiden bench-build mag unsigned toestaan met zichtbare capability/status en expliciete benchkeuze; geen automatische fallback na signaturefouten, ontbrekende keys, oude panelcapabilities of onbekende boardrevision. Ook een gepaarde of TLS-host is geen vervanging voor paneelverificatie.

## Python signer/verifier en bewijs

De normale API is `private_key.sign(payload, ec.ECDSA(hashes.SHA256()))` en `public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))`; de output is DER en ongeldige signatures veroorzaken `InvalidSignature`. Gebruik bij reeds berekende digests uitsluitend `utils.Prehashed(hashes.SHA256())`. Vermijd optionele deterministic-signing features om niet onnodig een nieuwe library/backendversie te eisen. [cryptography ECDSA API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/)

Laad een externe signerkey met `serialization.load_pem_private_key`, publieke verificatiekeys met `load_der_public_key`/`load_pem_public_key`; controleer telkens EC-type en `SECP256R1`. SPKI serialisatie is `public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)`. Alleen de signeromgeving krijgt toegang tot private keys; host en paneel bevatten uitsluitend publieke keys. Dit onderzoek voerde geen keygeneratie of signing uit. [cryptography key-serialisatie](https://cryptography.io/en/stable/hazmat/primitives/asymmetric/serialization/)

Implementatiebewijs moet met duidelijk gemarkeerde testkeys aantonen: Python sign → firmware-mbedTLS verify en host verify; elke bitmutatie van payload, signature en firmware faalt; verkeerd algoritme/curve/key, onbekend key-ID, ingetrokken key, onbekende boardrevision, verkeerde layout/protocol, ontbrekende autorisatie en unsigned fallback falen vóór een mock `esp_ota_begin`. Voeg formaatgrenzen, malformed ASN.1/base64, dubbele buitenste velden, herstel na fout, resume met andere autorisatie en maximaal frame toe. Een bron-/headeronderzoek is nog geen compile/link-, interoperabiliteits-, timing-/heap- of fysiek OTA-bewijs.

## Trust, rotatie en resterende beperkingen

Provision de eerste publieke keyring via een gecontroleerde initiële USB/factory-installatie en verifieer de fingerprint buiten het downloadkanaal. Nooit trust-on-first-use uit een releasebestand. Kies vooraf keybeheer en herstelprocedure; een key-ID is een lookup, geen autorisatie.

Een beperkte eerste versie kan keyring-updates alleen via een door bestaande key geautoriseerde firmware aanbieden: eerst A+B uitrollen, migratie bevestigen, daarna A verwijderen. Reserveer een onafhankelijk beheerde recovery/rootkey als compromis-herstel vereist is; een gecompromitteerde enige releasekey kan zelf een kwaadaardige “rotatie” tekenen. TUF specificeert hiervoor expliciet vooraf vertrouwde rootmetadata, versiegebonden roots en verificatie onder zowel oude als nieuwe rootdrempels. Dit voorstel implementeert geen TUF en claimt die bescherming niet. [TUF rootload/rootupdate en sleutelbeheer](https://theupdateframework.github.io/specification/latest/#detailed-client-workflow)

Een softwarematige denylist of minimum-releasecounter is alleen zo betrouwbaar als de firmware en opslag die haar afdwingen. Een oude correct gesigneerde firmware of rollbackslot kan oude keys/policy terugbrengen; NVS reset, fysieke flashing of een gecompromitteerde signer kan deze basis ondermijnen. Zonder betrouwbare tijd zijn expiry/freeze-garanties evenmin vanzelfsprekend. Formuleer daarom nog geen permanente revocation of anti-rollback-garantie.

ESP32-S3 Secure Boot V2 in IDF 4.4.6 gebruikt RSA-3072/PSS met eFuse trust, niet deze applicatie-P256-record. Signed-app verification zonder hardware Secure Boot is eveneens een apart Espressif-pad. Het hier voorgestelde ontwerp verandert geen bootloader/eFusepolicy en beschermt niet tegen fysieke herprogrammering. [Secure Boot V2 4.4.6 en signed-app-verificatie](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/security/secure-boot-v2.html)

Open besluiten vóór implementatie: bekende boardrevision-provisioning; wie offline trust bootstrap controleert; signer/eigenaar/opslag en recoverykey; toelatingsbeleid voor oudere gesigneerde releases; atomaire policyopslag en herstel bij stroomuitval; maximale envelopevelden; testkeys en concrete interop-vectors. Houd echte keyprovisioning, CI-secrets, release-signing en fysieke acceptatie als afzonderlijke expliciete stappen.
