#!/usr/bin/env python3
"""Validate the examples in skills/atlassian-cli/SKILL.md against the live MCP.

The Atlassian Remote MCP is an evolving upstream: tool parameters get renamed
and added without notice. A stale example (`query` where the server now wants
`searchString`) only surfaces as a -32602 at the moment an agent tries to use
it. This checks every documented invocation up front: the tool exists, each key
is a real parameter, value shapes match, and required parameters are present.

    ./validate_skill_doc.py

Agents needing a parameter list should ask the server directly —
`atlassian-cli tools <name> --schema` — rather than trusting prose. This script
only keeps the handful of illustrative examples in SKILL.md honest.

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

# `atlassian-cli call <tool> '<json>'`, tolerating shell line-continuations
# (joined before matching) and JSON that wraps across lines inside the quotes.
#
# `[^']*` rather than `.*?` with re.S: a non-greedy dot-matches-newline run has
# no floor, so one example missing its closing `}'` swallows the following
# example whole — the swallowed one is then never validated while the error
# points at the wrong line. Excluding `'` cannot cross a quote boundary.
CALL_RE = re.compile(r"atlassian-cli call ([\w.-]+)\s+'(\{[^']*\})'")
# Every literal invocation, however malformed — used to prove CALL_RE saw them
# all. A `call` whose args don't parse must fail loudly, not vanish.
ANY_CALL_RE = re.compile(r"atlassian-cli call (\S+)")
# `<toolName>`/`<name>` in the prose skeleton are documentation placeholders,
# not examples; they legitimately have no JSON to check.
PLACEHOLDER_TOOL_RE = re.compile(r"^<[\w-]+>$")


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
        args: dict | None
        try:
            args = json.loads(blob.replace("\n", " "))
        except json.JSONDecodeError:
            args = None
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

    `type` may be a list (`["string", "null"]` is standard for nullable
    params) — treat it as a set of acceptable types, not a scalar.
    """
    if "anyOf" in spec:
        return any(type_matches(value, s) for s in spec["anyOf"])
    raw = spec.get("type")
    if raw is None:
        return True
    expected = {raw} if isinstance(raw, str) else set(raw)
    actual = json_type(value)
    if actual == "integer" and "number" in expected:
        return True
    if actual == "string" and expected & {"object", "array"}:
        # A JSON document carried as a string: the MCP takes ADF this way
        # (commentBody is typed `string`). Only accept it when the string
        # really does parse as the structured type — otherwise `fields:
        # "summary"` where an array is wanted would pass as "well, ADF".
        try:
            return json_type(json.loads(value)) in expected
        except (json.JSONDecodeError, TypeError):
            return False
    return actual in expected


def enum_mismatch(value, spec: dict) -> str | None:
    """Report a value outside a declared enum.

    `contentFormat` is the parameter SKILL.md devotes a section to calling a
    trap; an unchecked enum is exactly how a plausible-but-wrong spelling
    (`ATLAS_DOC_FORMAT`, Jira REST's name for ADF) would ship.
    """
    allowed = spec.get("enum")
    if not allowed or not isinstance(value, (str, int, float, bool)):
        return None
    if value in allowed:
        return None
    return f"not in enum {allowed}"


def validate(tools: dict[str, dict], text: str) -> list[str]:
    problems: list[str] = []

    # Every literal `atlassian-cli call` must be accounted for. Without this,
    # any invocation CALL_RE can't match — double-quoted JSON, no args at all,
    # a stray newline before the closing quote — silently contributes nothing
    # and the run still reports "ok". Silence must not read as success.
    flat = re.sub(r"\\\n\s*", " ", text)
    parsed = parse_examples(text)
    seen = len(parsed)
    literal = [name for name in ANY_CALL_RE.findall(flat) if not PLACEHOLDER_TOOL_RE.match(name)]
    if len(literal) > seen:
        matched = [t for t, _, _ in parsed]
        for name in literal:
            if name in matched:
                matched.remove(name)
            else:
                problems.append(
                    f"{name}: `atlassian-cli call` found but its arguments could "
                    "not be parsed — quote the JSON in single quotes on one "
                    "logical line, or it ships unchecked"
                )

    for tool, args, raw in parsed:
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
                problems.append(f"{tool}.{key}: wrong shape — sent {json_type(value)}, want {want}")
            elif (bad := enum_mismatch(value, props[key])) is not None:
                problems.append(f"{tool}.{key}: {value!r} {bad}")
        for key in sorted(required - set(args)):
            problems.append(f"{tool}.{key}: required parameter missing from example")
    return problems


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    tools = load_tools()
    text = SKILL.read_text()

    problems = validate(tools, text)
    examples = len(parse_examples(text))
    if problems:
        print(f"{len(problems)} problem(s) in {SKILL.relative_to(REPO)}:\n")
        for p in problems:
            print(f"  \u2717 {p}")
        return 1
    print(f"ok: {examples} documented call(s) match the live schema ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
