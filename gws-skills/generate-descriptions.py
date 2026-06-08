#!/usr/bin/env python3
"""Generate trigger-optimized frontmatter descriptions for the gws service skills.

A *dev-time* tool (not run in the nix build): it calls `claude -p` headlessly to
author one tight, third-person "what + when" `description:` per Google Workspace
service skill, optimized so the model auto-invokes the right skill. Output goes
to `overrides/gws-descriptions.json`, which is committed and consumed by
`transform.py` at build time (which also asserts verb coverage).

Ported from ak2k/ce-lite `converter/refine-keyword-rules.py` (the keyword+phrasing
refiner): same headless `claude -p --json-schema` harness and the same quality
rubric, with the output contract changed from "keywords + phrasing" to a single
frontmatter description string. The `structured_output` (not `result`) parsing
gotcha follows ~/.claude/memory/claude_p_headless_subscription.md.

Usage:
  python3 gws-skills/generate-descriptions.py <transformed-skills-dir>
  python3 gws-skills/generate-descriptions.py <dir> --filter gmail   # subset
  python3 gws-skills/generate-descriptions.py <dir> --dry-run        # no API calls
  python3 gws-skills/generate-descriptions.py <dir> --skip-existing  # keep current
  python3 gws-skills/generate-descriptions.py <dir> --model sonnet --workers 4

`<transformed-skills-dir>` is the output of `nix build .#gws-skills`
(.../share/skills) so each service's nested `references/<verb>.md` are visible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERRIDES_PATH = HERE / "overrides" / "gws-descriptions.json"
METHOD_CAP = 60  # max API method names fed as context (drive has many; cap the tail)

# Lines in a gws SKILL.md we mine for the capability surface: helper-command
# table rows (`| [`+verb`](...) | label |`), resource subsection headers
# (`### messages`), and method bullets (``  - `list` — ...``).
HELPER_ROW_RE = re.compile(r"\|\s*\[`(\+[\w-]+)`\][^|]*\|\s*([^|]+?)\s*\|")
RESOURCE_RE = re.compile(r"^#{3,}\s+([A-Za-z]\w*)\s*$")
METHOD_RE = re.compile(r"^\s*-\s+`(\w+)`")

# Service-level skills we author descriptions for: single-segment gws-<svc>
# plus the standalone admin-reports. (Recipes, personas, and gws-workflow-*
# sub-skills keep their upstream descriptions.)
EXTRA_SERVICES = {"gws-admin-reports"}

SYSTEM_PROMPT = """You write a single Claude Code skill `description` for a Google Workspace service skill (a thin wrapper over the `gws <service> <verb>` CLI). The description is loaded into the model's context at all times and is the SOLE signal another Claude uses to decide whether to auto-invoke this skill when a user makes a request. Your output's only job is correct triggering for this gws CLI skill.

Optimize for the requests a real user ACTUALLY makes to this service most often. Picture the everyday phrasings someone would type ("reply to this email", "what's on my calendar", "add a row to the sheet", "share this Drive folder") and make sure those fire first. Breadth of coverage exists to avoid missing a real request — not to enumerate every API method; never pad with rare or admin-only operations at the cost of focus or length.

For the one service you are given, produce:
  - description: ONE third-person sentence, "<Product>: <what — concrete verbs>. Use when <real user triggers/nouns>." Max 180 characters; aim for 100-150. Tighter is better — every word must earn its place.
  - verb_coverage: an object mapping each REQUIRED verb (given to you) to the exact trigger word/phrase in your description that covers it.
  - rationale: one sentence (for review).

QUALITY RULES (strict):

1. Third person only. Never "I", "you", "I can", "helps you". e.g. "Sends, reads, and searches Gmail..."

2. The REQUIRED verbs are a FLOOR, not the ceiling. Each must appear (as that word or an obvious synonym, e.g. triage -> "inbox", watch -> "new mail") AND be listed in verb_coverage. But they are only convenience-helper shortcuts — ALSO cover the service's major create / read / update / delete operations shown in the SKILL.md method tables below, so the description reflects everything the service can do (e.g. a calendar that can delete events, a spreadsheet that can be created), not just the helper shortcuts. A real user request like "delete my 3pm meeting" or "create a new spreadsheet" must trigger.

