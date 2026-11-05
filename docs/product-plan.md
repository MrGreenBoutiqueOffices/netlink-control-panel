# NetLink control panel: USB with optional Wi-Fi

Current decision, 2026-11-05: the panel will own its update lifecycle and download signed firmware independently over Wi-Fi. Webserver update integration and host-fed routine updates are outside issue #15; USB remains available for installation and recovery. See [the current update design](signed-updates.md#besluit-het-paneel-beheert-zijn-updates). The proposal below is historical; its panel-service and host-owned update assumptions are superseded. Autonomous download and local boot confirmation are not implemented yet.

Status: proposal, 2026-10-24. No panel firmware, USB service, deployment, or physical acceptance is delivered by this document.


Implementation update, 2026-11-03: the user requested Wi-Fi immediately for easier testing. Bench firmware 0.2.0 now includes USB provisioning, a TLS-PSK connection to the Mac test server, and shared USB/Wi-Fi application messages. Wi-Fi moved ahead of the original phase order. Physical radio/transport/recovery acceptance and wireless firmware updates remain outstanding. See [Wi-Fi bench instructions](wifi.md).


Implementation update, 2026-11-03 (OTA): firmware/host 0.3.0 adds application-only Wi-Fi updates through the paired TLS-PSK session, inactive-slot writes, image/hash validation, and explicit post-reboot confirmation. Local protocol/TLS tests and the firmware build pass. Independent release signing and physical flash/power-loss/rollback acceptance remain outstanding. See [OTA instructions](ota.md).

## Product goal and requirements

Add a compact touchscreen at the desk edge for desk and monitor control. The first hardware candidate is the LILYGO T-Display S3 Long.

The user set two requirements:

1. Use a direct USB connection to the NetLink as the default, preferably with one cable carrying power and data. USB operation must not depend on Wi-Fi. Also support optional Wi-Fi operation, for example for a panel placed elsewhere at home.
2. Manage and update the panel remotely through the NetLink, including recovery after a failed update without someone pressing buttons at the desk.

The NetLink needs its existing upstream connection for remote management. Local desk and monitor control must continue without internet. When upstream connectivity returns, management must reconcile the reported and desired panel state.

## First version

- Show actual desk height and connection state.
- Provide desk controls supported by the attached controller. Offer sit/stand targets only where the current desk implementation supports them.
- Provide monitor brightness and power controls where the attached monitor supports them.
- Allow remote configuration of language, panel brightness, and idle dimming.
- Report panel identity, hardware revision, firmware version, protocol version, health, configuration revision, and update outcome.
- Support remote application firmware updates and rollback.

USB is the first implementation and hardware acceptance path. Optional Wi-Fi is part of the product plan and must reuse the same control, management, and update behavior; it is not required to complete the USB bench prototype.

Booking status, check-in, personal profiles, and sit/stand reminders follow after the USB and recovery requirements pass. They require separate decisions about business data, authorization, and storage.

## Proposed architecture

```text
Existing remote management / Balena fleet deployment
                         |
                         v
              NetLink panel service
                 |             |
          USB or Wi-Fi     Local MQTT
          (USB default)        |
                 |       Existing desk/display services
                 v
           LILYGO firmware
           Display + touch
```

The panel service owns discovery, USB and optional Wi-Fi transport, the shared panel protocol, configuration delivery, firmware transfer, and bounded recovery. It translates supported panel actions to the existing local MQTT commands and sends confirmed state back to the panel. It does not open the desk UART or perform DDC/CI itself.

The agent retains ownership of device sync, aggregate system health, and recovery policy. Define a bounded interface between the agent and panel service before adding remote actions; the panel service must not become a second independent supervisor.

No panel cloud connection or existing Signing/Home Assistant bearer tokens are required on the panel. USB-only installations do not require Wi-Fi credentials. Wireless installations need local Wi-Fi provisioning and a dedicated enrolled panel identity. Start with one panel per NetLink and explicitly enroll its identity. A replacement must be detected and enrolled before receiving configuration or firmware.

### Optional Wi-Fi operation

