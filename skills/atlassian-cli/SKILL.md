---
name: atlassian-cli
description: Query and update Atlassian Jira and Confluence via Atlassian's official Remote MCP. Use when the user asks about Jira issues, JQL searches, sprints, Confluence pages, or any Jira/Confluence operation.
---

# atlassian-cli

Thin pass-through to Atlassian's Remote MCP (`mcp.atlassian.com/v1/mcp`):

```bash
atlassian-cli call <toolName> '<json>'    # invoke one; output is JSON
atlassian-cli status                      # auth state
```

**Always narrow the output.** Responses are verbose — a bare `getJiraIssue` is
~1.5k tokens of fields you didn't ask for. Ask the server for less, then `jq`
what's left:

```bash
atlassian-cli call getJiraIssue '{"cloudId":"...","issueIdOrKey":"PROJ-1","fields":["summary","status"]}' \
  | jq '{key, summary: .fields.summary, status: .fields.status.name}'   # ~30x smaller
```

**Before composing any call you haven't made before, ask the server for its
parameters** — never guess them and never trust prose, including this file:

```bash
atlassian-cli tools <toolName> --schema   # params, types, enums, required
```

That is always current. Every documented parameter list rots when Atlassian
renames a field; the schema cannot.

To find a tool, **filter the listing** — bare `atlassian-cli tools` is ~1k
tokens of all 31 descriptions:

```bash
atlassian-cli tools | grep -i comment     # ~4x cheaper than the full list
atlassian-cli tools | awk '{print $1}'    # names only, ~6x cheaper
```

Nearly every tool takes `cloudId` (site UUID *or* hostname like
`kanerai.atlassian.net`). Get it once from `getAccessibleAtlassianResources`
and reuse it.

# Finding things

**`search` (Rovo) is the default** — it spans Jira *and* Confluence and takes
natural language. Reach for JQL/CQL only when the user supplies an explicit
query expression, or when you need precise filters (assignee, status, date).

```bash
# Rovo: natural language, mixed issues + pages. Filter the type you want.
atlassian-cli call search '{"cloudId": "<cloudId>", "query": "empty collateral versions"}' \
  | jq '[.results[] | select(.type == "issue") | {title, url}]'

# JQL: when you need exact filters
atlassian-cli call searchJiraIssuesUsingJql \
  '{"cloudId": "<cloudId>", "jql": "assignee = currentUser() AND status != Done"}' \
  | jq '[.issues[] | {key, summary: .fields.summary}]'
```

Rovo ranks semantically, so phrasing matters: a query loaded with extra terms
can bury the issue you want under Confluence pages. If a known ticket doesn't
surface, re-query with fewer, more distinctive words before concluding it
isn't there.

# Authentication

`atlassian-cli auth` runs an OAuth 2.1 browser consent flow — an agent cannot
drive it, so ask the user to run it. Refreshing *writes*
`~/.config/atlassian/token.json`, so sandboxed calls fail with `PermissionError`
and need `dangerouslyDisableSandbox`.

Scope is granted per-app: on a Jira+Confluence-only grant there are **no Compass
tools at all** — check `atlassian-cli tools` before routing Compass work here.
Bitbucket is never covered.

# Formatting: the `contentFormat` trap

Every body-bearing tool (comments, descriptions, worklogs, Confluence pages)
takes a sibling `contentFormat`. **Always pass it explicitly** — the schema
itself says "defaults vary by tool when omitted."

- **Jira** — `markdown` (default) or `adf`. Markdown is more capable than it
  looks: bold, code fences, nested lists, **and pipe tables** all convert to
  real ADF nodes. A `| a | b |` table becomes a genuine `table`/`tableRow`/
  `tableCell` tree, and a `- one<br>- two` cell nests a `bulletList` inside the
  cell. Reach for `adf` only for nodes markdown cannot spell — panels, status
  lozenges, mentions, media — or when you need exact structural control.
- **Confluence** — `html` (round-trip safe, preserves inline comments and local
  IDs, full `<table>` support plus HTML+ `data-type` nodes), `markdown`, or
  `adf`. Never storage XML (`<ac:structured-macro>`).

