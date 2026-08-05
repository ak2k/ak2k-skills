"""Regression tests for validate_skill_doc.py.

Every case here is a defect that shipped and was found only by adversarial
review — the validator looked like coverage while being a no-op on the inputs
that mattered. A validator with no tests of its own is the same trap one level
up, so each finding gets a test that fails against the old behaviour.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "line",
    [
        "atlassian-cli call totallyFakeTool",
        'atlassian-cli call getJiraIssue "{\\"bogusParam\\":1}"',
    ],
)
def test_unparseable_invocation_is_reported_not_ignored(line):
    """A `call` the regex can't fully match must fail loudly. Previously these
    contributed zero examples and the run still printed 'ok'."""
    problems = vsd.validate({"getJiraIssue": {"inputSchema": {}}}, line)
    assert problems, f"silent pass for: {line}"


def test_prose_placeholder_is_not_flagged():
    """`atlassian-cli call <toolName> '<json>'` is the doc skeleton, not an
    example — flagging it would train readers to ignore the checker."""
    doc = "atlassian-cli call <toolName> '<json>'"
    assert vsd.validate({}, doc) == []


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
