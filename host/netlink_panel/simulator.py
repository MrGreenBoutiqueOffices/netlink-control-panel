"""A pseudo-terminal panel for testing the real USB serial host path."""

import os
import select
import threading
import time
import tty

from .protocol import Decoder, encode


class SimulatedPanel:
    def __init__(self, *, respond=True):
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.port = os.ttyname(self.slave)
        self.respond = respond
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=2)
        os.close(self.master)
        os.close(self.slave)

    def run(self):
        decoder = Decoder()
        next_heartbeat = float("inf")
        last_host = 0.0
        while not self.stop.is_set():
            ready, _, _ = select.select([self.master], [], [], 0.05)
            if ready:
                for request in decoder.feed(os.read(self.master, 4096)):
                    if not self.respond:
                        continue
                    kind = request["type"]
                    response = None
                    if kind == "hello":
                        response = {
                            "type": "hello",
                            "id": request["id"],
                            "panel_id": "simulated-panel",
                            "firmware": "0.1.0",
                            "simulated": True,
                            "capabilities": ["demo_state"],
                        }
                        next_heartbeat = time.monotonic()
                        last_host = next_heartbeat
                    elif kind == "heartbeat":
                        last_host = time.monotonic()
                    elif kind == "demo_state":
                        height, brightness = request.get("height_mm"), request.get("brightness")
                        valid = (
                            type(height) is int
                            and 500 <= height <= 1300
                            and type(brightness) is int
                            and 0 <= brightness <= 100
                        )
                        response = {"type": "ack", "id": request["id"], "ok": valid}
                    else:
                        response = {"type": "ack", "id": request.get("id", 1), "ok": False}
                    if response:
                        os.write(self.master, encode(response))
            now = time.monotonic()
            if self.respond and now >= next_heartbeat and now - last_host < 3.5:
                os.write(self.master, encode({"type": "heartbeat", "uptime_ms": int(now * 1000)}))
                next_heartbeat = now + 0.5
