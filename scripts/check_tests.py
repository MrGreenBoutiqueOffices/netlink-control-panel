"""Run all host/native tests and fail if CI silently skips prerequisites."""

import ssl
import sys
import unittest

if __name__ == "__main__":
    if not getattr(ssl, "HAS_PSK", False):
        raise SystemExit("CI requires Python/OpenSSL with TLS-PSK support")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("tests"))
    if result.skipped:
        print("Skipped tests are not accepted in CI", file=sys.stderr)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