- Connect to the paired NetLink over the local network; internet is not required for local controls. The panel needs a separate power source when USB is not connected to the NetLink.
- Reuse the application protocol and NetLink panel service for actions, state, settings, diagnostics, and firmware transfer. Choose the network transport during implementation; do not create a second desk-control implementation.
- Provision the network and NetLink pairing locally, preferably over USB, with a deliberate local recovery/setup flow for installations without a nearby NetLink USB port. Keep credentials out of logs and use an authenticated, encrypted connection with verified peer identity.
- Default to USB when connected to the enrolled NetLink. Allow an explicit wireless mode for installations using USB only for power. An unrelated USB host must not receive control or update access.
- Permit only one active control session per panel. A change of transport requires a fresh handshake and state snapshot; expire movement authorization and discard pending movement actions before switching. Do not silently continue an active movement through Wi-Fi fallback.
- Report the selected transport and connection quality so remote diagnostics can distinguish panel, USB, and wireless faults.
- Provide firmware updates and post-boot validation over Wi-Fi as well as USB. A Wi-Fi-only installation must retain a working image after a failed update, including recovery from unusable candidate network settings. Diagnose full loss of wireless access separately: recovery that requires a USB cable at the desk does not meet unattended wireless recovery acceptance.

Prove wireless update and recovery behavior before treating Wi-Fi-only installations as remotely recoverable. USB remains the preferred service connection when physical access is available.

The exact USB host port and available power budget depend on the NetLink hardware revision and must be recorded during the bench test. A panel fault or update must not interrupt the existing desk UART or monitor services.

## Firmware and shared transport contract

Use ESP-IDF with LVGL as the initial direction, subject to validating the manufacturer display/touch examples against the actual purchased board revision. Keep the USB interface available during normal operation and recovery. Implement USB first, keeping the application protocol independent of transport so optional Wi-Fi can use the same firmware and behavior. Wi-Fi stays disabled until explicitly configured.

Define and test a versioned protocol before implementing the control UI:

| Message group | Required behavior |
| --- | --- |
| Handshake | Panel identity, board revision, firmware version, protocol range, capabilities, boot reason, and running image status |
| Liveness | Bounded heartbeat, stale-state indication, and reconnection handshake |
| State | Full snapshot on reconnect, then revisions/deltas; distinguish confirmed device state from requested state |
| Actions | Correlation ID, explicit acceptance/rejection, bounded deadline, and actual outcome where supported by the existing command path |
| Configuration | Versioned settings with validation and acknowledgement of the applied revision |
| Update | Manifest, transfer progress, integrity validation, activation, post-boot confirmation, and failure reason |

Choose framing, message size limits, and encoding after a USB throughput test. Keep logs separate from protocol frames. Reject unknown actions and incompatible protocol versions. Do not treat transport delivery as proof that a desk or monitor command completed.

Discover the enrolled panel by USB identity and handshake, not a fixed `/dev/ttyACM0` number. Handle disappearance and re-enumeration during unplugging, rebooting, and flashing. USB permissions must cover those transitions without granting unrelated host-device access.

### Desk movement and loss of connection

First inspect the current desk controller's movement/stop behavior. Continuous press-to-move controls are allowed only once bounded stopping has been demonstrated on the real command path.

- Releasing touch requests stop immediately.
- Losing the active USB/Wi-Fi connection, a heartbeat, the panel process, or the NetLink panel service must expire movement authorization at the component that can still stop the desk.
- A UI timer alone is insufficient: if the host service crashes, it cannot send stop.
- Never replay movement actions after reconnecting or after an update.
- Updates require an idle desk and inhibit new panel movement actions until the panel is ready again.

If the existing controller cannot support those guarantees, restrict the initial UI to proven bounded target movements until the control path is improved. Keep the original physical desk controls available during development and acceptance.

## Remote management and release ownership

For the first pilot, distribute a pinned panel firmware artifact and compatibility manifest with the NetLink panel-service image through the existing Balena fleet release flow. This gives a concrete remote delivery route without assuming that a new operations UI already exists.

The manifest identifies the artifact digest, signature, supported board revisions, firmware version, and supported host protocol range. Persist the last update attempt and actual observed version on the NetLink so a host restart can reconcile the outcome.

Later management UI work can expose desired configuration, reported version, health, restart, and update progress through existing authenticated device-management mechanisms. Define authorization and delivery for those actions explicitly; do not assume current agent sync or eKuiper rules already carry arbitrary panel commands.

Use existing journal logging and `monitor-metrics` for bounded diagnostics. Preserve the NetLink telemetry identity described in [Device telemetry in PostHog](../infra/posthog-device-telemetry.md); do not add a separate telemetry shipper. Decide whether the panel is configured as required or optional before it affects aggregate health.

## Firmware update and recovery

