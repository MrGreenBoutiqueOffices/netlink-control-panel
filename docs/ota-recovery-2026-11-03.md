# Recoverable OTA — 2026-11-03

## Established cause

On the actual panel, diagnostic firmware first recorded a Wi-Fi disconnect with reason 3 (`WIFI_REASON_AUTH_LEAVE`) at uptime 14004 ms. TLS then reported `data_to_read` error -76 and the session was released at uptime 14071 ms. The last valid host activity was only 120 ms earlier. Upload failed at offset 73216, well before activation. The subsequent handshake returned the same valid image and pairing.

For this reproduced failure, this shows Wi-Fi loss preceded TLS reset; the control/OTA deadline had not expired. Why association was lost (station/access point/radio) was not established. The one-second connect call also affects the TLS write budget in Arduino 2.0.14, but this measurement does not prove a write timeout. That budget was therefore not changed based on an unproven cause.

The application bug making OTA failure fatal was established: `releaseSession()` always called `ota.abort()` and the host stopped at the first transport error. Even a written block with a lost acknowledgement could not resume. The earlier 15-second timeout correction did not fix this.

## Change

- The valid active slot remains selected throughout the transfer. A transfer handle and running SHA-256 in RAM survive Wi-Fi/TLS loss for at most 60 seconds without transfer activity.
- A new mutually authenticated session can resume only the same complete manifest. Size, profile, version and both SHA-256 values must match. The actual written position is returned; no repeat erase or duplicate write occurs. A different image is rejected.
- The host validates the position, recovers at most five times within its default 600-second deadline and reports recovery. No automatic retry on substantive rejection or legacy firmware without resume capability.
- USB takeover, explicit abort and lease expiry clean up the transfer. Panel reset loses the RAM transfer; restarting from zero is then safe. Normal controls retain the 3.5-second timeout and remain blocked during OTA.
- Activation still requires length, both hashes, image identity and ESP image validation. Success requires a new session with the desired boot, startup self-check and read-back VALID boot confirmation. Lost finish and confirm responses are resolved through status checks.
- Hello includes uptime, reset reason and last Wi-Fi disconnect reason. Temporary debug prints and additional SDK log levels were removed from final firmware. Redundant screen redraws across many consecutive chunks in the same percentage range are limited to one per 10% step.

## Validation

- The full 43-test local suite passed without skips; two subsequently found host problems are covered by two additional TLS regressions and the affected 10-test TLS suite passes (45 unique tests total). Lint and formatting pass. Coverage includes real TLS, lost begin/block/finish/confirm responses, invalid resume offsets and the actual firmware handler with counted fake SDK writes. The new TLS test first failed with `ConnectionError`; the handler first failed on inability to resume. Both passed after the change.
- Firmware 0.3.2 with recovery code built successfully and was installed once over USB; the written flash hash was verified. A separate diagnostic build had been installed once beforehand. NVS and partition layout were preserved.
- Physical server outage of 5 s: resumed at byte 4096, new connection 4.28 s after reopening, no panel reset.
- Physically sent chunk without reading its ACK: resumed at byte 4608, new connection after 4.28 s, no blind rewrite. Both trials ended with explicit abort, original image VALID and `receiving=false`.

| Full trial | Result |
| --- | --- |
| 1: to 0.3.3, 904144 bytes | Automatically passed, new boot and VALID read back; 0 recoveries. About 100.08 s from server start to confirmation. |
| 2: to 0.3.2, 904144 bytes | All bytes and reboot succeeded; old host stopped on reboot race. Boot confirmation alone recovered, without re-upload. |
| 3: to 0.3.3, 904144 bytes | Automatically passed, new boot and VALID read back; 2 recoveries. About 144.61 s from server start to confirmation. |

The third trial actually lost connection after transfer began. The normal updater automatically resumed from byte 12800, then completed the entire image and boot confirmation. This is physical end-to-end recovery validation in addition to the two deliberately interrupted trials. Exactly six OTA transfer trials were performed: one diagnostic, two partial recovery trials and three full transfers. No additional transfer after the reboot race; only status and boot confirmation.

Final status: firmware **0.3.3**, expected image hash `d7428a80fe06f3fe1423d089759011193efd6c0c3864afe30b19e2a7334166dd`, **VALID**, startup self-check passed and no active transfer. An additional 30-second read-only session and three reconnects passed. Host tool and lockfile are at 0.3.3; the local installation is synchronized.

Conclusion: the original fatal transport interruption was fixed and retested on the same panel. Full update, actual connection loss, automatic resume, reboot and confirmation succeeded together. This accepts this bounded recovery route; it does not prove multi-day or electrical power-loss resilience.

## Additional reboot race

The second full transfer reached 100% and activated the candidate, but an early handshake still received a negative ACK from the old, already committed firmware. The host treated it as `Unexpected OTA response type` and stopped. A status check then saw exactly the desired 0.3.2 as PENDING_VERIFY with startup self-check passed. Only boot confirmation was recovered; no transfer was repeated. This happened before the boot deadline, after which the same hash was read back as VALID.

The host now distinguishes an explicitly rejected hello (`HandshakeRejected`) from unexpected protocol data. Only during ongoing recovery or expected reboot is this retried within the same reconnect budget. No firmware is blindly rewritten. A real TLS regression first failed on this exact negative-ACK path and passed after correction.

Another focused TLS regression prevented the host from cancelling an already active different image with `ota_abort` after a rejected `ota_begin`. That automatic abort was removed; firmware enforces its own transfer lease and substantive error handling.

## Evidence and limitations

`artifacts/ota-reset-diagnostic.json` and `artifacts/ota-reset-diagnostic-usb.log` contain the measured failure. `artifacts/ota-resume-physical-faults.json` contains the two physical recovery trials. `artifacts/ota-resume-full-1.json`, `ota-resume-full-2.json`, `ota-resume-full-2-recovery.json` and `ota-resume-full-3.json` preserve the full update attempts, including the second attempt's original unconfirmed result and separate later confirmation. `artifacts/ota-resume-final-status.json` and `artifacts/ota-resume-summary.json` contain final checks and summary. The repeatable opt-in script is `scripts/hardware_ota_recovery.py`; the normal updater remains `panel wifi update`.

These trials do not guarantee recovery from every network fault. Out-of-range or interruptions exceeding recovery budgets produce a controlled error and leave the known valid image active. Electrical power loss during writing/activation, actual access point outage, USB takeover during writing and multi-day stability were not tested. The earlier physically demonstrated 90-second rollback is retained; that trial was not repeated. Factory backup and pairing remain private.

Sources for SDK semantics: [Arduino WiFiClientSecure 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/WiFiClientSecure.cpp), [TLS transport 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/ssl_client.cpp), [ESP-IDF 4.4.6 OTA](https://docs.espressif.com/projects/esp-idf/en/v4.4.6/esp32s3/api-reference/system/ota.html).
