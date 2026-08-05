#!/usr/bin/env python3
"""Generate skills/atlassian-cli/reference.md from the live MCP, and validate
SKILL.md's examples against it.

The Atlassian Remote MCP is an evolving upstream: tool parameters get renamed
and added without notice. Hand-written API surface in SKILL.md rots silently —
a stale `query` vs `searchString` only shows up as a -32602 at the moment an
agent tries to use it. So the surface is generated here and SKILL.md keeps only
the judgment a schema can't express.

    ./refresh_skill_reference.py            # validate SKILL.md, report drift
    ./refresh_skill_reference.py --update   # also rewrite reference.md

Requires an authenticated `atlassian-cli` (tools/list is an authenticated call),
so this is a manual/local check, NOT CI: wiring it into GitHub Actions would
mean parking a long-lived Atlassian OAuth token in repo secrets to lint a
markdown file. Exit code is nonzero when SKILL.md contradicts the live schema.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "atlassian-cli" / "SKILL.md"
REFERENCE = REPO / "skills" / "atlassian-cli" / "reference.md"

# `atlassian-cli call <tool> '<json>'`, tolerating shell line-continuations
# and JSON that wraps across lines inside the single quotes.
CALL_RE = re.compile(r"atlassian-cli call (\w+)\s+'(\{.*?\})'", re.S)
PLACEHOLDER_RE = re.compile(r"<([^>\"]+)>")
# A stringified-ADF example is a JSON document inside a JSON string; it defeats
# a naive json.loads of the outer object, so collapse it to a scalar first.
STRINGIFIED_ADF_RE = re.compile(r'"\{\\"type.*?\}"')


def load_tools() -> dict[str, dict]:
    """Fetch the live tool schemas via the installed atlassian-cli."""
    try:
        import atlassian_cli  # noqa: F401
    except ModuleNotFoundError:
        # Resolve the nix-wrapped install rather than requiring a venv.
        import subprocess

        which = subprocess.run(
            ["sh", "-c", "command -v atlassian-cli"], capture_output=True, text=True
        ).stdout.strip()
        if not which:
            sys.exit("atlassian-cli not on PATH — install it or run inside its env")
        real = Path(which).resolve()
        wrapped = real.parent / f".{real.name}-wrapped"
        target = wrapped if wrapped.exists() else real
        paths = re.findall(r"'([^']*site-packages)'", target.read_text(errors="ignore"))
        if not paths:
            sys.exit(f"could not locate atlassian-cli site-packages from {target}")
        sys.path[:0] = paths
        import atlassian_cli  # noqa: F811

    tools = atlassian_cli._mcp().list_tools()
    return {t["name"]: t for t in tools}


def parse_examples(text: str) -> list[tuple[str, dict | None, str]]:
    """Extract (tool, parsed_args, raw) for every documented invocation."""
    flat = re.sub(r"\\\n\s*", " ", text)
    out: list[tuple[str, dict | None, str]] = []
    for m in CALL_RE.finditer(flat):
        tool, blob = m.group(1), m.group(2)
        candidate = STRINGIFIED_ADF_RE.sub('"<adf>"', blob.replace("\n", " "))
        args: dict | None = None
        for attempt in (candidate, PLACEHOLDER_RE.sub(r"\1", candidate)):
            try:
                args = json.loads(attempt)
                break
            except json.JSONDecodeError:
                continue
        out.append((tool, args, blob))
    return out


def json_type(value) -> str:
    return {
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
        list: "array",
        dict: "object",
    }.get(type(value), "unknown")


def type_matches(value, spec: dict) -> bool:
    """Shallow type check against a property schema.

    Only the top-level shape is checked — that is what actually broke in
    practice (a `{representation, value}` object passed where the server wanted
    a plain string). anyOf is accepted if any branch matches; unconstrained or
    unfamiliar specs pass rather than emit noise.
    """
    if "anyOf" in spec:
        return any(type_matches(value, s) for s in spec["anyOf"])
    expected = spec.get("type")
    if expected is None:
        return True
    actual = json_type(value)
    if expected == "number" and actual == "integer":
        return True
    if actual == "string" and expected in {"object", "array"}:
        # Deliberate: ADF and other structured payloads travel as JSON strings.
        return True
    return actual == expected


def validate(tools: dict[str, dict], text: str) -> list[str]:
    problems: list[str] = []
    for tool, args, raw in parse_examples(text):
        if tool not in tools:
            problems.append(f"{tool}: no such tool on the server")
            continue
        if args is None:
            problems.append(f"{tool}: example is not parseable JSON — {raw[:60]}...")
            continue
        schema = tools[tool].get("inputSchema", {})
        props: dict = schema.get("properties", {})
        required = set(schema.get("required", []))
        for key, value in args.items():
            if key not in props:
                problems.append(
                    f"{tool}.{key}: not a parameter (valid: {', '.join(sorted(props))})"
                )
            elif not type_matches(value, props[key]):
                want = props[key].get("type", "?")
                problems.append(
                    f"{tool}.{key}: wrong shape — sent {json_type(value)}, want {want}"
                )
        for key in sorted(required - set(args)):
            problems.append(f"{tool}.{key}: required parameter missing from example")
    return problems


def render_reference(tools: dict[str, dict]) -> str:
    lines = [
        "<!-- GENERATED by atlassian-cli/refresh_skill_reference.py — do not edit."
        "  Judgment and gotchas belong in SKILL.md; this file is pure API surface. -->",
        "",
        "# Atlassian MCP tool reference",
        "",
        f"{len(tools)} tools. `R` marks a required parameter. Regenerate with "
        "`atlassian-cli/refresh_skill_reference.py --update`.",
        "",
        "Reading one tool's section costs a small fraction of the whole file — "
        "extract just the one you need:",
        "",
        "```bash",
        "awk '/^## <toolName>$/{f=1;print;next} f&&/^## /{exit} f' reference.md",
        "```",
        "",
        "## Contents",
        "",
    ]
    lines += [f"- {name}" for name in sorted(tools)]
    lines.append("")
    for name in sorted(tools):
        tool = tools[name]
        schema = tool.get("inputSchema", {})
        props: dict = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines.append(f"## {name}")
        lines.append("")
        if desc := (tool.get("description") or "").strip():
            lines.append(desc.splitlines()[0])
            lines.append("")
        if not props:
            lines.append("_No parameters._")
            lines.append("")
            continue
        lines.append("| param | type | | notes |")
        lines.append("|---|---|---|---|")
        for key in sorted(props, key=lambda k: (k not in required, k)):
            spec = props[key]
            typ = spec.get("type") or "/".join(
                s.get("type", "?") for s in spec.get("anyOf", [])
            )
            if enum := spec.get("enum"):
                typ = " \\| ".join(f"`{e}`" for e in enum)
            note = (spec.get("description") or "").split(". ")[0].strip()
            note = note.replace("|", "\\|")[:150]
            lines.append(
                f"| `{key}` | {typ} | {'R' if key in required else ''} | {note} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--update", action="store_true", help="rewrite reference.md from the live schema"
    )
    args = ap.parse_args()

    tools = load_tools()
    text = SKILL.read_text()

    if args.update:
        rendered = render_reference(tools)
        changed = not REFERENCE.exists() or REFERENCE.read_text() != rendered
        REFERENCE.write_text(rendered)
        print(f"{'updated' if changed else 'unchanged'}: {REFERENCE.relative_to(REPO)}")

    problems = validate(tools, text)
    examples = len(parse_examples(text))
    if problems:
        print(f"\n{len(problems)} problem(s) in {SKILL.relative_to(REPO)}:\n")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print(f"ok: {examples} documented call(s) match the live schema ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
