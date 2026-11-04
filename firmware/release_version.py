"""Inject a validated published-release version without editing tracked sources."""

import os
import re

Import("env")  # noqa: F821 - provided by PlatformIO/SCons

version = os.environ.get("PANEL_RELEASE_VERSION")
if version:
    if len(version) > 31 or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", version
    ):
        raise ValueError("Invalid panel release version")
    env.Append(CPPDEFINES=[("PANEL_FIRMWARE_VERSION", '\\"' + version + '\\"')])  # noqa: F821
