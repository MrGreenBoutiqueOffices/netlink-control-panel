"""Package a validated application and a versioned webserver core; never flash."""

import argparse
import ast
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tomllib
from pathlib import Path

from netlink_panel.ota import inspect_image

ROOT = Path(__file__).resolve().parents[1]


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def protocol_core(root, commit):
    """Use the same AST boundary as the existing SerialX webserver consumer."""
    spec = json.loads((root / "release/protocol-core.json").read_text())
    if spec["schema"] != 1 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", spec["version"]):
        raise ValueError("Unknown protocol package schema/version")
    sources = {name: (root / "host/netlink_panel" / name).read_bytes() for name in ("protocol.py", "service.py")}
    lines = sources["service.py"].decode().splitlines(keepends=True)
    selected = []
    for node in ast.parse(sources["service.py"]).body:
        if isinstance(node, ast.Import) and any(a.name in spec["excluded_import_modules"] for a in node.names):
            continue
        if isinstance(node, ast.ImportFrom) and node.module in spec["excluded_import_modules"]:
            continue
        if (
            isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign))
            or getattr(node, "name", None) in spec["selected_symbols"]
        ):
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
            selected.append("".join(lines[start : node.end_lineno]))
    generated = {
        "protocol.py": sources["protocol.py"],
        "transport.py": (
            '"""Generated selection of upstream service.py; no daemon, CLI or deployment entrypoint."""\n\n'
            + "\n\n".join(selected).rstrip()
            + "\n"
        ).encode(),
    }
    hashes = {name: digest(data) for name, data in generated.items()}
    if hashes != spec["consumer"]["generated_sha256"]:
        raise ValueError("Protocol core differs from the pinned webserver contract; review compatibility/version first")
    manifest = {
        "schema": spec["schema"],
        "version": spec["version"],
        "commit": commit,
        "repository": "MrGreenBoutiqueOffices/netlink-control-panel",
        "source_directory": "host/netlink_panel",
        "selected_symbols": spec["selected_symbols"],
        "excluded_import_modules": spec["excluded_import_modules"],
        "upstream_sha256": {name: digest(data) for name, data in sources.items()},
        "generated_sha256": hashes,
        "consumer": spec["consumer"],
    }
    files = {**generated, "__init__.py": b"", "UPSTREAM.json": json_bytes(manifest)}
    output = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o644
                archive.addfile(entry, io.BytesIO(data))
    return output.getvalue(), manifest


def release_version(tag):
    match = re.fullmatch(
        r"v((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?)", tag
    )
    if not match or len(match[1]) > 31:
        raise ValueError("Release tag must be v<semver> and fit the firmware version marker")
    return match[1]


def package(root, firmware, output, commit, tag=None, notes=None):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("An exact Git source commit is required")
    image = inspect_image(firmware.read_bytes())
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    header = (root / "firmware/src/panel_version.h").read_text()
    if f'#define PANEL_FIRMWARE_VERSION "{version}"' not in header:
        raise ValueError("Fallback firmware header and project version must match")
    expected = release_version(tag) if tag is not None else version
    if image["version"] != expected:
        raise ValueError("Firmware image must match the release tag or source fallback version")
    if tag is not None and (notes is None or not notes.is_file()):
        raise ValueError("Release Drafter notes are required for release packaging")
    release_notes = (
        notes.read_bytes() if notes is not None else b"CI candidate; release notes are managed by Release Drafter.\n"
    )
    core, core_manifest = protocol_core(root, commit)
    files = {
        "firmware.bin": firmware.read_bytes(),
        "protocol-core.tar.gz": core,
        "RELEASE_NOTES.md": release_notes,
    }
    inputs = [
        "uv.lock",
        "pyproject.toml",
        "firmware/platformio.ini",
        "firmware/release_version.py",
        "firmware/partitions.csv",
        "firmware/src/demo_assets.cpp",
        "scripts/prepare_firmware.py",
        "release/protocol-core.json",
    ]
    manifest = {
        "schema": 1,
        "source": {"repository": "MrGreenBoutiqueOffices/netlink-control-panel", "commit": commit, "tag": tag},
        "firmware": image,
        "compatibility": {
            "protocol_min": 2,
            "protocol_max": 2,
            "board_profile": "lilygo-s3-long-cst3530",
            "board_revision": "unverified",
            "partition_layout": "ota3m-v1",
            "actions": [],
            "protocol_core_version": core_manifest["version"],
            "capabilities": ["panel.status.v1", "device.state.v1", "panel.config.status.v1"],
        },
        "inputs_sha256": {name: digest((root / name).read_bytes()) for name in inputs},
        "artifacts": {name: {"sha256": digest(data), "size": len(data)} for name, data in files.items()},
        "signature": {
            "status": "unsigned",
            "reason": "Release-key provisioning and firmware verifier remain issue #15",
        },
    }
    files["manifest.json"] = json_bytes(manifest)
    files["SHA256SUMS"] = "".join(f"{digest(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Artifact output must be empty; never mix releases")
    for name, data in files.items():
        (output / name).write_bytes(data)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", type=Path, default=ROOT / "firmware/.pio/build/panel-bench/firmware.bin")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--notes", type=Path, help="Release Drafter body fetched from the published release")
    parser.add_argument("--print-release-version", action="store_true")
    args = parser.parse_args()
    if args.print_release_version:
        if args.tag is None:
            parser.error("--tag is required")
        print(release_version(args.tag))
        return
    if args.output is None:
        parser.error("--output is required")
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = package(ROOT, args.firmware, args.output, commit, args.tag, args.notes)
    print(f"Packaged {manifest['firmware']['version']} from {commit}; unsigned, no installation performed")


if __name__ == "__main__":
    main()
