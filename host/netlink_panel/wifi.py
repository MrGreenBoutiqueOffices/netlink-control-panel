"""USB provisioning and a local, mutually authenticated TLS-PSK bench server."""

import getpass
import ipaddress
import json
import os
import secrets
import socket
import ssl
import time
from pathlib import Path

import serial

from .cli import bench, report
from .protocol import Decoder, encode

CIPHER = "PSK-AES128-GCM-SHA256"
DEFAULT_PAIRING = Path(".secrets/panel.json")


def psk_context(panel_id, key_hex, *, server):
    if not getattr(ssl, "HAS_PSK", False):
        raise RuntimeError("Wi-Fi bench needs Python 3.13+ with OpenSSL PSK support; use uv run --python 3.14")
    if not isinstance(panel_id, str) or not panel_id.isascii() or not 1 <= len(panel_id) <= 32:
        raise ValueError("Invalid panel identity")
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        raise ValueError("Pairing key must be 32 random bytes encoded as hex")
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError("Pairing key must contain exactly 32 bytes")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers(CIPHER)
    if server:
        context.set_psk_server_callback(lambda identity: key if identity == panel_id else b"")
    else:
        # Certificate validation is replaced by mutual authentication with the
        # per-panel pre-shared key. No anonymous/plaintext transport is allowed.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_psk_client_callback(lambda hint: (panel_id, key))
    return context


class TLSStream:
    def __init__(self, connection):
        self.connection = connection
        connection.settimeout(0.1)

    def read(self, size):
        try:
            data = self.connection.recv(size)
        except TimeoutError:
            return b""
        if not data:
            raise ConnectionError("Panel closed the Wi-Fi session")
        return data

    def write(self, data):
        self.connection.sendall(data)
        return len(data)


def request(device, message, *, timeout=8):
    decoder = Decoder()
    deadline = time.monotonic() + timeout
    device.write(encode(message))
    retry = time.monotonic() + 1
    while time.monotonic() < deadline:
        for response in decoder.feed(device.read(4096)):
            if response.get("id") == message["id"] and response["type"] in ("hello", "ack"):
                return response
        if message["type"] == "hello" and time.monotonic() >= retry:
            device.write(encode(message))
            retry = time.monotonic() + 1
    raise RuntimeError("USB request timed out; inspect the device before retrying")


def save_pairing(path, pairing):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive create avoids replacing another panel's key or following an
    # existing symlink. Never put Wi-Fi passwords in this file or in stdout.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(pairing, output, indent=2)
        output.write("\n")


def load_pairing(path):
    pairing = json.loads(path.read_text())
    if not isinstance(pairing, dict) or not {"panel_id", "key", "host", "port"} <= pairing.keys():
        raise ValueError("Pairing file is incomplete")
    psk_context(pairing["panel_id"], pairing["key"], server=True)
    address = ipaddress.IPv4Address(pairing["host"])
    if address.is_unspecified or address.is_multicast:
        raise ValueError("Pairing host must be the Mac's reachable IPv4 address")
    if type(pairing["port"]) is not int or not 1024 <= pairing["port"] <= 65535:
        raise ValueError("Invalid server port")
    return pairing


def provision(args):
    host = ipaddress.IPv4Address(args.host)
    if host.is_unspecified or host.is_multicast or host.is_loopback:
        raise ValueError("Use the Mac's local-network IPv4 address, not localhost or 0.0.0.0")
    if not 1024 <= args.server_port <= 65535:
        raise ValueError("Server port must be 1024..65535")
    if args.pairing.exists():
        raise ValueError("Pairing file already exists; use another --pairing path to reconfigure")
    ssid = input("Wifi-netwerk (2,4 GHz): ")
    password = getpass.getpass("Wifi-wachtwoord (niet opgeslagen op de Mac): ")
    if not 1 <= len(ssid.encode()) <= 32 or not 8 <= len(password.encode()) <= 63:
        raise ValueError("Use an SSID of 1..32 bytes and a WPA2/WPA3 passphrase of 8..63 bytes")
    with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=1) as device:
        hello = request(device, {"type": "hello", "id": 1})
        if not isinstance(hello.get("capabilities"), list) or "wifi_provision" not in hello["capabilities"]:
            raise RuntimeError("First flash the Wi-Fi-enabled bench firmware via USB")
        pairing = {
            "panel_id": hello["panel_id"],
            "host": str(host),
            "port": args.server_port,
            "key": secrets.token_hex(32),
        }
        psk_context(pairing["panel_id"], pairing["key"], server=True)
        # Save before sending, so a lost acknowledgement does not lose the key.
        save_pairing(args.pairing, pairing)
        response = request(
            device,
            {
                "type": "wifi_config",
                "id": 2,
                "ssid": ssid,
                "password": password,
                "host": str(host),
                "port": args.server_port,
                "key": pairing["key"],
            },
        )
        if response.get("ok") is not True:
            raise RuntimeError("Panel rejected Wi-Fi configuration; pairing file retained for inspection")
    report(
        "wifi_configured",
        panel_id=pairing["panel_id"],
        pairing_file=str(args.pairing),
        host=str(host),
        port=args.server_port,
    )
    return 0


