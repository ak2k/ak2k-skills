---
name: krisp-cli
description: Query Krisp meeting data — search meetings, list action items, upcoming meetings, and activities. Use when the user asks about meetings, action items, transcripts, or schedules.
---

# Usage

```bash
# List available tools (discovered dynamically from MCP server)
krisp-cli tools

# Search meetings
krisp-cli call search_meetings '{"search": "budget approval"}'
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
```

# Authentication

Run `krisp-cli auth` to authenticate via OAuth. Tokens are cached at `~/.config/krisp/token.json` and auto-refresh.

# Notes

- Tool discovery is dynamic — if Krisp adds new MCP tools, they appear automatically via `krisp-cli tools`
- Document IDs are 32-char lowercase hex strings (UUID without dashes)
- Use `get_multiple_documents` with meeting_id from search results to get full transcripts
