# Firmware checks and traceable releases

Part of #23. Firmware/protocol remain in `netlink-control-panel`; the existing webserver container is the consumer. No panel-service image or extra deployment path is added. Release Drafter manages release notes and the draft. On publication, the firmware workflow builds assets for that existing release; no firmware is installed.

## PR and main checks

Workflow structure follows `python-netlink` and `python-balena-cloud`:

| Workflow | Trigger and responsibility |
| --- | --- |
| `linting.yaml` — Linting | Push, PR and manual; separate Ruff, yamllint and asset/preview jobs |
| `tests.yaml` — Testing | Push, PR and manual; Python job with firmware build, all host/native tests and commit-bound candidate artifacts |
| `release-drafter.yaml` — Release Drafter | Main and manual; standard action with central organization configuration |
| `release.yaml` — Release | `release.published`; one firmware release job in the `release` environment |

Jobs use `DEFAULT_PYTHON`, `ubuntu-latest`, setup-uv, explicit `uv python install` and `uv sync --locked`, like the package projects. Lint/test use the uv cache; the release job disables it. `contents: read` is the default; only draft/release jobs receive required write permissions. Actions are pinned to the same commit SHAs as the examples. The current firmware test baseline is Python 3.14 with TLS-PSK; the runner uses the current patch version of that Python series.

Functional checks remain firmware-focused: fixed Python/PlatformIO/library versions, immutable LILYGO source with automatic touch-controller flashing disabled, actual C++ protocol/UI tests, preview syntax and sanitized artifacts. Missing compiler/ArduinoJson/TLS-PSK or skipped tests do not produce a green test job. `tests.yaml` uploads a `panel-<commit>` artifact with 30-day retention.

The generator explicitly fixes BASIC font layout on macOS and Linux. PNG references are checked at identical dimensions and RGBA pixels; embedded C++ arrays must remain byte-identical.

Existing local system tests remain usable on machines lacking all CI prerequisites, but `scripts/check_tests.py` accepts no skips.

Run the same check path locally:

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

The output directory must be empty; the packaging CLI rejects changes to tracked source files. Always rebuild from the same clean checkout. An existing binary with the same version does not itself prove its source commit. CI therefore builds and packages in the same job without caching an earlier firmware build result.

## Artifacts

| File | Contents |
| --- | --- |
| `firmware.bin` | Validated ESP32-S3 application; no merged flash, bootloader, partitions or credentials |
| `manifest.json` | Source repository/commit/tag, firmware version, file/image hashes, profile/slot limit, protocol/board compatibility, input digests, artifact digests and signing status |
| `protocol-core.tar.gz` | Bounded version of `protocol.py` and selected transport-independent host symbols, with provenance/digests, GPL license and third-party inventory |
| `RELEASE_NOTES.md` | Release: Release Drafter body of the existing published release; PR/main: CI candidate notice |
| `authorization.json` | Signed releases only: separate ECDSA P-256 authorization record and signature |
| `SHA256SUMS` | SHA-256 of all preceding files, including the manifest |

ESP image header, segment checksums, appended image hash and board/partition marker are checked. Without a release, image, project version and fallback header must match. For a published release, validated tag `v<semver>` is authoritative: a compiler define injects the same version into display, handshake and image marker, and it must appear in the built image. Source files are not rewritten. Release notes come from GitHub; no separate manual changelog or mandatory version commit per release is required. Individual artifacts can be checked for transfer corruption with `sha256sum --check SHA256SUMS`.

For the same source commit, firmware bytes and release notes, packaging, manifest and protocol archive are deterministic, including archive order, metadata and gzip timestamp. The workflow does not claim bit-identical ESP builds across operating systems/toolchains; each actual built image has its own recorded digests. Hashes are not proof of authenticity and do not replace a release signature.

## Protocol boundary and webserver

`release/protocol-core.json` defines package version 1.0.1, allowed symbols and excluded serial imports. Version 1.0.1 adds `LICENSE`, `THIRD_PARTY_NOTICES.md` and `preview/assets/OFL.txt`, with their digests in `UPSTREAM.json`; generated protocol/transport bytes and consumer digests remain unchanged. Archive and manifest version do change, so consumer adoption must explicitly review package version and archive hash. This package version is independent of firmware 0.8.0 and wire protocol v2. The package contains no daemon, CLI, USB opener or pySerial import. The webserver owns its SerialX adapter, session lifecycle and existing status/command layer.

CI compares generated bytes against the consumer selection from the webserver commit pinned in this contract. The artifact contains the same `generated_sha256`/`upstream_sha256` boundary checked by existing webserver vendoring. A test imports the packaged core and uses the actual C++ firmware handler through a pseudo-terminal: handshake, read-only device state, snapshot and rejected actions must work. A changed consumer digest blocks packaging until package version, contract and compatibility are deliberately reviewed.

This tests the protocol package and recorded consumer contract, not the complete webserver container/fleet. The private webserver repository is not fetched using extra credentials from PR CI. The webserver retains its existing immutable source commit and digest checks for now; adopting the release artifact requires a separate webserver PR with commit/package version/archive hash and existing consumer/runtime checks. Open webserver PRs and submodule pointers are not changed here.

## Release Drafter and release assets

`release-drafter.yaml` uses the same minimal job as `python-balena-cloud`: one Release Drafter action on main or a manual run, with inherited central categories and version resolver. There is no checkout, custom version initialization or local configuration copy. v0.8.0 is published; subsequent drafts follow existing release history and PR labels. Review the proposed version and notes before publication.

The maintainer reviews and publishes the draft in GitHub. `release.yaml` starts on `release.published`, like the package release workflow. The release job runs in the `release` environment and checks out the **exact release tag**. It validates main ancestry and version, sets firmware version for the build, builds the image and runs host/native tests. There is no second publication/upload job or cross-workflow artifact transfer.

The publication event's release body is included as `RELEASE_NOTES.md`. The job packages the image, checks `SHA256SUMS` and uploads the five bench assets or six signed assets using `svenstaro/upload-release-action` to the existing release ID. Existing Release Drafter title and body are preserved. Assets are not overwritten; duplicate names fail the upload. A partially failed upload may leave assets behind; inspect them before retrying. A release has usable firmware assets only after its release job succeeds. PR/test workflows create no tags or releases.

The default policy produces explicitly **unsigned bench artifacts**. Optional signing and host/panel verification are described in [signed updates](signed-updates.md). A signed release requires previously reviewed public trust, known board revision and a private secret in environment `release`; missing or invalid configuration fails the job. PR CI uses only ephemeral test keys. Production key provisioning and the panel's independent Wi-Fi lifecycle remain open within #15; webserver update integration is outside this scope. A Release Drafter draft, published release or green CI is not physical installation, OTA acceptance or movement permission.

The existing fleet-first route remains authoritative for NetLink host software: a reviewed consumer pin goes through the webserver image to NetLink develop/dev, acceptance and stable production. Panel firmware will also gain independent Wi-Fi downloading and installation without requiring a webserver or Balena deployment. The panel uses signed release assets and its local verification policy. Actual distribution source, reachability and channel selection still need to be implemented within #15; a private GitHub release is not automatically accessible by the panel. This release workflow builds and publishes assets and initiates no hardware installation. Protocol-core artifact adoption in the webserver and its rollout acceptance remain separate work within #23; a webserver update feature is not part of #15.
