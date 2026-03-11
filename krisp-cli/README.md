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

# Upcoming meetings
krisp-cli call list_upcoming_meetings '{"days": 7}'

# Action items
krisp-cli call list_action_items '{"completed": false, "assigned_to_me": true}'

# Get full transcript by document ID
krisp-cli call get_multiple_documents '{"ids": ["abc123..."]}'

# Check auth status
krisp-cli status

# Logout
krisp-cli logout
```

## Configuration

Tokens are cached at `~/.config/krisp/token.json` and auto-refresh when expired.
