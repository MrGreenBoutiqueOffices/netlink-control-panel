# Publication readiness

Status on 2026-11-05: the chosen license for the project's own code is **GPL-3.0-only**. The repository remains private until the distribution issues below are resolved. These documentation and license changes do not change GitHub visibility.

The remaining items are tracked in [#34](https://github.com/MrGreenBoutiqueOffices/netlink-control-panel/issues/34).

## Checked

- The repository previously had no project license. `LICENSE`, the README and Python package metadata now record the same choice. Copyright is not transferred to another individual or legal entity.
- An offline `detect-secrets` 1.5.0 scan of 178 unique text blobs from the locally fetched Git history found no potential secrets. Candidates were not verified over the network. This is a bounded scan, not a guarantee that every type of secret or sensitive information is absent.
- `.secrets/`, `artifacts/`, `firmware/.vendor/` and `firmware/.pio/` are not tracked repository files. GitHub already has release assets and Actions artifacts; these are separate distributions and are not protected by `.gitignore`.
- Inter includes its OFL license. The build also downloads pinned LILYGO source and SDK/dependencies; see [third-party notices](../THIRD_PARTY_NOTICES.md).

## Still required before making the repository public

1. Establish the license/distribution permission for the Hynitron touch driver in the pinned LILYGO source. The inspected root and driver directory lack a clear license notice. GPL for our own code does not resolve this. Alternatives are demonstrable permission or a replacement driver with a suitable license; no upstream message has been sent.
2. Establish applicable notices for the exact Arduino_GFX vendor copy and collect the other notices for the components actually compiled. A license text from current upstream is not automatically evidence for that vendor copy.
3. Provide applicable licenses, corresponding source and reproducible build information with the firmware assets and protocol-core archive; where required by GPL, also provide installation information for installing modified software. The existing USB recovery route and OTA signing policy must be addressed explicitly. Production signing keys or pairing details are not made public by default.
4. Review existing releases, Actions artifacts and Actions logs for distribution conditions and sensitive content before changing visibility. The local Git scan did not include these external files and logs. No old assets or runs were deleted.

Once these items are resolved, releases from this repository can directly serve as a public update source. No separate firmware repository or update server is needed. The panel must still verify the independent release signature and compatibility locally; public download access does not establish installation trust.

Sources: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html), [GPL-3.0-only SPDX text](https://github.com/spdx/license-list-data/blob/main/text/GPL-3.0-only.txt), [GitHub visibility and public Actions history](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), [pinned LILYGO source](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long/tree/3deece89098f25e7d155e41e4e0f5dd8b368ab02).
