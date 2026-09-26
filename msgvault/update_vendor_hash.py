"""Refresh msgvault's vendorHash after its tag moves.

Renovate rewrites the tag and relocks, but cannot compute a Go module hash.
Build the module derivation; on a hash mismatch, write the hash nix reports
into msgvault/default.nix and build again to confirm. Run from the repo root.
"""

import re
import subprocess
import sys
from pathlib import Path

PACKAGE = Path("msgvault/default.nix")
INSTALLABLE = ".#msgvault.goModules"
SRI = r"sha256-[A-Za-z0-9+/]+=*"
HASH_LINE = re.compile(rf'(vendorHash = "){SRI}(";)')
GOT = re.compile(rf"got:\s+({SRI})")


def build() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nix", "build", "--no-link", INSTALLABLE],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    first = build()
    if first.returncode == 0:
        print("vendorHash is current")
        return 0

    got = GOT.search(first.stderr)
    if got is None:
        sys.stderr.write(first.stderr)
        return 1

    text = PACKAGE.read_text()
    updated, count = HASH_LINE.subn(rf"\g<1>{got.group(1)}\g<2>", text)
    if count != 1:
        sys.stderr.write(f"{PACKAGE}: expected 1 vendorHash, found {count}\n")
        return 1
    PACKAGE.write_text(updated)
    print(f"vendorHash -> {got.group(1)}")

    confirm = build()
    if confirm.returncode != 0:
        sys.stderr.write(confirm.stderr)
    return confirm.returncode


if __name__ == "__main__":
    sys.exit(main())
