# License research for the exact Arduino_GFX vendor copy

Researched on 2026-11-05. No firmware or dependency was replaced. The source is LILYGO's bundled `lib/Arduino_GFX-1.3.7` directory from commit `3deece89098f25e7d155e41e4e0f5dd8b368ab02`.

## Established findings

The upstream maintainer responded to the license question in [Arduino_GFX #240](https://github.com/moononournation/Arduino_GFX/issues/240) and added [commit 372094ccbf2579a5a568ca59e5315250bf1ae080](https://github.com/moononournation/Arduino_GFX/commit/372094ccbf2579a5a568ca59e5315250bf1ae080) on 22 August 2023. The [license text at that commit](https://github.com/moononournation/Arduino_GFX/blob/372094ccbf2579a5a568ca59e5315250bf1ae080/license.txt) is two-clause BSD, copyright Adafruit Industries 2012. An unchanged copy is in [licenses/Arduino_GFX-BSD-2-Clause.txt](../licenses/Arduino_GFX-BSD-2-Clause.txt). This is primary evidence of the upstream license, not an arbitrarily selected license for the entire vendor copy.

The discussion acknowledges that upstream used code from other projects. Existing component copyrights/conditions must therefore be retained; the maintainer's response cannot replace other copyright holders' permissions.

## Comparison with the vendor copy

Official tag [v1.3.7](https://github.com/moononournation/Arduino_GFX/tree/597ad3e6da7aa6008b7ce69711f6c9ec78d4b635) does not yet contain a root license file. All 274 vendor files were compared by relative path against official GitHub archives of this tag and the license commit. `exact` means identical bytes; `whitespace` means only filtering whitespace makes the files equal, not evidence of identical license rights.

| Reference | Exact | Whitespace differences only | Substantive differences | Vendor only |
| --- | ---: | ---: | ---: | ---: |
| v1.3.7, `597ad3e6da7aa6008b7ce69711f6c9ec78d4b635` | 183 | 71 | 7 | 13 |
| License commit `372094ccbf2579a5a568ca59e5315250bf1ae080` | 164 | 45 | 52 | 13 |

Substantive source differences from v1.3.7 are in `src/Arduino_GFX_Library.h`, `src/Arduino_DataBus.cpp`, `src/Arduino_GFX.cpp`, `src/Arduino_GFX.h`, `src/Arduino_TFT.cpp` and `src/databus/Arduino_ESP32QSPI.h`; the seventh difference is README. The 13 vendor-only files include additional display implementations for AXS15231, CO5300 and SH8601 and extra examples. Those differences do not themselves establish a license. The exact vendor copy is therefore not an unchanged repackaging of the upstream tag.

## Conclusion

The upstream BSD basis is established and recorded. Rights/notices for LILYGO-specific modifications and additions remain a specific question for LILYGO. No blanket claim is made that all code in the vendor copy is demonstrably BSD-2-Clause. This question is included in the [unsent license inquiry](lilygo-license-inquiry-draft.md); #34 remains open for it.
