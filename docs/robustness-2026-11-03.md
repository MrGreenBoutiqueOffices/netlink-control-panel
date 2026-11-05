# Physical robustness check — 2026-11-03

> This report describes the earlier diagnostic phase through timeout fix 0.3.1. The follow-up fix and current final status 0.3.3 are in the [OTA recovery report](ota-recovery-2026-11-03.md), where a full update with actual connection loss and automatic resume passed.

## Assessment of this earlier phase

Basic operation, reconnect and fallback work in the trials performed. Normal Wi-Fi update delivery is **not sufficiently reliable yet**: two earlier attempts and the single authorized trial with timeout fix 0.3.1 failed before activation. This is not production acceptance.

After explicit permission, timeout correction `0.3.1` was installed once over USB; esptool verified the written hash. Exactly one Wi-Fi transfer of the same image was then attempted. It failed after at least 40% with `ConnectionResetError`, before `ota_finish`, reboot or boot confirmation. No upload was repeated. The display still runs the valid USB-installed `0.3.1`; Wi-Fi pairing was retained and `receiving` was `false` when checked.

## Measured results

| Trial | Result |
| --- | --- |
| Hello response before change | 589 bytes across 559 TLS reads; median 1.069 s over 8 requests |
| Response after packet improvement | Usually 1 TLS read, once 2; median 0.07465 s over 8 requests, about 14 times faster |
| Continuous session | 30 s, all 30 heartbeats received, 0 rejected frames |
| Reconnect | 5 of 5 passed; measured 0.32–5.47 s |
| Server port closed | Recovered automatically after 5 s unavailable; about 5 s after reopening |
| Host sends no heartbeats | Panel terminated the stale session after 3.76 s |
| Invalid/large input | Valid command worked again after 10010 bytes of invalid/oversized input |
| Touch | Zitten, Staan and Monitor events received; user confirmed touching the buttons |
| Interrupted flash transfer | TLS disconnected after 4096 written bytes; previous image remained VALID and active |
| Full candidate | 902768 bytes in 91.44 s over Wi-Fi; correct candidate started as PENDING_VERIFY |
| Deliberately unconfirmed | Automatically returned to previous VALID image 90.56 s after observed pending boot |
| Normal update attempts | Two interrupted transfers, after at least 60% and 90% respectively; no activation |
| Single timeout-fix trial | USB installation and hash verification passed; same-image Wi-Fi transfer interrupted after at least 40%, before activation |
| Current state | 0.3.1 running VALID, self-test passed, no active partial transfer; additional 10-second read-only session passed |
| Local tests | 36 tests passed without skips; lint and formatting passed |

Response timing is a small before/after comparison, not a standardized radio benchmark. RSSI varied from approximately -79 to -89 dBm during trials. The latency improvement alone does not prove the cause of every connection loss.

## Demonstrated improvement

`serializeJson` wrote directly to WiFiClientSecure, producing almost one TLS record per byte. The native regression first failed with 96 writes for a 96-byte frame. Firmware now constructs a bounded JSON frame first and sends it in one write. The regression and physical measurements confirm this effect. Oversized frames are rejected; an incomplete write closes the connection.

The first wireless installation attempt for this improvement failed. The old image remained intact. The improvement was then installed once over USB in the same application slot, without replacing NVS, bootloader or partitions. Wi-Fi pairing was retained.

## Second correction: installed, Wi-Fi delivery still unreliable

Firmware also closed an active OTA session after 3.5 s without processed host activity, although OTA had a separate 15-second inactivity budget. A native test against the actual policy function reproduces this difference.

The installed correction uses 15 s only during an active OTA transfer and retains 3.5 s for normal controls. Touch controls remain blocked during OTA. Transfer guard and session share one constant to prevent future divergence. This may prevent interruptions during temporary delays; it remains unproven that this timeout caused the observed physical disconnect.

A later read-only uptime check aligns within about 3.3 s with the known deliberate rollback restart. There is therefore no evidence of another unexpected restart during the last failed transfer. Radio problems and the exact disconnect moment still need to be distinguished from session timeout.

Installed image: `artifacts/releases/panel-0.3.1-ota-lease-fix.bin`. Whole-file SHA-256: `0efb702697ea3de16592c43cbb80bd5948e1cb2739af0e4adcfec9e6701aadaa`; ESP-content SHA-256: `9292af414b67fa2bd41afb4d0b985e00fd1d2fda24f2b261ec9fa5ac67e070de`. This hash was read back from the actual panel with VALID status after both USB installation and failed Wi-Fi transfer. Wi-Fi delivery still fails despite this correction; the timeout discrepancy is therefore not a sufficient explanation or solution for the physical resets. RSSI was -81 dBm during recovery checks. The full successful OTA route with this image was not demonstrated.

## Evidence and repetition

- `artifacts/tls-before.json`: before measurement and regression data.
- `artifacts/hardware-after-batching.json`: reconnect, heartbeat, parser and latency trials.
- `artifacts/hardware-ota-faults.json`: physical interruption, full candidate and actual rollback.
- `artifacts/failed-ota-recovery.json` and `artifacts/current-after-update-failures.json`: valid state after interrupted transfers.
- `artifacts/robust-rc1-install.json` and `artifacts/robust-final-0.3.1.json`: failed normal attempts; these are not success evidence.
- `artifacts/read-only-reset-check.json`: earlier uptime/status check.
- `artifacts/hardware-0.3.1-approved-once.json`: verified USB boot and single failed Wi-Fi transfer with timeout fix.
- `artifacts/hardware-0.3.1-after-approved-failure.json`: retained valid 0.3.1, self-test, Wi-Fi and cleaned-up transfer state after that attempt.
- Full factory backup and Wi-Fi credentials remain private under `.secrets/`.

Non-destructive software checks:

```sh
uv run python -m unittest discover -s tests -v
uv tool run --from ruff ruff check .
uv tool run --from ruff ruff format --check .
```

`scripts/hardware_robustness.py` uses the actual paired panel. Without a candidate it tests connections and input errors; with `--candidate` it actually writes the unused flash slot and causes restarts. Do not run alongside `panel wifi serve` or another updater. The explicitly authorized USB installation and single Wi-Fi transfer were performed. Further physical firmware writes are outside that one-time permission.

Not yet tested: electrical power loss during writing/activation, actual access point outage, Mac sleep, multi-day stability and a successful full update with the additional timeout correction. Existing pairing uses a fixed Mac address; a changed address currently requires setup again.
