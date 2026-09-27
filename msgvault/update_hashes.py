"""Refresh msgvault's fixed-output hashes after its tag moves.

Renovate rewrites the tag and relocks, but cannot compute the web-asset or
Go module hashes. Build each fixed-output derivation; on a hash mismatch,
write the hash nix reports into msgvault/default.nix and build again to
confirm. Run from the repo root.
"""

import re
import subprocess
import sys
from pathlib import Path

PACKAGE = Path("msgvault/default.nix")
SRI = r"sha256-[A-Za-z0-9+/]+=*"
GOT = re.compile(rf"got:\s+({SRI})")
# (installable, name of the let-binding holding its hash)
TARGETS = [
    (".#msgvault.web", "webHash"),
    (".#msgvault.goModules", "vendorHash"),
]


def build(installable: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nix", "build", "--no-link", installable],
        capture_output=True,
        text=True,
        check=False,
    )


def refresh(installable: str, binding: str) -> int:
    first = build(installable)
    if first.returncode == 0:
        print(f"{binding} is current")
        return 0

    got = GOT.search(first.stderr)
    if got is None:
        sys.stderr.write(first.stderr)
        return 1

    line = re.compile(rf'({binding} = "){SRI}(";)')
    text = PACKAGE.read_text()
    updated, count = line.subn(rf"\g<1>{got.group(1)}\g<2>", text)
    if count != 1:
        sys.stderr.write(f"{PACKAGE}: expected 1 {binding}, found {count}\n")
        return 1
    PACKAGE.write_text(updated)
    print(f"{binding} -> {got.group(1)}")

    confirm = build(installable)
    if confirm.returncode != 0:
        sys.stderr.write(confirm.stderr)
    return confirm.returncode


def main() -> int:
    for installable, binding in TARGETS:
        status = refresh(installable, binding)
        if status != 0:
            return status
    return 0


if __name__ == "__main__":
    sys.exit(main())