**The silent failure:** passing an ADF document *without* `contentFormat: "adf"`
runs it through the markdown converter and stores the raw `{"type": "doc", ...}`
as literal visible text. The tell is markdown escaping the JSON's brackets
(`\[`). If you see that, you forgot the flag.

```bash
# a markdown table is a real Jira table — no ADF needed
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-1", "contentFormat": "markdown",
    "commentBody": "| Range | Count |\n| --- | --- |\n| 2024-05 | 120 |"}'

# ADF must be JSON-STRINGIFIED into commentBody
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-1", "contentFormat": "adf",
    "commentBody": "{\"type\":\"doc\",\"version\":1,\"content\":[...]}"}'
```

`commentBody` is typed `string`, so ADF must be stringified there. But
`createJiraIssue.description` is `anyOf: [string, {type: "doc"}]` and takes a
bare object too — don't assume one shape works everywhere.

**Reading it back:** pass `responseContentFormat: "adf"` to get a real `doc`
object. A string body just means you didn't ask for ADF — it is *not* a
corruption signal. `getJiraIssue` also omits comments entirely unless you pass
`fields: ["comment"]`.

# Gotchas

- **Nothing is deletable.** No `deleteJiraIssue` / `deletePage` / `archive*` —
  a deliberate Atlassian safety choice. But **comments are editable**: pass
  `commentId` to `addCommentToJiraIssue` to overwrite one in place. A bad
  comment gets rewritten, never removed; route real deletions to the web UI.
- **`editJiraIssue`** is the update verb (there is no `updateJiraIssue`).
  Status changes go through `transitionJiraIssue` with an ID from
  `getTransitionsForJiraIssue`.
- **Users are `accountId`, never email or display name.** Resolve with
  `lookupJiraAccountId`. Note `atlassianUserInfo` is the *acting* user — useful
  for `currentUser()` JQL, useless for resolving "Adam".
- **Custom fields need discovery.** Project-specific required fields surface
  only via `getJiraIssueTypeMetaWithFields`; skipping it means a 400 that lists
  what you missed.
- **Issue-link directionality:** for "Blocks", `inwardIssue` is the *blocker* —
  "A is blocked by B" means `inwardIssue: B, outwardIssue: A`.
- **Worklog time** is Jira's natural-language format: `1w`, `2d`, `3h`, `30m`,
  or `1d 4h`.

# Write-op safety

Nothing here is deletable, but the writes that *are* exposed change state,
notify watchers, and leave an audit trail. Apply destructive-op hygiene:

- **Before a bulk write driven by JQL/CQL:** run the query as a *search* first
  and show the user the resolved targets. Never iterate writes over an
  unverified list.
- **Before `transitionJiraIssue` / `editJiraIssue`:** name the issue, the field,
  and the new value in your acknowledgement — these trigger notifications,
  workflow side effects, and downstream automation.
- **Comments and worklogs are visible to watchers and notify them.** Confirm
  before posting, especially on a ticket assigned to someone else.
- **`createIssueLink` publishes a relationship.** Wrong link type is fixable
  with a second call, but both survive in the audit trail.
- **Never infer "the bug" or "this sprint".** Pin writes to an explicit issue
  key; loose JQL is fine for reads only.

# Workflow templates

Atlassian's 5 official workflows ship under `workflows/` — `triage-issue`,
`spec-to-backlog`, `capture-tasks-from-meeting-notes`, `generate-status-report`,
`search-company-knowledge`. Deliberately not registered as top-level skills
(keeps idle context lean); Read `workflows/<name>/SKILL.md` when one fits. They
invoke MCP tools by bare name (`getJiraIssue(...)`) — translate each into
`atlassian-cli call <name> '<json>'`.

# Maintaining this skill

This file deliberately carries **no parameter lists** — `atlassian-cli tools
<name> --schema` is the source of truth, and anything transcribed here would
rot. Keep it to judgment the schema can't express.

The few illustrative examples above are checked against the live schema by:

```bash
atlassian-cli/validate_skill_doc.py   # tool exists, keys real, shapes match
```

Nonzero exit on drift. Needs an authenticated CLI, so it's a local pre-flight,
not CI.
