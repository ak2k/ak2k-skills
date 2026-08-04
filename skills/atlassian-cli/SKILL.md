---
name: atlassian-cli
description: Query and update Atlassian Jira, Confluence, and Compass via Atlassian's official Remote MCP. Use when the user asks about Jira issues, JQL searches, sprints, Confluence pages, or any Atlassian product operation.
---

# Usage

```bash
# List available tools (discovered dynamically from the Atlassian MCP)
atlassian-cli tools

# Identity + site discovery (most tools take cloudId as a parameter)
atlassian-cli call atlassianUserInfo '{}'
atlassian-cli call getAccessibleAtlassianResources '{}'

# Default search — Rovo Search across both Jira and Confluence.
# The MCP itself recommends this over CQL/JQL unless the user explicitly
# uses those query languages. Returns mixed Jira issues + Confluence pages.
atlassian-cli call search '{"cloudId": "<cloudId>", "query": "kickoff notes"}'

# Jira: JQL search (use when user gives a JQL expression)
atlassian-cli call searchJiraIssuesUsingJql \
  '{"cloudId": "<cloudId>", "jql": "assignee = currentUser() AND status != Done"}'

# Jira: get / edit / create / comment / transition
atlassian-cli call getJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123"}'
atlassian-cli call editJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "fields": {"summary": "..."}}'
atlassian-cli call createJiraIssue '{"cloudId": "<cloudId>", "projectKey": "PROJ", "issueTypeName": "Task", "summary": "..."}'
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "commentBody": "...", "contentFormat": "markdown"}'

# Jira: a markdown pipe table becomes a REAL Jira table — no ADF needed
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "contentFormat": "markdown",
    "commentBody": "| Range | Count |\n| --- | --- |\n| 2024-05 | 120 |"}'

# Jira: ADF for nodes markdown cannot spell (panels, status, mentions).
# Must be JSON-STRINGIFIED into commentBody
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "contentFormat": "adf",
    "commentBody": "{\"type\":\"doc\",\"version\":1,\"content\":[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"hi\"}]}]}"}'

# Jira: update an existing comment in place (no delete tool exists)
atlassian-cli call addCommentToJiraIssue \
  '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "commentId": "<commentId>", "commentBody": "...", "contentFormat": "markdown"}'
atlassian-cli call getTransitionsForJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123"}'
atlassian-cli call transitionJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "transition": {"id": "31"}}'

# Jira: assignee resolution (turns email/displayName into accountId for createJiraIssue/editJiraIssue)
atlassian-cli call lookupJiraAccountId '{"cloudId": "<cloudId>", "query": "user@example.com"}'

# Jira: worklog
atlassian-cli call addWorklogToJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "timeSpent": "2h", "comment": "..."}'

# Jira: issue links (e.g., "blocks" / "is blocked by")
atlassian-cli call getIssueLinkTypes '{"cloudId": "<cloudId>"}'
atlassian-cli call createIssueLink \
  '{"cloudId": "<cloudId>", "type": {"name": "Blocks"}, "inwardIssue": {"key": "PROJ-1"}, "outwardIssue": {"key": "PROJ-2"}}'

# Jira: discover field metadata for a project/issue type before createJiraIssue
atlassian-cli call getVisibleJiraProjects '{"cloudId": "<cloudId>"}'
atlassian-cli call getJiraProjectIssueTypesMetadata '{"cloudId": "<cloudId>", "projectIdOrKey": "PROJ"}'
atlassian-cli call getJiraIssueTypeMetaWithFields '{"cloudId": "<cloudId>", "projectIdOrKey": "PROJ", "issueTypeId": "10001"}'

# Confluence: CQL search (use when user gives a CQL expression)
atlassian-cli call searchConfluenceUsingCql \
  '{"cloudId": "<cloudId>", "cql": "type = page AND space = DEV AND title ~ \"deployment\""}'

# Confluence: get / create / update pages
atlassian-cli call getConfluenceSpaces '{"cloudId": "<cloudId>"}'
atlassian-cli call getPagesInConfluenceSpace '{"cloudId": "<cloudId>", "spaceId": "..."}'
atlassian-cli call getConfluencePage '{"cloudId": "<cloudId>", "pageId": "12345"}'
atlassian-cli call createConfluencePage \
  '{"cloudId": "<cloudId>", "spaceId": "...", "title": "...", "body": {"representation": "storage", "value": "<p>...</p>"}}'
atlassian-cli call updateConfluencePage \
  '{"cloudId": "<cloudId>", "pageId": "12345", "title": "...", "body": {"representation": "storage", "value": "<p>...</p>"}, "version": {"number": 2}}'

# Confluence: comments (footer = page-level, inline = anchored to text)
atlassian-cli call getConfluencePageFooterComments '{"cloudId": "<cloudId>", "pageId": "12345"}'
atlassian-cli call createConfluenceFooterComment '{"cloudId": "<cloudId>", "pageId": "12345", "body": {"representation": "storage", "value": "..."}}'

# ARI (Atlassian Resource Identifier) lookup — when an ID is in ARI form, use this
atlassian-cli call fetch '{"ari": "ari:cloud:jira:..."}'

# Check auth status
atlassian-cli status
```

