# kagi

Multi-verb CLI for Kagi. Authenticates via session token (no API credits used):

- `kagi search QUERY` — search the web; returns Quick Answer summaries + result links
- `kagi summarize URL` — summarize a known URL via Kagi's Universal Summarizer

`kagi-search` and `kagi-summarize` are also available as standalone binaries
(Python `console_scripts` shortcuts for `kagi search` and `kagi summarize`).

## Configuration

Create `~/.config/kagi/config.json` (auto-created with defaults on first run):

```json
{
  "password_command": "rbw get kagi-session-link",
  "timeout": 30,
  "max_retries": 5
}
```

`password_command` runs through your shell; both raw tokens and full
session-link URLs (`?...token=X...`) are accepted.

## Getting Your Token

1. Log in to [Kagi](https://kagi.com)
2. Go to [Settings → Session Link](https://kagi.com/settings?p=api)
3. Generate and copy the link (or extract the token)
4. Store in your password manager

## Usage

See [../skills/kagi/SKILL.md](../skills/kagi/SKILL.md).

## License

MIT
