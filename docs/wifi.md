# Wireless testing with the Mac

Status 2026-11-03: Wi-Fi is implemented since bench firmware 0.2.0; version 0.3.0 adds [application updates over Wi-Fi](ota.md). Firmware has been tested on the physical display; current OTA results are in the [recovery report](ota-recovery-2026-11-03.md). USB remains available and takes priority when a USB test session is active.

## One-time setup over USB

The initial firmware installation and Wi-Fi setup require a USB data cable. Afterwards the panel can run wireless tests with power only. First identify the board and preserve the factory flash; see the project README before overwriting firmware.

Build and load the Wi-Fi firmware with PlatformIO following the README. Then open a terminal in this project directory:

```sh
uv run panel ports
uv run panel wifi setup --port <usb-port> --host <mac-ip-address>
```

For `--host`, use this Mac's local IPv4 address, for example `192.168.1.20`. Find it in macOS network details. This is the address the panel uses to reach your Mac; `127.0.0.1`, `localhost` and `0.0.0.0` are unsuitable.

The program asks for the 2.4-GHz Wi-Fi network name, then the password with hidden input. The password is not put in shell history or logs and is not stored on the Mac. Firmware stores network details and the unique connection key in NVS so the panel can reconnect after power-on. NVS/flash is not encrypted in this bench firmware.

The Mac stores only panel identity, server address, port and a random key in `.secrets/panel.json`, with file permissions `0600`. This directory is in `.gitignore`. Do not share or commit this file. The file is deliberately created before configuration transfer: the new key remains available even if the USB acknowledgement is lost.

If Wi-Fi settings or the Mac address change, configure again using a new file:

```sh
uv run panel wifi setup --port <usb-port> --host <mac-ip-address> --pairing .secrets/panel-nieuw.json
```

Firmware replaces the old configuration once storage is confirmed. An existing local pairing file is not silently overwritten.

## Start a wireless test

Ensure the Mac and panel can reach each other on the local network. Start:

```sh
uv run panel wifi serve --duration 300 --height 740 --brightness 60
```

For a different pairing file:

```sh
uv run panel wifi serve --pairing .secrets/panel-nieuw.json --duration 300
```

By default, the program listens only on the configured Mac address and TCP port 8769. If macOS requests local-network access, it is needed for the panel to connect. Wi-Fi client isolation or a firewall can block local traffic; no internet or cloud route is required.

The panel makes an outgoing TLS connection to the Mac. The display shows connection status and its own local IP address. Demo values appear once the Mac program completes the handshake. Tapping buttons produces diagnostic events in the terminal; no desk or monitor commands are sent.

The server runs for five minutes by default; each test session lasts thirty seconds by default. The panel may reconnect afterwards. Stop with Ctrl+C. Without a heartbeat, buttons are disabled and the session expires after about 3.5 seconds. This may happen sooner when the TCP connection closes.

Do not run a simultaneous USB bench when testing Wi-Fi. Only an active USB handshake takes over control; a USB cable used only for power does not prevent Wi-Fi. A transport change always requires a new handshake. Touches are neither carried over nor replayed.

## Keep USB and clear Wi-Fi

USB also works when the Wi-Fi network or Mac is unreachable:

```sh
uv run panel bench --port <usb-port> --duration 30
uv run panel wifi forget --port <usb-port>
```

`forget` removes the saved Wi-Fi and TLS key on the panel and disables Wi-Fi. The local pairing file is retained; remove it yourself when no longer needed.

## Security and limitations

- Both sides use a unique random 256-bit key for TLS 1.2 PSK authentication and AES-128-GCM encryption. There is no anonymous/plaintext mode or `setInsecure()` route on the panel. The PSK suite has no forward secrecy; this is a local bench solution.
- Configuration and clearing are allowed only over USB, not Wi-Fi. The server also verifies panel identity in the application protocol.
- For Wi-Fi, the Mac program requires Python 3.13+ with OpenSSL PSK support. The pinned Python 3.14 environment on this Mac supports it. USB continues to work on Python 3.11+.
- Setup does not use an open configuration access point. No production credentials from Signing, Home Assistant or NetLink are reused.
- This is the wireless connection to the Mac test program. [Wireless application updates](ota.md) are implemented since 0.3.0. A managed NetLink service, automatic configuration rollback and full recovery are not implemented yet.
- TLS handshakes, incorrectly configured keys and the shared protocol are tested locally; radio range, Wi-Fi recovery, power failure, touch and USB/Wi-Fi priority on the real panel remain physical acceptance tests.

Sources: [ESP32 Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html), [ESP32 Preferences/NVS](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/preferences.html), [WiFiClientSecure 2.0.14](https://github.com/espressif/arduino-esp32/blob/2.0.14/libraries/WiFiClientSecure/src/WiFiClientSecure.h), [Python TLS-PSK callbacks](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.set_psk_server_callback).
