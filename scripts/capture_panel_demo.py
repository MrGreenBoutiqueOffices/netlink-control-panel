"""Read the actual demo framebuffer over USB or paired TLS and check local simulated interactions.

Changes only local demo state; never sends desk/monitor commands or writes firmware.
"""

import argparse
import base64
import json
import struct
import time
from contextlib import ExitStack
from pathlib import Path

import serial
from hardware_robustness import Harness
from netlink_panel.ota import Peer, inspect_image
from netlink_panel.wifi import load_pairing, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="USB port; omit to read over the existing paired TLS connection")
    parser.add_argument("--pairing", type=Path, default=Path(".secrets/panel.json"))
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument(
        "--scenes",
        default=",".join(str(scene) for scene in range(1, 26)),
        help="Comma-separated reference scene numbers to capture",
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/display-demo"))
    args = parser.parse_args()
    pairing = load_pairing(args.pairing)
    manifest = inspect_image(args.firmware.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"frames": [], "checks": [], "capture_kind": "device_framebuffer_not_camera_photo"}
    with ExitStack() as stack:
        if args.port:
            port = serial.Serial(port=None, baudrate=115200, timeout=0.05, write_timeout=2)
            port.dtr = True
            port.rts = False
            port.port = args.port
            stack.enter_context(port)
            hello = request(port, {"type": "hello", "id": 1}, timeout=15)
            peer = Peer(port)
            peer.sequence = 1
            report["transport"] = "usb"
        else:
            harness = Harness(args.pairing, args.output / "session.json")
            stack.callback(harness.listener.close)
            connection, peer, hello, latency = harness.connect(timeout=40)
            stack.enter_context(connection)
            report["transport"] = "wifi_tls"
        assert hello["panel_id"] == pairing["panel_id"]
        assert hello["ota"]["image_sha256"] == manifest["image_sha256"] and hello["ota"]["state"] == "valid"
        assert hello["self_test_ok"] is True and "demo_ui_v1" in hello["capabilities"]
        report["initial_hello"] = hello
        expected = [
            "bureau",
            "bevestigen",
            "bewegen",
            "offline",
            "menu",
            "monitor",
            "voorkeuren",
            "paneel",
            "paneel_gedraaid",
            "opstarten",
            "verbinden",
            "bijwerken",
            "bijgewerkt",
            "update_mislukt",
            "obstakel",
            "afstellen",
            "ruststand",
            "updates",
            "bureau",
            "bureau",
            "updates",
            "updates",
            "updates",
            "updates",
            "welkom",
        ]
        selected = [int(value) - 1 for value in args.scenes.split(",")]
        if not selected or any(value < 0 or value > 24 for value in selected):
            raise ValueError("Scenes must be 1..25")
        for scene in selected:
            name = expected[scene]
            result = peer.request("demo_ui", op="scene", scene=scene)
            if result.get("screen") != name:
                raise RuntimeError("Unexpected selected screen")
            pixels = bytearray()
            snapshot_id = None
            snapshot_screen = None
            for offset in range(0, 640 * 180 * 2, 512):
                response = peer.request("demo_frame", offset=offset)
                if response.get("offset") != offset or response.get("format") != "rgb565le":
                    raise RuntimeError("Invalid framebuffer position/format")
                if snapshot_id is None:
                    snapshot_id = response.get("snapshot_id")
                    snapshot_screen = response.get("snapshot_screen")
                if response.get("snapshot_id") != snapshot_id:
                    raise RuntimeError("Snapshot changed during capture")
                chunk = base64.b64decode(response["data"], validate=True)
                if len(chunk) != min(512, 640 * 180 * 2 - offset):
                    raise RuntimeError("Incomplete framebuffer chunk")
                pixels.extend(chunk)
            if (snapshot_id is not None and snapshot_screen != name) or (
                snapshot_id is None and peer.request("demo_ui")["screen"] != name
            ):
                raise RuntimeError("Demo was touched during screenshot; capture is not coherent")
            rgb = bytearray()
            for (pixel,) in struct.iter_unpack("<H", pixels):
                rgb.extend(
                    (((pixel >> 11) & 31) * 255 // 31, ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31)
                )
            path = args.output / f"screen-{scene + 1:02}.ppm"
            path.write_bytes(b"P6\n640 180\n255\n" + rgb)
            report["frames"].append({"scene": scene + 1, "name": name, "bytes": len(pixels), "file": path.name})
            print(json.dumps({"captured": name, "bytes": len(pixels)}), flush=True)

        def tap(x, y, held=80):
            return peer.request("demo_ui", op="tap", x=x, y=y, held_ms=held)

        peer.request("demo_ui", op="scene", scene=0)
        selected = tap(560, 80)
        assert selected["screen"] == "bevestigen" and selected["height_mm"] == 740 and selected["target_mm"] == 750
        selected = peer.request("demo_ui", op="press", x=560, y=80)
        assert selected["screen"] == "bevestigen" and selected["target_mm"] == 760 and selected["height_mm"] == 740
        for _ in range(5):
            status = peer.request("demo_ui")
            assert status["height_mm"] == 740
            time.sleep(0.2)
        assert status["target_mm"] > 760
        selected = peer.request("demo_ui", op="release")
        goal = selected["target_mm"]
        for _ in range(3):
            time.sleep(0.2)
            status = peer.request("demo_ui")
            assert status["height_mm"] == 740 and status["target_mm"] == goal
        assert tap(74, 80)["target_mm"] == goal - 10
        assert tap(200, 130)["screen"] == "bureau"
        assert peer.request("demo_ui")["height_mm"] == 740
        report["checks"].append(
            {"test": "tap_and_hold_edit_target_only_release_freezes_cancel_preserves_height", "passed": True}
        )
        peer.request("demo_ui", op="height", height_mm=1086)
        stopped = {"height_mm": 1086}
        tap(420, 130)
        assert tap(500, 50)["screen"] == "voorkeuren"
        saved = tap(500, 50)
        assert saved["sit_mm"] == stopped["height_mm"]
        report["checks"].append({"test": "save_current_height", "passed": True, "saved_mm": saved["sit_mm"]})
        tap(50, 90)
        assert tap(180, 50)["screen"] == "monitor"
        assert tap(430, 130)["monitor"] == 75
        report["checks"].append({"test": "monitor_brightness", "passed": True})
        peer.request("demo_ui", op="scene", scene=0)
        offline = tap(420, 130, 1200)
        assert offline["screen"] == "offline" and offline["connected"] is False
        assert tap(560, 80)["screen"] == "offline"
        tap(420, 130)
        assert tap(180, 130)["screen"] == "paneel"
        assert tap(130, 130)["brightness"] == 95
        report["checks"].append({"test": "offline_blocks_desk_keeps_local_settings", "passed": True})
        peer.request("demo_ui", op="scene", scene=0)
        report["final_hello"] = peer.request("hello")
        assert report["final_hello"]["ota"]["state"] == "valid"
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"frames": len(report["frames"]), "checks": report["checks"]}), flush=True)


if __name__ == "__main__":
    main()