# Authentication

Run `atlassian-cli auth` to authenticate via OAuth 2.1 (3LO consent flow). The
browser will open the Atlassian consent screen — pick which Atlassian apps
(Jira, Confluence, Compass) to grant access to. Tokens are cached at
`~/.config/atlassian/token.json` and auto-refresh.

# Workflow templates

Atlassian's 5 official workflow skills ship under `./workflows/<name>/SKILL.md`
relative to this skill's directory. They are NOT registered as top-level skills
(intentional — keeps idle context lean); load the relevant one with the Read
tool when the task fits.

| Workflow | When to load it |
|---|---|
| `workflows/triage-issue/SKILL.md` | User reports a bug or error message. Searches Jira for duplicates, classifies the issue, helps create a structured ticket or augment an existing one. |
| `workflows/spec-to-backlog/SKILL.md` | User has a spec / PRD doc (in Confluence or pasted) and wants it broken down into Jira epics + stories. |
| `workflows/capture-tasks-from-meeting-notes/SKILL.md` | User has meeting notes (Confluence page or pasted text) and wants action items extracted into Jira issues with assignees. |
| `workflows/generate-status-report/SKILL.md` | User wants a project status report — querying Jira via JQL, formatting, optionally publishing to Confluence. |
| `workflows/search-company-knowledge/SKILL.md` | User has a question whose answer probably lives across Jira + Confluence; uses Rovo Search and synthesizes. |

These workflows are written by Atlassian to invoke MCP tools by name
(`searchJiraIssuesUsingJql(...)`, `getJiraIssue(...)`, `createJiraIssue(...)`,
etc.). Translate each such reference into the equivalent
`atlassian-cli call <name> '<json>'` invocation when executing the workflow's
steps.

# Notes

- **Tool discovery is dynamic** — `atlassian-cli tools` is the source of truth. Atlassian's Remote MCP currently exposes ~33 tools; if the user's site has a different scope grant (e.g. no Compass), the list may differ.
- **Most tools require `cloudId`** — the unique site identifier. Get it once with `atlassian-cli call getAccessibleAtlassianResources '{}'` and reuse it for the rest of the session. The site hostname (e.g. `kanerai.atlassian.net`) often works in place of the UUID.
- **Default search is `search` (Rovo)**, not CQL/JQL — only fall back to `searchJiraIssuesUsingJql` / `searchConfluenceUsingCql` when the user provides an explicit query expression.
- **No destructive operations exposed.** The MCP intentionally omits `deleteJiraIssue` / `deletePage` / `archive*` etc. — Atlassian's design choice for safety. If the user needs deletion, route them to the Atlassian web UI or use the REST API directly.
- **`editJiraIssue`** is the update verb (not `updateJiraIssue`). For workflow transitions use `transitionJiraIssue` with a transition ID from `getTransitionsForJiraIssue`.
- **Worklog** uses Jira's natural-language time format: `1w`, `2d`, `3h`, `30m`, or combined like `1d 4h`.
- **Issue link directionality:** for "Blocks", `inwardIssue` is the *blocker*, `outwardIssue` is the *blocked* item — i.e., "A is blocked by B" → `inwardIssue: B, outwardIssue: A`.
- **Bitbucket is NOT covered** by Atlassian's Remote MCP. Use a separate tool for Bitbucket operations.
- **Output is JSON** — pipe through `jq` for ad-hoc filtering.

# Footguns

These fail silently or produce surprising output rather than erroring loudly — call them out before invoking.

