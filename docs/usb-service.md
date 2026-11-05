# USB panel service

The service in this repository replaces the Mac bench program for discovery, enrollment and status monitoring. It runs on Linux without Wi-Fi or internet and monitors one explicitly enrolled panel. It publishes only local sanitized status; MQTT actuation, agent integration, firmware transfer and an HTTP management interface are not present yet.

Firmware 0.6.0 with [protocol v2](production-protocol.md) is required. A panel with the previously installed 0.5.2 cannot complete a production handshake. Firmware has since been installed separately over USB on the prototype and tested with the service; the procedure below installs nothing automatically. Existing v1 tools remain usable when no v2 session is active.

## Start locally

```sh
uv sync --locked
uv run panel ports
uv run panel-service --enrollment .secrets/service-enrollment.json enroll \
  --port <current-usb-port> \
  --panel-id <verified-panel-identity> \
  --usb-serial <serial-from-usb-inventory> \
  --board-revision unverified
uv run panel-service --enrollment .secrets/service-enrollment.json run --status .secrets/service-status.json
```

Use `unverified` only while firmware explicitly reports that revision. This is not evidence of the PCB revision; record actual hardware during physical commissioning before a pilot. A supported board profile does not establish acceptance of every board with the same USB chip.

Enrollment is deliberate: the command requires expected panel identity and USB serial, checks VID/PID and the current port, performs the v2 handshake and only then writes enrollment. It does not scan for an arbitrary panel to trust automatically. Existing enrollment is never overwritten. For a replacement, stop the service and deliberately remove the old enrollment; then identify the new panel again.

A file lock prevents simultaneous enrollment/running with the same configuration. The serial port is opened exclusively. Configuration and status are written atomically with mode 0600. The lock directory and enrollment are locally managed; do not grant unauthorized users write access. One installation uses one enrollment path; do not create parallel managers with separate configuration paths.

## Status and lifecycle

```sh
uv run panel-service status --status .secrets/service-status.json
```

Exit code 0 means unexpired connected status; 1 means absent, stale, stopped or a read/configuration error. The status command does not open the panel and needs no service lock.

`waiting` means discovery is in progress; `connected` follows only after a pinned handshake and a fresh full snapshot. An error removes usable panel/device status and reports a fixed error code. Consumers must always check the snapshot lease; the word `connected` in an old file is insufficient. `panel-service status` checks this even when the service process is no longer running.

Requests and heartbeats are bounded; discovery/reconnect backs off from 1 to at most 15 seconds. A missing panel stays in discovery. Re-enumeration under another tty name is allowed when the pinned USB identity matches. Each opened connection gets a new nonce, empty pending state and a full snapshot request. On SIGTERM/SIGINT the service closes the port and publishes `stopped`; a blocked serial read lasts at most 100 ms. Firmware expires a session with no renewed liveness within 3.5 seconds.

There is no command queue and no retry of real actions. Nothing is flashed. A normal USB open can still trigger a reset through the native USB driver. Do not run bench/capture/flash programs against the same panel simultaneously.

## Linux container

```sh
docker build -t netlink-panel-service:0.6.0 .
```

[The compose example](../deploy/compose.usb.example.yml) is a standalone USB-only example, not a fleet deployment. Set `PANEL_SERIAL_GID` to the numeric group of the host ttyACM device. The image runs as UID/GID 65532, with only that supplementary group, no capabilities, no network and a read-only root filesystem. Only `/data` is writable persistent storage. A volume preserving enrollment/status across recreations is required.

```sh
export PANEL_SERIAL_GID=<numeric-device-group>
docker compose -f deploy/compose.usb.example.yml run --rm panel enroll \
  --port <linux-ttyACM-port> --panel-id <panel-identity> \
  --usb-serial <usb-serial> --board-revision unverified
docker compose -f deploy/compose.usb.example.yml up -d
```

The example exposes host `/dev` read-only to discover new ttyACM names after hotplug. A device-cgroup rule allows only read/write of USB-CDC-ACM major 166; no `privileged`, block-device, raw-USB, GPIO or UART access is needed. DAC/group permissions and enrollment further limit which port is used. The process can see device names; kernel permission covers all ttyACM minors because a reserved minor is not stable across restart/hotplug. Mounting a fixed `devices:` inode is stricter but does not reliably survive re-enumeration. If a fleet does not support that dynamic cgroup rule/mount, host integration must pass specific devices and recreate the container after enumeration changes; do not claim transparent hotplug recovery in that case.

Use the example on a cgroup/Docker host that enforces the access rule; test this on the target NetLink. A different USB chip/driver major requires an explicitly reviewed configuration, not a broader wildcard. `/sys/class/tty` and associated USB identity metadata must be available read-only for pyserial discovery. No access to the desk UART or DDC is needed.

## NetLink integration and physical gate

The service is intended to become its own image/block in the existing fleet-first Balena stack. This PR changes no `netlink_balena` compose file, existing submodule pointer or fleet. The panel service will not be a second agent: agent health, desired state and remote authorization are separate issues.

Start with a free USB data host port on the intended NetLink, separate from the desk UART path. Do not use a power-only cable. Actual power budget, available port and plug-in/reboot behavior must be measured and recorded on that hardware; the Mac prototype does not prove them. If USB power is insufficient, the solution must be explicitly validated; no silent dependency on Wi-Fi or an untested hub.

Still to prove physically on the target NetLink (issues #9 and #24): power, correct port/group/cgroup access, identification, enrollment, container lifecycle and hotplug/reboot with a new tty name. The test must show desk and monitor services remain unaffected. Existing pseudo-terminal tests prove the service path and new handshake, not the physical Linux device/permissions or power layer.

## Checks

```sh
uv run python -m unittest discover -s tests -v
uv tool run --from ruff ruff check .
uv tool run --from ruff ruff format --check .
uv tool run --from platformio==6.1.18 pio run --project-dir firmware
```

Build the firmware once first so the pinned ArduinoJson headers are available for native protocol tests. Tests use their own pseudo-terminals and do not write to the real panel.

## Physical USB trial on the Mac — 4 November 2026

Firmware 0.6.0 from source commit `684205f` was written app-only over USB after checking USB identity, factory backup and active slot. Esptool verified the flash hash. The v1 hello then confirmed the expected image hash, version 0.6.0, VALID and a passing startup self-check.

On the same physical panel, the v2 handshake, board-profile/identity checks, snapshots with revisions 1/2/3 and rejection of unsupported actions passed. The reported board revision deliberately remains `unverified`; desk and monitor remained unknown. No UI actions were injected or real device commands sent.

The first immediate transition after a v1 hello correctly returned `busy`: closing an open USB client does not end the application session immediately. V2 passed after the 3.5-second liveness boundary. For manual enrollment, wait at least four seconds after stopping a bench client; the daemon automatically retries busy responses with backoff. This requires no firmware change.

Actual CLI enrollment succeeded, wrote mode 0600 and refused overwrites. A 15-second service trial produced 14 different fresh revisions; after a clean stop and restart it again produced revision 1 and five fresh revisions in five seconds. A second simultaneous service was rejected in both trials. SIGTERM closed the service and published `stopped`. After a separate forced host-process termination (SIGKILL), the old snapshot was read as stale without usable status after four seconds. A new service restarted at revision 1 and was stopped cleanly after verification.

This proves USB communication with the display from macOS. It is not a physical cable-hotplug, power-failure, endurance or target-NetLink permissions test. Local evidence is under `artifacts/display-0.6.0/verification.json` (deliberately outside Git); the corresponding image and manifest are under `artifacts/releases/`.
