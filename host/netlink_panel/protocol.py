"""Bounded, newline-delimited bench protocol shared with the firmware."""

import json

VERSION = 1
MAX_FRAME = 1024


class ProtocolError(ValueError):
    pass


def encode(message: dict, *, version: int = VERSION) -> bytes:
    payload = {"v": version, **message}
    validate(payload, version=version)
    frame = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
    if len(frame) > MAX_FRAME:
        raise ProtocolError("Frame exceeds 1024 bytes")
    return frame + b"\n"


def validate(message: object, *, version: int = VERSION) -> dict:
    if not isinstance(message, dict):
        raise ProtocolError("Expected object")
    if type(message.get("v")) is not int or message["v"] != version:
        raise ProtocolError("Incompatible protocol version")
    if not isinstance(message.get("type"), str) or not message["type"]:
        raise ProtocolError("Missing message type")
    if "id" in message and (type(message["id"]) is not int or not 0 < message["id"] <= 2**31 - 1):
        raise ProtocolError("Invalid request ID")
    return message


class Decoder:
    def __init__(self, *, version: int = VERSION):
        self.version = version
        self.buffer = bytearray()
        self.dropping = False
        self.rejected = 0

    def feed(self, data: bytes) -> list[dict]:
        messages = []
        for byte in data:
            if byte == 10:
                if not self.dropping and self.buffer:
                    try:
                        messages.append(validate(json.loads(self.buffer), version=self.version))
                    except (ValueError, UnicodeDecodeError):
                        self.rejected += 1
                self.buffer.clear()
                self.dropping = False
            elif not self.dropping:
                self.buffer.append(byte)
                if len(self.buffer) > MAX_FRAME:
                    self.rejected += 1
                    self.buffer.clear()
                    self.dropping = True
        return messages