3. Front-load the distinctive trigger nouns a real user would type ("spreadsheet", "calendar event", "Drive file"). The listing can truncate, so lead with what discriminates this service. Prefer naming concrete CRUD verbs over the catch-all "manage".

4. Be DISTINCTIVE vs sibling services. You are given the full service list. Do NOT use trigger nouns that would equally fire a sibling; where services overlap, name the boundary briefly (e.g. "Chat-space messages, not email").

5. Avoid ubiquitous words that fire on almost any prompt ("manage", "data", "file" alone, "information", "content"). Prefer specific product nouns and verbs.

6. Tight. No marketing, no "powerful/seamless", no trailing period-padding. Every word earns triggering value.

SPECIAL CASES:
  - A service marked NOT-USER-INVOKED (e.g. gws-shared): write the description so the model does NOT select it for user requests — describe it as the internal shared dependency (auth, flags, output formatting) for the other gws-* skills, and say it is not directly user-invoked. verb_coverage may be empty.
  - gws-workflow: it is the entry point for multi-step CROSS-service workflows (e.g. standup report, meeting prep, weekly digest, email-to-task, announce a Drive file in Chat). Trigger on multi-step/cross-service intent; say single-service actions go to the specific gws-* skill.

RETURN strictly per the supplied JSON schema. No commentary outside the JSON."""

SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string", "minLength": 20, "maxLength": 200},
        "verb_coverage": {"type": "object", "additionalProperties": {"type": "string"}},
        "rationale": {"type": "string", "minLength": 10, "maxLength": 300},
    },
    "required": ["description", "verb_coverage", "rationale"],
    "additionalProperties": False,
}


@dataclass
class Service:
    name: str
    product: str
    upstream_desc: str
    verbs: list[str]
    capabilities: str
    not_user_invoked: bool


def _desc(skill_md: Path) -> str:
    m = re.search(r'^description:\s*"?(.*?)"?\s*$', skill_md.read_text(), re.M)
    return m.group(1) if m else ""


def extract_capabilities(text: str) -> str:
    """Distil a SKILL.md to its capability surface — helper commands + API method
    names (resource.method) — dropping the verbose method prose. A few hundred
    chars of high signal instead of multi-KB of raw body."""
    helpers: list[str] = []
    methods: list[str] = []
    resource: str | None = None
    for line in text.splitlines():
        h = HELPER_ROW_RE.match(line)
        if h:
            helpers.append(f"{h.group(1)} ({h.group(2).strip()})")
            continue
        r = RESOURCE_RE.match(line)
        if r:
            resource = r.group(1)
            continue
        m = METHOD_RE.match(line)
        if m:
            methods.append(f"{resource}.{m.group(1)}" if resource else m.group(1))
    methods = list(dict.fromkeys(methods))[:METHOD_CAP]  # dedupe, cap the tail
    out = []
    if helpers:
        out.append("Helper commands: " + ", ".join(helpers))
    if methods:
        out.append("API methods: " + ", ".join(methods))
    return "\n".join(out) or "(no commands/methods documented)"


def load_services(skills_dir: Path) -> list[Service]:
    services: list[Service] = []
    for d in sorted(skills_dir.iterdir()):
        if not (d / "SKILL.md").is_file():
            continue
        is_service = (
            bool(re.fullmatch(r"gws-[a-z]+", d.name)) or d.name in EXTRA_SERVICES
        )
        if not is_service:
            continue
        verbs = (
            sorted(f.stem for f in (d / "references").glob("*.md"))
            if (d / "references").is_dir()
            else []
        )
        services.append(
            Service(
                name=d.name,
                product=d.name.removeprefix("gws-"),
                upstream_desc=_desc(d / "SKILL.md"),
                verbs=verbs,
                capabilities=extract_capabilities((d / "SKILL.md").read_text()),
                not_user_invoked=(d.name == "gws-shared"),
            )
        )
    return services


def _user_input(svc: Service, roster: str) -> str:
    flags = " [NOT-USER-INVOKED]" if svc.not_user_invoked else ""
    verbs = (
        ", ".join(svc.verbs)
        if svc.verbs
        else "(none — derive the operation surface from the body)"
    )
    return (
        f"Service: {svc.name}{flags}\n"
        f"Upstream (terse) description: {svc.upstream_desc}\n"
        f"REQUIRED helper-shortcut verbs (FLOOR — must mention, but also cover the fuller "
        f"CRUD surface in the method tables below): {verbs}\n\n"
        f"Full service roster (for disambiguation — do not collide with these):\n{roster}\n\n"
        f"This service's capability surface (helper commands + API methods):\n{svc.capabilities}\n\n"
        f"Write the description per the schema."
    )


def refine(svc: Service, roster: str, model: str) -> dict | None:
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_CODE_DISABLE_AUTO_UPDATE": "1",
            "CLAUDE_CODE_DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
    )
    cmd = [
        "claude",
        "-p",
        _user_input(svc, roster),
        "--model",
        model,
        "--setting-sources",
        "",
        "--system-prompt",
        SYSTEM_PROMPT,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=120
        )
    except subprocess.TimeoutExpired:
        print(f"  [{svc.name}] TIMEOUT", file=sys.stderr)
        return None
    except FileNotFoundError:
        sys.exit("claude CLI not on PATH. Run inside an env that exports it.")
    if result.returncode != 0:
        print(
            f"  [{svc.name}] claude -p exit {result.returncode}: {result.stderr[:300]}",
            file=sys.stderr,
        )
        return None
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"  [{svc.name}] stdout not JSON: {exc}", file=sys.stderr)
        return None
    # `claude -p --json-schema` puts the structured result under
    # `structured_output` (NOT `result`).
    data = response.get("structured_output") or {}
    if not isinstance(data, dict) or not data.get("description"):
        print(
            f"  [{svc.name}] missing structured_output.description: {str(response)[:200]}",
            file=sys.stderr,
        )
        return None
    return {
        "description": str(data["description"]).strip(),
        "verb_coverage": data.get("verb_coverage") or {},
        "rationale": str(data.get("rationale", "")).strip(),
        "locked": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "skills_dir",
        help="transformed gws-skills dir (nix build .#gws-skills .../share/skills)",
    )
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--filter", default="", help="substring filter on service name")
    ap.add_argument("--dry-run", action="store_true", help="list targets, no API calls")
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="keep entries already present (incl. locked)",
    )
    args = ap.parse_args()

    services = load_services(Path(args.skills_dir))
    if args.filter:
        services = [s for s in services if args.filter in s.name]
    roster = "\n".join(
        f"  - {s.name}: {s.upstream_desc}" for s in load_services(Path(args.skills_dir))
    )

    existing: dict = {}
    if OVERRIDES_PATH.is_file():
        existing = json.loads(OVERRIDES_PATH.read_text())

    targets = [
        s
        for s in services
        if not (args.skip_existing and s.name in existing)
        and not existing.get(s.name, {}).get("locked")
    ]
    print(
        f"services: {len(services)}  to-generate: {len(targets)}  (skip-existing={args.skip_existing})"
    )
    for s in targets:
        print(f"  - {s.name}  verbs={s.verbs or '[]'}")
    if args.dry_run:
        return 0

    out = dict(existing)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for svc, res in zip(
            targets, pool.map(lambda s: refine(s, roster, args.model), targets)
        ):
            if res is None:
                print(
                    f"  [{svc.name}] FAILED — keeping any existing entry",
                    file=sys.stderr,
                )
                continue
            out[svc.name] = res
            print(f"  [{svc.name}] {len(res['description'])}c: {res['description']}")

    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(json.dumps(dict(sorted(out.items())), indent=2) + "\n")
    print(f"\nwrote {OVERRIDES_PATH} ({len(out)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