Normal application updates use two firmware slots and ESP-IDF image validation/rollback, with the image bytes transported over the active USB or Wi-Fi connection by the panel service. The ESP-IDF OTA partition mechanism does not require Wi-Fi; both panel-service transfer paths are new implementation work.

1. Validate hardware revision, protocol compatibility, artifact signature, and digest before activation.
2. Transfer to the inactive application slot, leaving the current image bootable if transfer is interrupted.
3. Validate the completed image and activate it.
4. Boot the candidate under a watchdog. Validate display/touch initialization and a compatible host handshake before confirming the image.
5. If validation fails, reset into the previous valid application and report the outcome. Define a bounded confirmation timeout so an unconfirmed image cannot remain stuck indefinitely.

Keep bootloader and partition-table changes out of routine panel updates. Provision the initial partition layout and verification material at the bench.

USB Serial/JTAG flashing is a separate recovery route, not the normal update mechanism. Espressif supports automatic download-mode entry, but disabling/reconfiguring USB in firmware can make manual BOOT/RESET necessary. Therefore, stock-board unattended recovery is an open hardware acceptance gate.

Test the actual board for recovery from an application hang, boot loop, and unavailable USB interface. If native USB recovery is insufficient, evaluate a serviceable harness exposing reset/boot and an independent flashing path. Do not claim full remote recovery until that path also passes; additional wiring may be necessary alongside USB.

A Balena rollback does not automatically revert external panel flash. The host and panel must support an explicitly documented compatibility window, and an older host must reject incompatible panel firmware safely. Never automatically alternate between upgrades and downgrades on every restart. Firmware rollback policy must also account for signature/security-version restrictions.

## Delivery sequence and acceptance

| Phase | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1. Bench feasibility | Exact board/NetLink revisions, cable and power measurements, minimal USB firmware, host discovery and recovery experiments | Power/data over one cable; panel reconnects after hotplug and both-device restarts; unattended recovery route demonstrated |
| 2. Protocol and simulator | Versioned contract, simulated panel, host bridge with mocked MQTT | Reject malformed/incompatible messages; reconnect restores state; stale commands are not replayed; command outcomes remain distinct from delivery |
| 3. Local controls | LVGL height/status screen and capability-based desk/monitor controls | Real desk and monitor operation; stop guarantees pass for disconnect, service crash, and stuck touch; local use survives internet loss |
| 4. Managed updates | Pinned artifacts, signed-image verification, dual-slot updates, persisted results and compatibility checks | Remote success, interrupted transfer, power loss during staging/activation/first boot, invalid image, failed self-test, and host rollback tested |
| 5. Optional Wi-Fi | Local network provisioning, authenticated pairing, shared-protocol network transport, and explicit transport selection | Local operation without internet; stop on network loss; no duplicate actions with both transports connected; remote updates and failed-update/network-setting recovery without USB intervention |
| 6. Pilot | Enclosure, mounting, dimming, documented install/replacement flow and fleet telemetry | Multiple desks run through daily use, remote update, panel replacement, and recovery; operator can identify actual version and failure reason; USB and wireless acceptance recorded separately |

Before hardware arrives, phase 2 can start with contract design and simulation. Physical USB, power, touch behavior, and recovery acceptance remain outstanding regardless of automated test results.

## Repository boundaries

- This repository owns stack wiring, firmware artifact pins, rollout documentation, and acceptance evidence.
- Panel firmware and the reusable host service need an explicit source/release home before implementation; use a service repository/block if following the existing block model.
- Desk changes, if necessary for movement expiry, belong in `netlink-desk`.
- Agent health/management integration belongs in `netlink-agent`; management UI work belongs in its actual frontend repository.
- Preserve existing submodule pointers unless explicitly requested to update them.

## Evidence and unresolved questions

Manufacturer and chip documentation establish feasibility, not acceptance on our hardware:

- [LILYGO T-Display S3 Long source and examples](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long): USB programming/serial support, display/touch examples, and manual recovery procedure.
- [Espressif USB Serial/JTAG console](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32s3/api-guides/usb-serial-jtag-console.html): serial transport, automatic download mode, and limitations when firmware disables USB.
- [Espressif application update and rollback](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/ota.html): inactive application slots, image validation, and post-boot confirmation.

Open before implementation: exact purchased board revision, available NetLink USB host/power, unattended recovery wiring, current desk stop semantics, compatible display/touch library versions, firmware/service repository ownership, host/panel compatibility policy, and wireless provisioning/transport/recovery design.
