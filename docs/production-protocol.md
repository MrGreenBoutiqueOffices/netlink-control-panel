# NetLink panel protocol v2

This is the panel-service contract. It is independent of USB or an authenticated Wi-Fi stream. Firmware 0.6.0 and host 0.6.0 implement the handshake and full panel status. Real desk/monitor actions, configuration synchronization and managed updates will be enabled only with their own capabilities and adapters. Firmware remains a local demo; `desk` and `monitor` are therefore `null`.

The existing [bench protocol v1](protocol.md) remains available for demos, USB provisioning and diagnostics/recovery. A v2 session accepts no v1 messages. A v1 client cannot take over an active v2 session; after disconnect the session expires within 3.5 seconds. Source firmware version 0.6.0 does not mean it is already installed on a physical panel.

## Framing and compatibility

- UTF-8 JSON objects, one per newline; at most 1024 bytes excluding newline. USB CDC uses 115200 baud. No logging on the protocol stream.
- Every v2 envelope has integer `v: 2` and nonempty `type`. A request/response has integer `id` in 1..2147483647, unique within the session. A boolean is not an integer ID.
- Host and panel must have overlapping `protocol_min`/`protocol_max`; this implementation supports only 2. The host rejects unknown board profiles, different panel identities, different board revisions, invalid boot state and missing capabilities.
- Framing versions 1 and 2 are isolated. Only v2 can negotiate this handshake; an unknown envelope version is ignored and produces a bounded host timeout. A v2 hello with an incompatible range gets `incompatible_protocol`.
- Unknown optional fields may be ignored; changing existing field semantics requires a new contract version/capability. Oversized frames are discarded through the next newline; invalid frames do not renew heartbeat liveness.

## Handshake and identity

For each connection, the host chooses a cryptographically random `session` of 32 lowercase hex characters. Responses, status and heartbeats belong to that session; late frames from another session are not applied.

```json
{"v":2,"type":"hello","id":1,"session":"0123456789abcdef0123456789abcdef","protocol_min":2,"protocol_max":2}
```

The panel responds with the same ID and session, plus:

| Field | Meaning |
| --- | --- |
| `panel_id` | Stable panel identity, separate from the USB serial |
| `board_profile` | `lilygo-s3-long-cst3530` for this build |
| `board_revision` | Currently `unverified`: no automatic detection or claim of an established PCB revision |
| `firmware` | Firmware version from the shared version source |
| `protocol_min`, `protocol_max` | Supported contract range, currently both 2 |
| `boot_id` | 16 random hex characters per boot; not a persistent device ID |
| `boot_state`, `self_test_ok` | The service accepts only `valid` and `true` |
| `capabilities` | Currently only `panel.status.v1` |
| `actions` | Currently empty; the host has no actuation route yet |

A healthy startup self-check confirms initialization; it is not a physical touch-quality or real desk-safety test. Enrollment pins USB VID, PID, serial and handshake identity/profile/revision. This is local host authorization, not mutual cryptographic USB authentication. Only status is currently exposed; control rights and enrolled-host verification on the panel must be enforced before real control is enabled.

The firmware handler is identical for both streams. The existing Wi-Fi stream requires its own TLS-PSK authentication; the new Linux service implements only USB in this PR. Transport selection/fallback and Wi-Fi enrollment remain future work. Another active session or OTA operation returns `busy`; this handshake never interrupts an ongoing OTA.

## Liveness and status

Both peers send `heartbeat` with `session` every second; the panel adds `uptime_ms`. Only a valid heartbeat from the active session or an accepted request renews firmware liveness. The host uses 3.5 seconds and a separate request deadline. Handshake may take at most eight seconds to accommodate USB reset/boot; only hello attempts are repeated during that period.

After each handshake, the host requests a full snapshot and repeats it periodically:

```json
{"v":2,"type":"state.get","id":2,"session":"0123456789abcdef0123456789abcdef"}
```

```json
{"v":2,"type":"state.snapshot","id":2,"session":"0123456789abcdef0123456789abcdef","revision":1,"sampled_uptime_ms":1234,"valid_for_ms":3500,"state":{"self_test_ok":true,"mode":"standalone_demo","desk":null,"monitor":null}}
```

`revision` increases per snapshot within a session, starting at 1. This is an observation revision even when values stay the same. `sampled_uptime_ms` is the panel's 32-bit local timestamp, not a host-synchronized clock. A new boot/session starts a new revision sequence. Deltas are not implemented; full snapshots are the only status form in this small contract.

The host subtracts measured request duration from `valid_for_ms` and publishes its own receipt timestamp. Consumers may use a snapshot only while the remaining lease is valid. `panel-service status` recalculates this even after a service crash or a clock moving backwards. An expired snapshot is returned stale without panel/device status. A heartbeat alone does not make old status fresh.

