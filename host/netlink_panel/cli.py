"""Read-only discovery and a demo-state USB bench session."""

import argparse
import json
import time
from contextlib import nullcontext

import serial
from serial.tools import list_ports

from .protocol import Decoder, encode
from .simulator import SimulatedPanel


def report(event, **values):
    print(json.dumps({"event": event, **values}), flush=True)


def bench(
    port=None,
    *,
    duration=5.0,
    timeout=3.5,
    height=740,
    brightness=60,
    device=None,
    expected_panel=None,
    transport="usb",
):
    decoder = Decoder()
    hello = None
    ack = False
    heartbeats = 0
    started = last_rx = last_hello = time.monotonic()
    next_heartbeat = started
    connection = serial.Serial(port, 115200, timeout=0.1, write_timeout=1) if device is None else nullcontext(device)
    with connection as device:
        device.write(encode({"type": "hello", "id": 1}))
        while time.monotonic() - started < duration:
            now = time.monotonic()
            if hello is None and now - last_hello >= 1:
                device.write(encode({"type": "hello", "id": 1}))
                last_hello = now
            if hello is not None and now >= next_heartbeat:
                device.write(encode({"type": "heartbeat"}))
                next_heartbeat = now + 1
            for message in decoder.feed(device.read(4096)):
                kind = message["type"]
                if kind == "hello" and message.get("id") == 1:
                    capabilities = message.get("capabilities")
                    if (
                        not isinstance(message.get("panel_id"), str)
                        or not message["panel_id"]
                        or not isinstance(capabilities, list)
                        or "demo_state" not in capabilities
                    ):
                        raise RuntimeError("Panel identity or demo capability missing")
                    if hello is None:
                        if expected_panel is not None and message["panel_id"] != expected_panel:
                            raise RuntimeError("Panel identity does not match the enrolled panel")
                        hello = message
                        last_rx = time.monotonic()
                        report("connected", panel=message)
                        device.write(
                            encode({"type": "demo_state", "id": 2, "height_mm": height, "brightness": brightness})
                        )
                elif hello is not None and kind == "heartbeat":
                    last_rx = time.monotonic()
                    heartbeats += 1
                elif hello is not None and kind == "ack" and message.get("id") == 2:
                    if message.get("ok") is not True:
                        raise RuntimeError("Panel rejected demo state")
                    ack = True
                    report("demo_applied", height_mm=height, brightness=brightness)
                elif hello is not None and kind == "touch":
                    report("touch", action=message.get("action"), hardware_command_sent=False)
            if time.monotonic() - last_rx > timeout:
                raise RuntimeError("Panel handshake/heartbeat timeout; no actions will be replayed")
        if hello is None or not ack or heartbeats < 1:
            raise RuntimeError("Bench incomplete: require handshake, matching acknowledgement and heartbeat")
        result = {
            "panel_id": hello["panel_id"],
            "simulated": hello.get("simulated", False),
            "heartbeats": heartbeats,
            "rejected_frames": decoder.rejected,
            "hardware_command_sent": False,
            "transport": transport,
        }
        report("bench_passed", **result)
        return result


def main():
    parser = argparse.ArgumentParser(description="NetLink panel bench tools (no desk/monitor commands)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ports", help="List serial ports without opening them")
    from .wifi import add_wifi_commands, run_wifi

    add_wifi_commands(commands)
    test = commands.add_parser("bench", help="Handshake and display demo data; never flash")
    choice = test.add_mutually_exclusive_group(required=True)
    choice.add_argument("--port")
    choice.add_argument("--simulate", action="store_true")
    test.add_argument("--duration", type=float, default=5)
    test.add_argument("--height", type=int, default=740)
    test.add_argument("--brightness", type=int, default=60)
    args = parser.parse_args()
    if args.command == "wifi":
        try:
            return run_wifi(args)
        except (RuntimeError, ValueError, OSError, serial.SerialException) as error:
            report("wifi_failed", error=str(error))
            return 1
        except KeyboardInterrupt:
            report("wifi_stopped")
            return 130
    if args.command == "ports":
        for port in list_ports.comports():
            report(
                "port",
                port=port.device,
                description=port.description,
                vid=port.vid,
                pid=port.pid,
                serial_number=port.serial_number,
            )
        return 0
    if not 4 <= args.duration <= 3600 or not 500 <= args.height <= 1300 or not 0 <= args.brightness <= 100:
        parser.error("duration must be 4..3600, height 500..1300 mm, brightness 0..100")
    try:
        with SimulatedPanel() if args.simulate else nullcontext() as simulator:
            bench(
                simulator.port if simulator else args.port,
                duration=args.duration,
                height=args.height,
                brightness=args.brightness,
            )
    except (RuntimeError, serial.SerialException, OSError) as error:
        report("bench_failed", error=str(error))
        return 1
    except KeyboardInterrupt:
        report("bench_stopped")
        return 130
    return 0
