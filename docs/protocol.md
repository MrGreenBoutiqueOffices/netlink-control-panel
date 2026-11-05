# Bench protocol v1

For the production contract and new USB service, see [protocol v2](production-protocol.md) and the [USB panel service](usb-service.md). This document describes the older bench interface.

This is a diagnostic prototype, not the final NetLink command contract. No desk or monitor action is executable. USB and Wi-Fi share these application messages. The panel is the TLS-PSK client; the Mac bench tool is the server. See [Wi-Fi setup](wifi.md).

Transport: UTF-8 JSON objects, one per newline, USB CDC serial at 115200 baud. Maximum frame length is 1024 bytes excluding the newline. On overflow discard through the next newline. Ignore malformed JSON, boot logs, and incompatible envelopes. Every message has integer `v: 1` and a nonempty string `type`. Request IDs are positive integers up to 2147483647. Do not replay actions after reconnect.

| Direction | Type | Fields and meaning |
| --- | --- | --- |
| Host → panel | `hello` | `id`; request fresh identity |
| Panel → host | `hello` | Matching `id`, `panel_id`, `firmware`, `simulated`, `capabilities`; hardware also reports `display_ready`, `transport`, and a sanitized `wifi` status |
| Both | `heartbeat` | No acknowledgement required; panel reports `uptime_ms` |
| Host → panel | `demo_state` | `id`, integer `height_mm` in 500..1300 and integer `brightness` in 0..100; display demo data only |
| Panel → host | `ack` | Matching `id` and boolean `ok`; confirms demo data application, never physical movement |
| Panel → host | `touch` | `action` is `sit_preview`, `stand_preview`, or `monitor_preview`; diagnostic event only |
| Host → panel, USB only | `wifi_config` | `id`, `ssid` (1..32 UTF-8 bytes), `password` (8..63 bytes), `host` (reachable IPv4), `port` (1024..65535), `key` (64 hex characters); `ack` confirms NVS storage, not successful association |
| Host → panel, USB only | `wifi_clear` | `id`; `ack` confirms removal of the stored network/key configuration |
| Host → panel, active TLS Wi-Fi only | `ota_begin` | `id`, `profile`, `version`, `size`, whole-file `sha256`, ESP-content `image_sha256`; ack includes `next_offset: 0` |
| Host → panel, active TLS Wi-Fi only | `ota_chunk` | `id`, exact `offset`, base64 `data` decoding to 1..512 bytes; ack includes exact `next_offset` |
| Host → panel, active TLS Wi-Fi only | `ota_finish` | `id`; verifies complete data/image, selects candidate and acknowledges `state: rebooting` |
| Host → panel, active TLS Wi-Fi only | `ota_confirm` | `id`, expected running `image_sha256`; after startup checks, ack includes `state: valid` |
| Host → panel, active TLS Wi-Fi only | `ota_abort` | `id`; discards unfinished transfer without changing boot selection |

The host sends a heartbeat each second after handshake; the panel sends one each second while connected. Both time out after approximately 3.5 seconds without the peer's expected liveness. The host retries hello while waiting, accommodating USB-triggered reset. Starting a new bench session uses a new serial session and handshake; it sends only demo state.

The firmware disables touch feedback on host timeout. Releasing a touch is required before generating another press event after reconnect. A USB hello preempts Wi-Fi; a Wi-Fi hello cannot preempt active USB. Only the active transport can send demo state or renew its heartbeat. Inactive partial frames are discarded when the network session closes. A Wi-Fi TCP/TLS connection without an application hello is also closed after a bounded wait.

There is no movement authorization, MQTT bridge, or production management API. Wi-Fi peers are authenticated by a unique PSK installed over USB, and the host additionally checks the application identity. A successful bench requires matching hello and state-acknowledgement IDs plus a heartbeat; unrelated messages do not satisfy those requirements. Credentials are never included in hello, ack, status, or error payloads.

Firmware 0.3.0 advertises `ota_v1`. Hello includes `self_test_ok` and an `ota` object with supported profile, running ESP image hash, retained image marker, state, slot capacity, and receive state. OTA is disabled on an unexpected partition layout. USB preemption aborts a receiving Wi-Fi transfer; selecting a validated candidate schedules an immediate reboot and rejects further commands. Chunk data remains within the existing 1024-byte JSON limit.

Only accepted OTA requests renew transfer liveness. A partial transfer is abandoned on connection loss or inactivity. Pending boots require confirmation within 90 seconds; the Arduino automatic early confirmation hook is overridden. Host success requires a second TLS session after activation, the expected image/version, successful explicit confirmation, and an observed valid state. A dropped finish acknowledgement is resolved by observing the boot, never by blindly retransmitting. See [OTA procedure](ota.md).

The serial simulator models framing, handshake, demo validation, heartbeat, and a silent endpoint. Additional tests exercise real TLS-PSK authentication/encryption, invalid peers, identity checks, and a host-compiled firmware arbitration policy. They do not emulate the ESP32 radio, graphics, touch hardware, bootloader, update recovery, or power behavior. Successful simulation cannot establish physical acceptance.
