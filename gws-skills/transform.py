#!/usr/bin/env python3
"""Restructure the flat googleworkspace/cli skills tree into nested parents.

Each ``gws-<svc>-<verb>/SKILL.md`` becomes ``gws-<svc>/references/<verb>.md``,
linked from the parent's helper table and loaded by the agent via Read only
when that service skill is in use -- so verb-helpers cost zero idle context.

Runs in-place inside the already-copied skills dir (argv[1]). Membership rule
is kept in lockstep with ``nix/gws.nix``: nest ``gws-<svc>-<verb>`` iff parent
``gws-<svc>`` exists and the family is not ``gws-workflow-*`` (workflows are
compound entry points that stay top-level; ``gws-admin-reports`` has no
``gws-admin`` parent so it stays standalone).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

HELPER_RE = re.compile(r"^gws-([a-z]+)-(.+)$")
# Relative markdown link target, e.g. the `../foo/SKILL.md` in `](../foo/SKILL.md)`.
LINK_RE = re.compile(r"\]\((\.\.?/[^)]+)\)")


def nest_helpers(skills: Path) -> int:
    """Fold each eligible verb-helper into its parent's references/. Returns count."""
    nested = 0
    for helper_dir in sorted(skills.iterdir()):
        m = HELPER_RE.match(helper_dir.name)
        if not (m and helper_dir.is_dir()):
            continue
        svc, verb = m.group(1), m.group(2)
        if svc == "workflow":  # compound entry points -- keep top-level
            continue
        parent = skills / f"gws-{svc}"
        if not parent.is_dir():  # standalone (e.g. gws-admin-reports)
            continue

        (parent / "references").mkdir(exist_ok=True)

        # Move the helper body into the parent, fixing its two relative-link
        # shapes now that it sits one directory deeper:
        #   ../gws-shared/SKILL.md -> ../../gws-shared/SKILL.md
        #   ../<parent>/SKILL.md   -> ../SKILL.md   (link back to its own parent)
        body = (helper_dir / "SKILL.md").read_text()
        body = body.replace("](../gws-shared/SKILL.md)", "](../../gws-shared/SKILL.md)")
        body = body.replace(f"](../{parent.name}/SKILL.md)", "](../SKILL.md)")
        (parent / "references" / f"{verb}.md").write_text(body)

        # Repoint the parent's helper-table link at the nested reference.
        parent_md = parent / "SKILL.md"
        parent_md.write_text(
            parent_md.read_text().replace(
                f"](../{helper_dir.name}/SKILL.md)", f"](./references/{verb}.md)"
            )
        )

        shutil.rmtree(helper_dir)
        nested += 1
    return nested


def find_dead_links(skills: Path) -> list[str]:
    """Every relative markdown link whose target does not resolve on disk."""
    dead = []
    for md in skills.rglob("*.md"):
        for target in LINK_RE.findall(md.read_text()):
            path = target.split("#", 1)[0]
            if not (md.parent / path).exists():
                dead.append(f"{md} -> {target}")
    return dead


def main() -> int:
    skills = Path(sys.argv[1])
    count = nest_helpers(skills)
    print(f"gws-skills: nested {count} verb-helper(s)")

    # Safety net: if the membership rule, a link shape, or upstream's layout
    # drifts, fail the build here instead of shipping dead links (the exact
    # defect this transform replaces).
    dead = find_dead_links(skills)
    if dead:
        print("ERROR: gws-skills transform left dead relative links:", file=sys.stderr)
        print("\n".join(dead), file=sys.stderr)
        return 1
    print("gws-skills: all relative links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