- **`contentFormat` decides how bodies are parsed — always pass it explicitly.** Every body-bearing tool (`addCommentToJiraIssue`, `createJiraIssue`, `editJiraIssue`, `addWorklogToJiraIssue`, `createIssueLink`, and the Confluence page/comment tools) takes a sibling `contentFormat` enum, and the schema warns "Defaults vary by tool when omitted."
  - Jira: `["markdown", "adf"]`, **markdown is the default**. Markdown is more capable than it looks — verified converting to real ADF nodes: bold, code fences, nested lists, **and pipe tables** (`| a | b |` becomes a genuine `table`/`tableRow`/`tableCell` tree, not literal text). A `- one<br>- two` cell even yields a `bulletList` nested inside the `tableCell`. Reach for `"adf"` when you need nodes with no markdown spelling — panels, status lozenges, mentions, media — or when you want exact structural control.
  - Confluence: `["html", "markdown", "adf"]`. `"html"` is the ergonomic choice — it is round-trip safe, preserves inline comments and local IDs, and supports `<table>/<thead>/<tr>/<th>/<td>` plus Confluence HTML+ nodes via `data-type` attributes (panels, expands, task lists, layouts). Never use storage XML (`<ac:structured-macro>`).
  - **The silent-failure trap:** passing an ADF document *without* `contentFormat: "adf"` sends it through the Markdown converter, and the raw `{"type": "doc", ...}` is stored as literal visible text. The tell is markdown escaping the JSON's brackets (`\[`).
- **`commentBody` is string-only; `description` is not.** `addCommentToJiraIssue.commentBody` is typed `string`, so an ADF document must be **JSON-stringified** (a bare object is rejected with `-32602 expected string, received object`). `createJiraIssue.description` is `anyOf: [string, {type: "doc"}]` and accepts either a stringified ADF doc or a bare object. Don't assume one shape works everywhere.
- **Comments are editable, but nothing is deletable.** `addCommentToJiraIssue` takes an optional `commentId` to update an existing comment in place ("Add or update"). There is no delete-comment tool — nor any delete/archive op among the 31 tools — so a bad comment must be overwritten, not removed.
- **Reads default to markdown — ask for ADF if you want structure.** `getJiraIssue` accepts `responseContentFormat: ["markdown", "adf"]`; with `"adf"` the comment `body` comes back as a real `doc` object. A `str` body just means you didn't request ADF — it is *not* a corruption signal. `getJiraIssue` also omits comments entirely unless you pass `fields: ["comment"]`.
- **`updateConfluencePage` has no `version` parameter.** The server manages versioning; `required` is only `[cloudId, pageId, body]`. Pass `versionMessage` (a string) if you want a labelled revision. Do not try to compute `version.number` — there is no such field.
- **Custom fields require discovery.** Project-specific required fields surface only via `getJiraIssueTypeMetaWithFields` (per project + issue type). Calling `createJiraIssue` without them returns a 400 listing the missing fields, but it's faster to discover up front.
- **Assignees take `accountId`, not email or display name.** Use `lookupJiraAccountId '{"query": "user@example.com"}'` to resolve. The same applies to most user-valued fields.
- **`atlassianUserInfo` is the *acting* user**, not necessarily the *target* user — useful for `assignee = currentUser()` JQL but not for resolving "Adam".

# Write-op safety

The MCP omits delete/archive ops, but the writes it *does* expose can still cause real-world impact (state changes, notifications, version bumps, comment churn). Apply the same hygiene as for destructive ops:

- **Before bulk write via JQL/CQL:** run the same query as a search call first and show the user the resolved targets (count + a sample of keys/titles). Don't iterate writes against an unverified target list.
- **Before `transitionJiraIssue` / `editJiraIssue`:** name the target issue, the field changing, and the new value in your acknowledgement to the user, especially when the operation triggers notifications, workflow side effects, or downstream automation.
- **`addWorklogToJiraIssue` and comments are visible to other watchers and may trigger notifications.** Confirm with the user before posting.
- **`createIssueLink` is reversible but visible.** Get the link type wrong and you've published a wrong relationship publicly; the fix is a second call but the audit trail keeps both.
- **Don't infer "current sprint" / "active project" silently.** When a user says "the bug" or "this sprint", confirm which one before writing. JQL like `assignee = currentUser() AND sprint in openSprints()` is fine for *reads*; for writes, pin to an explicit issue key.
