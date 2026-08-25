"""Regression tests for validate_skill_doc.py.

Run with pytest; the nix build runs them via pytestCheckHook. Bare test
functions, so `unittest discover` collects nothing. Plain asserts and stdlib
only — matching kagi/tests, and keeping pytest out of the treefmt mypy env.

Every case here is a defect that shipped and was found only by adversarial
review — the validator looked like coverage while being a no-op on the inputs
that mattered. A validator with no tests of its own is the same trap one level
up, so each finding gets a test that fails against the old behaviour.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "validate_skill_doc.py"
_spec = importlib.util.spec_from_file_location("vsd", SRC)
assert _spec and _spec.loader
vsd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vsd)


def call(tool: str, args_json: str) -> str:
    return f"atlassian-cli call {tool} '{args_json}'"


# --- type_matches -----------------------------------------------------------


def test_list_valued_type_does_not_crash():
    """`{"type": ["string", "null"]}` is legal JSON Schema for a nullable
    param. This raised TypeError (unhashable list) and killed the whole run."""
    assert vsd.type_matches("hi", {"type": ["string", "null"]}) is True
    assert vsd.type_matches(None, {"type": ["string", "null"]}) is False
    assert vsd.type_matches(5, {"type": ["string", "null"]}) is False


def test_integer_still_satisfies_number():
    assert vsd.type_matches(3, {"type": "number"}) is True


def test_stringified_json_accepted_only_when_it_really_parses():
    """ADF travels as a JSON string in a `string`-typed field, so a string
    where an object is wanted can be legitimate — but only if it IS one."""
    adf = '{"type": "doc", "version": 1}'
    assert vsd.type_matches(adf, {"type": "object"}) is True
    # `fields: "summary"` where an array is wanted is a real doc error.
    assert vsd.type_matches("summary", {"type": "array"}) is False


def test_object_where_string_expected_is_caught():
    """The original bug: Confluence `body` is a plain string."""
    assert vsd.type_matches({"representation": "storage"}, {"type": "string"}) is False


# --- enums ------------------------------------------------------------------


def test_enum_violation_reported():
    """contentFormat is the trap SKILL.md devotes a section to; ATLAS_DOC_FORMAT
    is Jira REST's spelling and a plausible wrong guess."""
    spec = {"type": "string", "enum": ["markdown", "adf"]}
    assert vsd.enum_mismatch("ATLAS_DOC_FORMAT", spec) is not None
    assert vsd.enum_mismatch("adf", spec) is None


def test_enum_checked_end_to_end():
    tools = {
        "addCommentToJiraIssue": {
            "inputSchema": {
                "properties": {"contentFormat": {"type": "string", "enum": ["markdown", "adf"]}}
            }
        }
    }
    doc = call("addCommentToJiraIssue", '{"contentFormat": "ATLAS_DOC_FORMAT"}')
    assert vsd.validate(tools, doc), "enum violation must be reported"


# --- parse_examples ---------------------------------------------------------


def test_malformed_example_does_not_swallow_the_next():
    """re.S + non-greedy let an unterminated blob run across the document and
    eat the following example, which then shipped unvalidated."""
    doc = (
        'atlassian-cli call searchJiraIssuesUsingJql \'{\n  "cloudId": "x"\n}\n\'\n'
        + call("getJiraIssue", '{"cloudId":"x","BOGUS_1":1}')
        + "\n"
        + call("addCommentToJiraIssue", '{"cloudId":"x","BOGUS_2":2}')
    )
    names = [t for t, _, _ in vsd.parse_examples(doc)]
    assert "getJiraIssue" in names, "example after a malformed one must still parse"


def test_hyphenated_tool_name_is_seen():
    assert vsd.parse_examples(call("get-jira-issue", '{"a":1}'))


def test_unparseable_invocation_is_reported_not_ignored():
    """A `call` the regex can't fully match must fail loudly. Previously these
    contributed zero examples and the run still printed 'ok'."""
    for line in (
        "atlassian-cli call totallyFakeTool",
        'atlassian-cli call getJiraIssue "{\\"bogusParam\\":1}"',
    ):
        problems = vsd.validate({"getJiraIssue": {"inputSchema": {}}}, line)
        assert problems, f"silent pass for: {line}"


def test_prose_placeholder_is_not_flagged():
    """`atlassian-cli call <toolName> '<json>'` is the doc skeleton, not an
    example — flagging it would train readers to ignore the checker."""
    doc = "atlassian-cli call <toolName> '<json>'"
    assert vsd.validate({}, doc) == []


# --- tool-list drift --------------------------------------------------------

TOOL_LIST_DOC = """## The tools

**Jira** — `getJiraIssue` `createJiraIssue`

If a name isn't here, the server is ahead of this file
"""


