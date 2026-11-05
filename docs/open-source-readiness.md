# Publication readiness

Status on 2026-11-05: the repository is **public** and the project's own code is licensed under **GPL-3.0-only**. The owner chose to proceed with publication without the proposed upstream inquiry and further distribution-preparation steps. That decision does not establish new rights to vendor code; the research findings and unresolved scope below remain recorded.

The research and publication decision are recorded in [#34](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/34).

## Checked

- The repository previously had no project license. `LICENSE`, the README and Python package metadata now record the same choice. Copyright is not transferred to another individual or legal entity.
- An offline `detect-secrets` 1.5.0 scan of 178 unique text blobs from the locally fetched Git history found no potential secrets. Candidates were not verified over the network. This is a bounded scan, not a guarantee that every type of secret or sensitive information is absent.
- `.secrets/`, `artifacts/`, `firmware/.vendor/` and `firmware/.pio/` are not tracked repository files. GitHub already has release assets and Actions artifacts; these are separate distributions and are not protected by `.gitignore`.
- Inter includes its OFL license. The build also downloads pinned LILYGO source and SDK/dependencies; see [third-party notices](../THIRD_PARTY_NOTICES.md).

## Findings for #34

- [Exact driver research](touchdriver-license-research.md): 24 of 25 local upstream files are identical; the only local patch disables touch-controller flashing. The existing build links four Hyn implementations. Related official GPL-published source provides a publication trail for two identical files, but does not establish permission for the complete exact copy. Firmware blob headers are not compiled with the current patch; source rights for the driver code actually used are still needed.
- [GFX research](gfx-license-research.md): the maintainer demonstrably added an upstream BSD license. The LILYGO copy contains substantive changes and additions; these are not automatically relicensed.
- Remote snapshot: all 42 existing completed Actions log archives, 19 unexpired artifacts and 5 v0.8.0 release assets were downloaded successfully. No downloads were unavailable. A detect-secrets 1.5.0 scan without network verification found 0 candidates in 402 text files, including extracted protocol source and `strings -a` output from firmware binaries. SHA256SUMS for all 20 release/candidate bundles were also verified against the complete binary/archive bytes. See the [content-free inventory with IDs, sizes and SHA-256](evidence/publication-remote-inventory.json). This is a secrets/integrity check, not final license clearance or proof that every possible sensitive item is absent; images were not checked with OCR. The snapshot excludes runs created later for this research PR.
- Protocol-core 1.0.1 now includes GPL, the third-party inventory and OFL with digests in `UPSTREAM.json`. Protocol/transport code and consumer digests are unchanged. The new archive hash and package version require explicit consumer adoption; existing releases were not overwritten. This does not complete delivery of all firmware notices/source/installation information.
- PRs #35 and #36 are merged into main. The GPL license, English documentation, research and protocol-core license files are present. Public repository metadata and the v0.8.0 release manifest were retrieved successfully without authentication after the visibility change. That existing manifest is explicitly unsigned; public availability does not authorize automatic installation.

A [specific public question for LILYGO was prepared](lilygo-license-inquiry-draft.md), but was not sent; the owner chose not to pursue it. No driver was replaced and no physical firmware test was performed.

## Unresolved distribution findings

1. Establish the license/distribution permission for the Hynitron touch driver in the pinned LILYGO source. The inspected root and driver directory lack a clear license notice. GPL for our own code does not resolve this. Alternatives are demonstrable permission or a replacement driver with a suitable license; no upstream message has been sent.
2. Establish applicable notices for the exact Arduino_GFX vendor copy and collect the other notices for the components actually compiled. A license text from current upstream is not automatically evidence for that vendor copy.
3. Provide applicable licenses, corresponding source and reproducible build information with the firmware assets and protocol-core archive; where required by GPL, also provide installation information for installing modified software. The existing USB recovery route and OTA signing policy must be addressed explicitly. Production signing keys or pairing details are not made public by default.
4. Distribution conditions and sensitive-content review of existing releases, Actions artifacts and Actions logs remain separate from a negative automated secret scan. The remote snapshot above complements the local Git scan; it does not resolve license/distribution issues for historical firmware. No old assets or runs were deleted.

Releases from this now-public repository are directly accessible as the planned update source. No separate firmware repository or update server is needed. This availability does not resolve the distribution findings above. The panel must still verify the independent release signature and compatibility locally; public download access does not establish installation trust.

Sources: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html), [GPL-3.0-only SPDX text](https://github.com/spdx/license-list-data/blob/main/text/GPL-3.0-only.txt), [GitHub visibility and public Actions history](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), [pinned LILYGO source](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02).
