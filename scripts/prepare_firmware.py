"""Fetch the exact manufacturer sources; never download a moving branch."""

import argparse
import io
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REVISION = "3deece89098f25e7d155e41e4e0f5dd8b368ab02"
ROOT = Path(__file__).resolve().parents[1]
PARTS = ("board", "lib/Arduino_GFX-1.3.7", "lib/hyn_driver_for_esp32")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Existing official repository at the pinned commit")
    args = parser.parse_args()
    target = ROOT / "firmware/.vendor/lilygo"
    if target.exists():
        if (target / "UPSTREAM_REVISION").read_text().strip() != REVISION:
            raise SystemExit("Unexpected vendor revision; inspect the folder before replacing it")
        print(f"Manufacturer sources already prepared at {REVISION}")
        return
    with tempfile.TemporaryDirectory() as temporary:
        prepared = Path(temporary) / "lilygo"
        prepared.mkdir()
        if args.source:
            revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
            if revision != REVISION:
                raise SystemExit("Local manufacturer source is not at the pinned revision")
            if subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain"]):
                raise SystemExit("Local manufacturer source must be clean")
            for part in PARTS:
                shutil.copytree(args.source / part, prepared / part)
        else:
            url = f"https://codeload.github.com/Xinyuan-LilyGO/T-Display-S3-Long/zip/{REVISION}"
            with urllib.request.urlopen(url, timeout=120) as response:
                archive = response.read()
            prefix = f"T-Display-S3-Long-{REVISION}/"
            with zipfile.ZipFile(io.BytesIO(archive)) as source:
                for entry in source.infolist():
                    if not entry.filename.startswith(prefix) or entry.is_dir():
                        continue
                    relative = Path(entry.filename[len(prefix) :])
                    if relative.is_absolute() or ".." in relative.parts:
                        raise SystemExit("Invalid archive path")
                    if any(relative.as_posix().startswith(part + "/") for part in PARTS):
                        destination = prepared / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(source.read(entry))
        # The vendor driver enables autonomous touch-controller flashing by default.
        # A bench application must not replace the touch controller's own firmware.
        config = prepared / "lib/hyn_driver_for_esp32/hyn_cfg.h"
        original = config.read_text()
        old = "#define HYN_POWER_ON_UPDATA     (1)"
        if old not in original:
            raise SystemExit("Vendor touch update flag changed; inspect before building")
        config.write_text(original.replace(old, "#define HYN_POWER_ON_UPDATA     (0)"))
        (prepared / "UPSTREAM_REVISION").write_text(REVISION + "\n")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(prepared, target)
    print(f"Prepared {REVISION}; automatic touch-controller flashing disabled")


if __name__ == "__main__":
    main()