def test_tool_list_drift_detects_new_server_tool():
    tools = {"getJiraIssue": {}, "createJiraIssue": {}, "brandNewTool": {}}
    assert vsd.tool_list_drift(tools, TOOL_LIST_DOC)


def test_tool_list_drift_detects_removed_server_tool():
    tools = {"getJiraIssue": {}}
    problems = vsd.tool_list_drift(tools, TOOL_LIST_DOC)
    assert problems and "createJiraIssue" in problems[0]


def test_tool_list_in_sync_is_silent():
    tools = {"getJiraIssue": {}, "createJiraIssue": {}}
    assert vsd.tool_list_drift(tools, TOOL_LIST_DOC) == []


def test_missing_tool_list_section_is_not_flagged_on_fragments():
    """validate() runs on doc fragments in tests; only main() requires the
    section on the real SKILL.md."""
    assert vsd.tool_list_drift({"getJiraIssue": {}}, "# no such section") == []


# --- snapshot -----------------------------------------------------------------


def test_snapshot_exists_and_is_current():
    """The committed snapshot is what CI validates against — if it goes stale
    the check silently weakens, so the script treats age as a failure."""
    tools, problems = vsd.load_snapshot()
    assert problems == [], problems
    assert len(tools) > 20, "snapshot looks truncated"


def _load_snapshot_from(payload):
    """Run load_snapshot against a throwaway snapshot file.

    Unannotated on purpose: `vsd` is loaded by path, so mypy sees a bare
    ModuleType and rejects every attribute on it inside a checked body."""
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "mcp-schemas.json"
        snap.write_text(json.dumps(payload))
        orig = vsd.SNAPSHOT
        vsd.SNAPSHOT = snap
        try:
            return vsd.load_snapshot()
        finally:
            vsd.SNAPSHOT = orig


def test_stale_snapshot_is_reported():
    """Age is the only thing keeping this check honest: past the limit the
    snapshot is validating SKILL.md against a server that has moved on, so it
    has to surface as a problem rather than pass quietly."""
    stale = datetime.now(UTC).date() - timedelta(days=vsd.SNAPSHOT_MAX_AGE_DAYS + 1)
    tools, problems = _load_snapshot_from(
        {"captured": stale.isoformat(), "tools": {"getJiraIssue": {}}}
    )
    assert tools == {"getJiraIssue": {}}
    assert problems and "days ago" in problems[0], problems


def test_fresh_snapshot_reports_nothing():
    """The other side of the boundary — proves the staleness test above fails
    for the right reason and not because load_snapshot always complains."""
    fresh = datetime.now(UTC).date() - timedelta(days=1)
    _tools, problems = _load_snapshot_from({"captured": fresh.isoformat(), "tools": {}})
    assert problems == [], problems


def test_snapshot_at_exactly_the_age_limit_is_accepted():
    """Pins the comparison as `>` and not `>=`, so a refresh cadence set to
    exactly SNAPSHOT_MAX_AGE_DAYS does not flap between pass and fail."""
    edge = datetime.now(UTC).date() - timedelta(days=vsd.SNAPSHOT_MAX_AGE_DAYS)
    _tools, problems = _load_snapshot_from({"captured": edge.isoformat(), "tools": {}})
    assert problems == [], problems


def test_future_dated_snapshot_is_reported():
    """A future `captured` yields a negative age, which sails under the limit
    forever — the one thing keeping this check honest would never fire."""
    ahead = datetime.now(UTC).date() + timedelta(days=3)
    _tools, problems = _load_snapshot_from({"captured": ahead.isoformat(), "tools": {}})
    assert problems and "future" in problems[0], problems


def test_unreadable_captured_date_is_reported():
    """A snapshot whose `captured` cannot be parsed must not skip the age gate
    silently — that would be an un-aging snapshot."""
    _tools, problems = _load_snapshot_from({"captured": "not-a-date", "tools": {}})
    assert problems and "unreadable" in problems[0], problems


def test_snapshot_covers_every_documented_example():
    """A snapshot missing a tool an example uses would report 'no such tool'
    — catch that here rather than as a confusing CI failure."""
    tools, _ = vsd.load_snapshot()
    text = vsd.SKILL.read_text()
    for name, _args, _raw in vsd.parse_examples(text):
        assert name in tools, f"{name} used in SKILL.md but absent from snapshot"


def test_real_skill_doc_validates_against_snapshot():
    """End-to-end: the shipped doc must pass the exact check CI runs."""
    tools, _ = vsd.load_snapshot()
    assert vsd.validate(tools, vsd.SKILL.read_text()) == []


def test_clean_document_passes():
    tools = {
        "getJiraIssue": {
            "inputSchema": {
                "properties": {"cloudId": {"type": "string"}},
                "required": ["cloudId"],
            }
        }
    }
    assert vsd.validate(tools, call("getJiraIssue", '{"cloudId": "x"}')) == []