def serve(args):
    pairing = load_pairing(args.pairing)
    context = psk_context(pairing["panel_id"], pairing["key"], server=True)
    bind = args.bind or pairing["host"]
    deadline = time.monotonic() + args.duration
    successful = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((bind, pairing["port"]))
        listener.listen(1)
        listener.settimeout(0.5)
        report("wifi_listening", bind=bind, port=pairing["port"], panel_id=pairing["panel_id"])
        while time.monotonic() < deadline:
            try:
                raw, _ = listener.accept()
            except TimeoutError:
                continue
            try:
                with raw:
                    raw.settimeout(3)
                    with context.wrap_socket(raw, server_side=True) as connection:
                        if deadline - time.monotonic() < 4:
                            break
                        bench(
                            device=TLSStream(connection),
                            expected_panel=pairing["panel_id"],
                            transport="wifi",
                            duration=min(args.session_duration, deadline - time.monotonic()),
                            height=args.height,
                            brightness=args.brightness,
                        )
                        successful += 1
            except (OSError, RuntimeError) as error:
                # A bad/unpaired client must not terminate the server. Avoid
                # dumping protocol data or credentials in error output.
                report("wifi_session_failed", reason=type(error).__name__)
    report("wifi_server_stopped", successful_sessions=successful)
    return 0 if successful else 1


def add_wifi_commands(commands):
    wifi = commands.add_parser("wifi", help="Configure Wi-Fi over USB or run the TLS bench server")
    subcommands = wifi.add_subparsers(dest="wifi_command", required=True)
    setup = subcommands.add_parser("setup", help="Prompt for Wi-Fi credentials; provision via USB")
    setup.add_argument("--port", required=True)
    setup.add_argument("--host", required=True, help="This Mac's reachable LAN IPv4 address")
    setup.add_argument("--server-port", type=int, default=8769)
    setup.add_argument("--pairing", type=Path, default=DEFAULT_PAIRING)
    forget = subcommands.add_parser("forget", help="Disable Wi-Fi and erase its panel credentials via USB")
    forget.add_argument("--port", required=True)
    server = subcommands.add_parser("serve", help="Accept encrypted connections from the paired panel")
    server.add_argument("--pairing", type=Path, default=DEFAULT_PAIRING)
    server.add_argument("--bind", help="Local bind address; defaults to paired Mac IPv4")
    server.add_argument("--duration", type=float, default=300)
    server.add_argument("--session-duration", type=float, default=30)
    server.add_argument("--height", type=int, default=740)
    server.add_argument("--brightness", type=int, default=60)
    update = subcommands.add_parser("update", help="Send an application image over TLS, then verify its reboot")
    update.add_argument("--firmware", type=Path, default=Path("firmware/.pio/build/panel-bench/firmware.bin"))
    update.add_argument("--pairing", type=Path, default=DEFAULT_PAIRING)
    update.add_argument("--bind", help="Local bind address; defaults to paired Mac IPv4")
    update.add_argument("--timeout", type=float, default=600)
    update.add_argument("--receipt", type=Path, default=Path("artifacts/last-update.json"))


def run_wifi(args):
    if args.wifi_command == "update":
        from .ota import update

        return update(args)
    if args.wifi_command == "setup":
        return provision(args)
    if args.wifi_command == "forget":
        with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=1) as device:
            hello = request(device, {"type": "hello", "id": 1})
            if not isinstance(hello.get("capabilities"), list) or "wifi_provision" not in hello["capabilities"]:
                raise RuntimeError("Panel does not advertise Wi-Fi provisioning")
            response = request(device, {"type": "wifi_clear", "id": 2})
            if response.get("ok") is not True:
                raise RuntimeError("Panel did not confirm erasing Wi-Fi credentials")
        report("wifi_forgotten", local_pairing_file_retained=True)
        return 0
    if not 4 <= args.duration <= 3600 or not 4 <= args.session_duration <= 3600:
        raise ValueError("Durations must be 4..3600 seconds")
    if not 500 <= args.height <= 1300 or not 0 <= args.brightness <= 100:
        raise ValueError("Height must be 500..1300 mm and brightness 0..100")
    return serve(args)
