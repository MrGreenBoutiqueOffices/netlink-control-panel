"""Real TLS-PSK handshakes and the common bench protocol over encrypted sockets."""

import json
import secrets
import socket
import ssl
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from netlink_panel.cli import bench
from netlink_panel.protocol import Decoder, encode
from netlink_panel.wifi import CIPHER, TLSStream, load_pairing, psk_context, save_pairing, serve


@unittest.skipUnless(getattr(ssl, "HAS_PSK", False), "Python/OpenSSL does not support TLS-PSK")
class WifiTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_hex(32)
        self.identity = "panel-test"

    def exchange(self, *, client_key=None, client_identity=None, run_bench=False, expected_panel="panel-test"):
        server_raw, client_raw = socket.socketpair()
        server_raw.settimeout(2)
        client_raw.settimeout(2)
        errors = []

        def client():
            try:
                context = psk_context(client_identity or self.identity, client_key or self.key, server=False)
                with client_raw, context.wrap_socket(client_raw) as connection:
                    if not run_bench:
                        connection.sendall(b"authenticated")
                        return
                    connection.settimeout(0.1)
                    decoder = Decoder()
                    linked = False
                    next_heartbeat = 0
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        try:
                            data = connection.recv(4096)
                            if not data:
                                break
                        except TimeoutError:
                            data = b""
                        for message in decoder.feed(data):
                            if message["type"] == "hello":
                                linked = True
                                connection.sendall(
                                    encode(
                                        {
                                            "type": "hello",
                                            "id": message["id"],
                                            "panel_id": self.identity,
                                            "firmware": "0.2.0-simulator",
                                            "simulated": True,
                                            "capabilities": ["demo_state"],
                                        }
                                    )
                                )
                            elif message["type"] == "demo_state":
                                connection.sendall(encode({"type": "ack", "id": message["id"], "ok": True}))
                        if linked and time.monotonic() >= next_heartbeat:
                            connection.sendall(encode({"type": "heartbeat"}))
                            next_heartbeat = time.monotonic() + 0.25
            except OSError as error:
                errors.append(error)

        worker = threading.Thread(target=client, daemon=True)
        worker.start()
        try:
            context = psk_context(self.identity, self.key, server=True)
            with server_raw, context.wrap_socket(server_raw, server_side=True) as connection:
                self.assertEqual(connection.version(), "TLSv1.2")
                self.assertEqual(connection.cipher()[0], CIPHER)
                if run_bench:
                    return bench(
                        device=TLSStream(connection), duration=1.0, expected_panel=expected_panel, transport="wifi"
                    )
                self.assertEqual(connection.recv(64), b"authenticated")
        finally:
            server_raw.close()
            worker.join(timeout=4)
            self.assertFalse(worker.is_alive(), "TLS client must exit")

    def test_pair_key_authenticates_and_encrypts(self):
        self.exchange()

    def test_wrong_key_is_rejected(self):
        with self.assertRaises(ssl.SSLError):
            self.exchange(client_key=secrets.token_hex(32))

    def test_unpaired_identity_is_rejected(self):
        with self.assertRaises(ssl.SSLError):
            self.exchange(client_identity="unpaired")

    def test_same_bench_protocol_over_tls(self):
        result = self.exchange(run_bench=True)
        self.assertEqual(result["transport"], "wifi")
        self.assertFalse(result["hardware_command_sent"])

    def test_authenticated_but_mismatching_application_identity_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "identity does not match"):
            self.exchange(run_bench=True, expected_panel="another-panel")

    def test_pairing_file_is_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "panel.json"
            pairing = {"panel_id": self.identity, "key": self.key, "host": "192.168.1.20", "port": 8769}
            save_pairing(path, pairing)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_pairing(path), pairing)
            self.assertNotIn("password", json.loads(path.read_text()))
            with self.assertRaises(FileExistsError):
                save_pairing(path, pairing)

    def test_incomplete_pairing_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "panel.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "incomplete"):
                load_pairing(path)

    def test_server_accepts_a_paired_panel_after_a_bad_tls_client(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "panel.json"
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            save_pairing(path, {"panel_id": self.identity, "key": self.key, "host": "127.0.0.1", "port": port})
            results = []
            # Budget for a failed TLS handshake (up to 3 s) plus a full 4 s
            # application session; 6 s made this dependent on machine load.
            args = SimpleNamespace(pairing=path, bind=None, duration=12, session_duration=4, height=740, brightness=60)
            worker = threading.Thread(target=lambda: results.append(serve(args)), daemon=True)
            worker.start()

            def connect():
                deadline = time.monotonic() + 2
                while True:
                    try:
                        return socket.create_connection(("127.0.0.1", port), timeout=2)
                    except ConnectionRefusedError:
                        if time.monotonic() > deadline:
                            raise
                        threading.Event().wait(0.01)

            try:
                with connect() as bad:
                    bad.sendall(b"not a TLS client")
                context = psk_context(self.identity, self.key, server=False)
                with connect() as raw, context.wrap_socket(raw) as connection:
                    decoder = Decoder()
                    linked = False
                    next_heartbeat = 0
                    while True:
                        data = connection.recv(4096)
                        if not data:
                            break
                        for message in decoder.feed(data):
                            if message["type"] == "hello":
                                linked = True
                                connection.sendall(
                                    encode(
                                        {
                                            "type": "hello",
                                            "id": message["id"],
                                            "panel_id": self.identity,
                                            "firmware": "0.2.0-simulator",
                                            "simulated": True,
                                            "capabilities": ["demo_state"],
                                        }
                                    )
                                )
                            elif message["type"] == "demo_state":
                                connection.sendall(encode({"type": "ack", "id": message["id"], "ok": True}))
                        if linked and time.monotonic() >= next_heartbeat:
                            connection.sendall(encode({"type": "heartbeat"}))
                            next_heartbeat = time.monotonic() + 0.5
            finally:
                worker.join(timeout=14)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results, [0])
