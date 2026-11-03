"""Opt-in physical inactive-slot recovery checks; no activation or reboot."""

import argparse
import base64
import time
from pathlib import Path

from hardware_robustness import Harness
from netlink_panel.ota import inspect_image
from netlink_panel.protocol import encode

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--firmware", type=Path, required=True, help="Image currently running on the panel")
parser.add_argument("--pairing", type=Path, default=Path(".secrets/panel.json"))
parser.add_argument("--report", type=Path, default=Path("artifacts/ota-recovery-faults.json"))
parser.add_argument(
    "--write-inactive-slot",
    action="store_true",
    required=True,
    help="Explicitly authorize two partial physical flash transfers",
)
args = parser.parse_args()
image = args.firmware.read_bytes()
manifest = inspect_image(image)
h = Harness(args.pairing, args.report)
try:
    for test in ("server_unavailable_5s", "lost_chunk_ack"):
        connection, peer, hello, _ = h.connect(timeout=40)
        with connection:
            assert hello["firmware"] == manifest["version"] and hello["ota"]["state"] == "valid"
            assert hello["ota"]["image_sha256"] == manifest["image_sha256"]
            assert "ota_resume_v1" in hello["capabilities"]
            before = hello["uptime_ms"]
            assert peer.request("ota_begin", **manifest)["next_offset"] == 0
            for offset in range(0, 4096, 512):
                assert (
                    peer.request(
                        "ota_chunk", offset=offset, data=base64.b64encode(image[offset : offset + 512]).decode()
                    )["next_offset"]
                    == offset + 512
                )
            if test == "lost_chunk_ack":
                # Send but deliberately do not read its ACK. The reconnect must
                # resolve whether this chunk reached flash; no blind replay.
                peer.stream.write(
                    encode(
                        {
                            "type": "ota_chunk",
                            "id": 1000,
                            "offset": 4096,
                            "data": base64.b64encode(image[4096:4608]).decode(),
                        }
                    )
                )
                time.sleep(0.2)
        if test == "server_unavailable_5s":
            h.listener.close()
            time.sleep(5)
            h.open_listener()
        connection, peer, hello, latency = h.connect(timeout=40)
        with connection:
            assert hello["uptime_ms"] > before, "Unexpected panel reboot"
            assert hello["ota"]["receiving"] is True
            response = peer.request("ota_begin", **manifest)
            offset = response["next_offset"]
            assert offset in ([4096] if test == "server_unavailable_5s" else [4096, 4608]), offset
            assert (
                peer.request("ota_chunk", offset=offset, data=base64.b64encode(image[offset : offset + 512]).decode())[
                    "next_offset"
                ]
                == offset + 512
            )
            peer.request("ota_abort")
            final = peer.request("hello")
            assert final["ota"]["receiving"] is False and final["ota"]["state"] == "valid"
            assert final["ota"]["image_sha256"] == manifest["image_sha256"]
            h.record(
                test,
                resumed_offset=offset,
                reconnect_seconds=round(latency, 2),
                image_sha256=manifest["image_sha256"],
                state="valid",
                receiving=False,
            )
finally:
    h.listener.close()
