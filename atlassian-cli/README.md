# atlassian-cli

Dynamic Python CLI for Atlassian's Remote MCP server (`mcp.atlassian.com/v1/mcp`).
Discovers tools at runtime via MCP `tools/list`, so it adapts when Atlassian
adds or changes tools. Auth is OAuth 2.1 with PKCE + RFC 7591 dynamic client
registration; tokens cached at `~/.config/atlassian/token.json` and auto-refresh.

Forked from [`krisp-cli`](../krisp-cli) — see the module docstring in
`atlassian_cli.py` for the three substantive deltas (MCP URL, OAuth discovery
path, redirect port).

## Usage

```bash
atlassian-cli auth                          # one-time 3LO browser flow
atlassian-cli tools                         # list available MCP tools
atlassian-cli call <tool> '<json-args>'     # invoke a tool
atlassian-cli status                        # check token expiry
atlassian-cli logout                        # clear cached creds
```

The Atlassian MCP exposes Jira, Confluence, and Compass operations. Bitbucket
is not covered; use a separate tool for that.
