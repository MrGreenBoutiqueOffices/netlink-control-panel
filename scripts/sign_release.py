"""Sign release assets using an environment-provided key, never a CLI secret."""

import argparse
import os
from pathlib import Path

from netlink_panel.signed_updates import load_trust, sign_bundle

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--trust", type=Path, default=Path("release/update-trust.json"))
    parser.add_argument("--counter", type=int, required=True)
    args = parser.parse_args()
    key = os.environ.get("PANEL_RELEASE_SIGNING_KEY")
    if not key:
        raise SystemExit("Release signing key is not configured")
    try:
        sign_bundle(args.bundle, key.encode(), load_trust(args.trust), counter=args.counter)
    except (ValueError, TypeError, KeyError, OSError):
        raise SystemExit("Release signing failed; no unsigned fallback") from None
    print("Release authorization signed and bundle digests verified")
