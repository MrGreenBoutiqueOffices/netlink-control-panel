"""Inject a validated published-release version without editing tracked sources."""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

Import("env")  # noqa: F821 - provided by PlatformIO/SCons

version = os.environ.get("PANEL_RELEASE_VERSION")
if version:
    if len(version) > 31 or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", version
    ):
        raise ValueError("Invalid panel release version")
    env.Append(CPPDEFINES=[("PANEL_FIRMWARE_VERSION", '\\"' + version + '\\"')])  # noqa: F821

# Only public policy is compiled. A private release key never reaches this build.
root = Path(env["PROJECT_DIR"]).parent  # noqa: F821
sys.path.insert(0, str(root / "host"))
from netlink_panel.signed_updates import load_trust, unbase64  # noqa: E402

trust = load_trust(root / "release/update-trust.json")
revision = os.environ.get("PANEL_BOARD_REVISION", "unverified")
if not re.fullmatch(r"[A-Za-z0-9._:-]{1,32}", revision):
    raise ValueError("Invalid panel board revision")
policy_digest = hashlib.sha256(json.dumps(trust, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
identity = f"NETLINK_PANEL_TRUST_V1|{trust['mode']}|{revision}|{policy_digest};"
lines = ["#pragma once", "#define PANEL_UPDATE_IDENTITY " + json.dumps(identity), '#include "signed_update.h"']
for i, key in enumerate(trust["keys"]):
    for name, data in [("id", bytes.fromhex(key["id"])), ("der", unbase64(key["public_key"], 128))]:
        lines.append(f"static const uint8_t update_{name}_{i}[] = {{" + ",".join(str(c) for c in data) + "};")
if trust["keys"]:
    lines.append("static const UpdateKey updateKeys[] = {")
    for i, key in enumerate(trust["keys"]):
        lines.append(f"{{update_id_{i}, update_der_{i}, sizeof(update_der_{i}), " + str(key["revoked"]).lower() + "},")
    lines.append("};")
keys = "updateKeys" if trust["keys"] else "nullptr"
lines.append(
    "static UpdatePolicy compiledUpdatePolicy() { return {"
    + str(trust["mode"] == "signed").lower()
    + ", "
    + json.dumps(revision)
    + f", 2, {trust['minimum_counter']}ULL, {keys}, {len(trust['keys'])}"
    + "}; }"
)
build = Path(env.subst("$BUILD_DIR"))  # noqa: F821
build.mkdir(parents=True, exist_ok=True)
(build / "generated_update_trust.h").write_text("\n".join(lines) + "\n")
env.Append(CPPPATH=[str(build)])  # noqa: F821
