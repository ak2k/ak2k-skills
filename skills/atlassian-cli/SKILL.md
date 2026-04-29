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
atlassian-cli call addCommentToJiraIssue '{"cloudId": "<cloudId>", "issueIdOrKey": "PROJ-123", "commentBody": "..."}'
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
