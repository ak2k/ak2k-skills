# krisp-cli

Dynamic CLI for [Krisp's MCP server](https://help.krisp.ai/hc/en-us/articles/25396920405148-Krisp-MCP) over Streamable HTTP.

Discovers tools at runtime via MCP's `tools/list`, so it adapts automatically when Krisp adds or changes tools. Auth is OAuth 2.0 with PKCE, using dynamic client registration.

## Usage

```bash
# Authenticate (one-time, opens browser)
krisp-cli auth

# List available tools
krisp-cli tools

# Search meetings
krisp-cli call search_meetings '{"search": "standup"}'
krisp-cli call search_meetings '{"search": "standup", "limit": 5}'
krisp-cli call search_meetings '{"after": "2026-03-01", "search": "planning"}'

# Upcoming meetings
krisp-cli call list_upcoming_meetings '{"days": 3}'
krisp-cli call list_upcoming_meetings '{"days": 14}'

# Action items
krisp-cli call list_action_items '{"completed": false, "assigned_to_me": true}'
krisp-cli call list_action_items '{"limit": 30}'

# Activities / notifications
krisp-cli call list_activities '{"limit": 10}'

# Get full meeting transcript/content by document ID
krisp-cli call get_multiple_documents '{"ids": ["abc123..."]}'

# User preferences (name, timezone, company)
krisp-cli call get_user_preferences '{}'

# Check auth status
krisp-cli status

# Logout
krisp-cli logout
```

## Configuration

Tokens are cached at `~/.config/krisp/token.json` and auto-refresh when expired.

## Cloudflare Workaround

Krisp's OAuth discovery advertises endpoints on `api.krisp.ai`, which may be
blocked by Cloudflare for some IPs. The CLI detects this and automatically
rewrites blocked URLs to use `mcp.krisp.ai` as a proxy. If you see
"api.krisp.ai blocked by Cloudflare, using mcp.krisp.ai proxy" during auth,
this is expected and handled transparently.
