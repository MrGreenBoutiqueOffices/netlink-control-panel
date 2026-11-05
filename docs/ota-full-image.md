# Large OTA image: diagnosis and progress-based recovery

Part of #14. This changes the existing bench updater, not the deployment architecture. NetLink webserver integration, an authorized managed updater and signing remain #15. USB remains the installation route until the physical full-image matrix is accepted.

## Established host bug

The preserved 0.4.1 report shows a 1,515,984-byte image and resume at offsets 420864, 729600, 1139200 and 1448960. Despite this, the updater exhausted its lifetime budget of five recoveries and stopped around 95%. The report preserves the complete image hash and explicit terminal error `OTA reconnect budget exhausted`.

A new test against the actual Python updater over TLS-PSK reproduced the same category: six interruptions, each after a written block whose ACK is lost. Before the fix, the host stopped after five recoveries with `ConnectionError`, although the peer could demonstrably resume further. One command reproduces this regression:

```sh
uv run --locked python -m unittest discover -s tests -p test_ota_network.py -k repeated_progressing -v
```

The fix makes recovery allowance depend on a strictly higher validated write position. Only that new progress resets the stalled counter. Equal positions, reset positions after panel reset and successful handshakes alone grant no extra budget. Total recoveries are recorded separately. Five recovery attempts without progress remain allowed; then the host stops explicitly. This also applies to repeatedly lost `ota_finish` requests: no endless reactivation. Possible activation remains `unconfirmed` when evidence is insufficient.

The global deadline stays the same, 600 seconds by default and at most 3600. Recovery does not extend it. The TLS handshake budget is bounded by remaining global time. Firmware leases, normal control timeout, block size and wire protocol do not change. Existing 0.3.2+ firmware with `ota_resume_v1` can already use this host fix. Legacy firmware without the capability receives no blind upload retry.

The host still validates offsets and the same manifest. A rejected manifest does not automatically abort another image. Success requires the expected new image, version, startup self-check and read-back VALID status; a socket write or 100% progress is insufficient.

## Measurements and cause boundaries

Each valid hello records only a bounded selection: firmware identifier, uptime/reset reason and numeric Wi-Fi RSSI/disconnect reason where present. Host measurements add TLS duration, hello duration and elapsed time. The receipt contains phase, `confirmed_bytes` (highest confirmed position), `current_bytes` (last reported position of the current transfer), net progress per second, total recoveries and `failures_without_progress`. Net speed uses the highest position divided by total time, including waits/recovery; it is not raw radio throughput.

At most 32 recent session measurements are retained, plus the count omitted. Transport errors record only phase and local exception class. TLS rejections are counted; only the first five get console messages. No arbitrary exception text, credentials, SSID, IP or complete frames. The target image hash remains visible in the existing manifest.

The physical diagnosis in the [earlier report](ota-recovery-2026-11-03.md) measured Wi-Fi loss before TLS reset, without an expired control/OTA timeout. Why association was lost remains unproven. The host bug demonstrated here explains why a larger image failed permanently after several recoverable interruptions; it does not prove the radio/AP problem itself is solved. New diagnostics must enable that physical distinction.

## Software matrix

Tests establish a real TLS-PSK connection to the updater. The panel peer simulates application flash/boot and is not an ESP flash or Wi-Fi emulator. Comparing all received bytes, hashes and confirmed boot detects wrong offsets or duplicate data.

| Profile | Expected outcome |
| --- | --- |
| Complete built firmware, stable TLS | All bytes and confirmed boot within 60 seconds |
| Same complete image, 1 ms delay per block, six lost ACKs around 27/48/75/95/96/99% | Resume at actual written positions, complete bytes and confirmed boot within 60 seconds |
| Six disconnects before begin acknowledgement, no progress | Stop after at most five recoveries; no activation |
| Repeatedly lost finish requests, retained complete transfer | Bounded stop as unconfirmed; no invented success |
| Continuing but excessively slow transfer, fixed 10-second total deadline | Deadline stops transfer despite progress; no activation |
| Lost begin/chunk/finish/confirm ACK and reboot race | A verified outcome or explicit error; no blind rewrite |
| Different active manifest image | Rejection; host sends no abort for that other image |

The existing small TLS fixtures' 10-second budget was too short for the deliberately delayed large image on the development machine. The full-image test therefore uses 60 seconds; the production default was not raised. A separate deadline test demonstrates the final boundary under continuous progress. Test RSSI of -85 dBm is a synthetic diagnostics field, not an RF measurement or evidence of a weak physical connection.

```sh
uv sync --locked
uv run --locked python scripts/prepare_firmware.py
uv run --locked pio run --project-dir firmware
uv run --locked python scripts/check_tests.py
```

## Physical matrix still to run

Software tests do not open a physical panel. Start physical writes/restarts only as deliberately selected trials. Use a deliberate candidate, known image hash, active-slot/backup verification and one updater owner. Do not change Wi-Fi/AP settings as part of an upload test.

| Condition | Minimum acceptance |
| --- | --- |
| Measured good coverage | Two full uploads with known hashes within 600 seconds, correct new boot and read-back VALID |
| Measured weak coverage | Same matrix with recorded RSSI and disconnect/reset reasons; confirm within deadline or fail explicitly and safely, no claim without evidence |
| One interrupted connection and one lost chunk ACK | Resume without duplicate bytes; previous valid image remains available until correct activation |
| Recovery/deadline budget exhausted | No success report; read actual running image and transfer status separately |

For each trial, retain the sanitized receipt, candidate/current version and hashes, duration, RSSI, recoveries and boot outcome. A software matrix, published release or green CI does not close #14: physical full-image/radio tests remain required. Power loss, all faulty candidates and multi-day recovery also remain #16/#19.
