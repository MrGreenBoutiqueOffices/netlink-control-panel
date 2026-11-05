"""Build the exact SDK mbedTLS revision natively for cross-language tests."""

import hashlib
import io
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1d7033af30e20ccb2a0c0a114d3a08e372430f34"
SHA256 = "a74f373084e48df7b601d0185549ffdbdd72d89dcad939a2c59a1258cb0d0ee8"
TARGET = ROOT / "firmware/.vendor/mbedtls"


def main():
    if not TARGET.exists():
        with urllib.request.urlopen(
            f"https://codeload.github.com/espressif/mbedtls/tar.gz/{REVISION}", timeout=60
        ) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("Native crypto source checksum mismatch")
        with tempfile.TemporaryDirectory() as temporary:
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                archive.extractall(temporary, filter="data")
            shutil.copytree(Path(temporary) / f"mbedtls-{REVISION}", TARGET)
    subprocess.run(
        [
            "cmake",
            "-S",
            str(TARGET),
            "-B",
            str(TARGET / "build"),
            "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
            "-DENABLE_PROGRAMS=OFF",
            "-DENABLE_TESTING=OFF",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(TARGET / "build"), "--target", "mbedcrypto", "--parallel", "2"], check=True)


if __name__ == "__main__":
    main()
