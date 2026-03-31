---
name: claude-sessions
description: >
  List and search recent Claude Code sessions for resumption. Use when the user
  asks about past sessions, wants to find a session by topic or keyword, or needs
  help resuming a previous conversation.
---

# Usage

Always use `--json-output` when invoking programmatically:

```bash
# Recent sessions (last 7 days, up to 20)
claude-sessions --json-output

# Longer lookback
claude-sessions --json-output -d 14

# Filter by project path
claude-sessions --json-output -p haystack

# Keyword search across full session content
claude-sessions --json-output -s "nginx"

# Combine filters
claude-sessions --json-output -d 30 -p nix -s "litestream"
```

# Interpreting results

Each session object contains:

- `session_id` — UUID for `claude --resume`
- `slug` — human-readable session name (e.g. "tender-frolicking-coral")
- `project_path` — working directory the session was started in
- `active_time` — estimated active work time (excludes idle gaps >10min)
- `input_tokens` / `output_tokens` — API token usage
- `topic` — summary from first user message (+ topic pivots after idle gaps in `--json-output`)
- `resume_cmd` — ready-to-run shell command: `cd <project> && claude --resume <id>`

# Presenting results

- Summarize sessions as a scannable list: project, topic, when, active time
- When the user wants to resume, give them the `resume_cmd` to copy-paste
- To match a topic query, use `-s` for keyword search or scan `topic` text
- `active_time` reflects actual work time, not wall clock span
- The user cannot resume from within this session — they need to run the command in their terminal