## Action contract for future adapters

The following is normative for later real controls:

1. `action.request` contains session, unique request ID, `action`, validated `args` and `ttl_ms` (1..3500). TTL starts on receipt by the receiving adapter; the host also uses its own deadline and never sends an already expired command.
2. `action.result` uses the same session and ID. `stage: received` confirms only syntactic receipt; `accepted` only admission by the authorized actuator adapter; `completed` only a demonstrable physical outcome. Without outcome feedback, report `unknown`, never invented `completed`.
3. `rejected`, `failed`, `expired` and `unknown` are explicit terminal outcomes with a fixed `code`. A TCP/USB write or MQTT publish is not completion.
4. Within a session, the future adapter handles duplicate IDs idempotently: identical content returns the same known outcome, different content is rejected. It must not execute the same action again. A session has no transferable pending actions; reconnect starts with empty authorization and a snapshot.
5. Reconnect, transport change, stop, update or expired liveness clears pending movements. No automatic movement retry or replay. Stop behavior must also be enforced on host crash by the component still able to stop.

The current handler returns only `action.result` with `stage: rejected` and `code: unsupported_action` for every `action.request`; it executes nothing and advertises no actions. These future stages/deadlines are a contract, not an implemented MQTT action engine. See issue #10 for capability and idempotency enforcement on the real command route.

## Scope and errors

Demo, provisioning and update commands are not production actions. They are rejected in a v2 session. `state.get` is the only current production request after hello. Unknown messages return `unsupported_message`; missing/different sessions return `session_required`; invalid requests return `invalid_request`. No error text contains credentials or arbitrary peer data.

On disconnect, the host discards session, decoder buffer and outstanding requests. Discovery restarts with the pinned USB identity, followed by handshake and full snapshot. A different or replacement panel is not automatically enrolled.

## Verification

`tests/test_service.py` compiles the actual `ProductionSession` handler with the pinned ArduinoJson library and connects it to the Python service through pseudo-terminals. Coverage includes identity/versions/health, revisions, status freshness, unknown actions, framing isolation and re-enumeration. The firmware build checks USB and Wi-Fi wiring. This is not physical USB, radio, power or NetLink acceptance.

## Read-only device status since 0.7.0

The new `device.state.v1` capability accepts a host `device.state` request with the same session/ID, increasing `revision`, `valid_for_ms` (1–3000), `desk` and `monitor`. Both device fields are explicitly an object or `null`. Without the capability, the host does not send this message. All `action.request` remain rejected; no desk/monitor action is performed.

`desk` contains integer `height_mm` (0–3000) and boolean `fresh`. This is an observation: command limits 620–1270 mm are not used to clamp actual measurements. `monitor` contains the selected numeric `bus` (at most 8 characters), `brightness` (0–100 or null), `power` (`on`/`off`/`standby` or null), `source` (at most 24 visible ASCII characters or null) and boolean `fresh`. Missing measurements are not replaced with defaults. A fixed Waveshare HDMI source is valid read-only status even without source-switch capability.

Firmware validates the entire snapshot before applying it. An invalid, duplicate or older revision replaces nothing and does not renew the data lease. The response is `device.state.ack` with the same session/ID and applied revision. Lease expiry, session loss or a new handshake makes all device values unknown. A heartbeat alone does not renew the data lease. New values do not wake a sleeping screen.

The display shows measured height and brightness/power/input; `fresh:false` gets LAATST BEKEND. Unknown values appear as `--`/Onbekend. Desk/monitor controls, presets and physical demo-reset/scenario gestures are blocked in this mode; local panel settings and navigation remain available. An explicit bench scene can reopen the standalone demo after the production owner has stopped. No automatic fallback to demo values on host loss.

For old hosts, `state.snapshot.state.mode` remains `standalone_demo` before the first `device.state`; afterwards it is `read_only`, including after lease expiry. The updated host core accepts both modes. A new host with old firmware retains status monitoring but sends no device status. Install host and firmware as paired, capability-checked changes.

The webserver retains MQTT status ownership. The upstream host module receives only generic request fields and mode compatibility; the webserver uses its existing SerialX adapter without reintroducing pySerial. This change builds and natively tests firmware 0.7.0; it does not automatically install it on the physical panel.

## Local panel configuration status since 0.8.0

Optional capability `panel.config.status.v1` adds `state.panel_config` to the existing snapshot. It contains schema, saved revision, panel brightness, rotation, dim timeout and bounded storage status. No credentials, desk presets or managed writes. See the [storage and ownership contract](panel-settings.md). Unknown configuration requests remain rejected; this grants no extra device or configuration rights.
