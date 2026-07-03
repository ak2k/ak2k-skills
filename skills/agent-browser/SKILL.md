---
name: agent-browser
description: General browser automation — drive Chrome/Chromium over CDP (navigate, click, type, eval, screenshot, snapshot) via the agent-browser CLI. Use for normal or authenticated/logged-in browsing. For anonymous bot-walled / Cloudflare targets (i.e. "stealth" browsing) use the cloak-browser skill instead; for logged-in sites, inject real cookies (see below).
---

# agent-browser

`agent-browser` (vercel-labs) is a CDP browser-automation CLI. It drives an
external Chrome/Chromium — it ships no browser of its own.

**Full command reference:** run `agent-browser skills get core --full` — it
prints agent-browser's own up-to-date guide (verbs, sessions, `--state`,
`--profile`, network, tabs). Read it from the tool rather than duplicating it.

Typical loop:

```bash
agent-browser --session s open https://example.com
agent-browser --session s snapshot
agent-browser --session s eval "document.title"
agent-browser --session s close
```

## When to use which

| Situation | Tool |
|---|---|
| Normal / cooperative site | **agent-browser** |
| Logged-in / authenticated (your real HubSpot, Gmail, …) | **agent-browser** + injected real cookies — your genuine, stable identity |
| Anonymous site behind a bot wall (Cloudflare, fingerprinting, sannysoft) | the **cloak-browser** skill (rotating stealth fingerprint) |

Do **not** use cloak-browser for authenticated work: its per-launch fingerprint
rotation over a logged-in account reads as account-takeover.

## Authenticated sites

To drive a site you're already logged into, lift your real browser cookies and
inject them rather than re-authenticating. The reliable recipe (rookiepy →
Playwright state JSON → `agent-browser --state`, plus why attaching to running
Chrome / copied profiles fail) is captured in the `drive_authed_browser_rookiepy`
memory. Load a saved state with `agent-browser --state <file> open <url>`.

## Notes

- One browser per `--session`, launched on first `open`; `close` when done.
  `close --all` before switching `--profile`/`--state`, or a stale daemon
  silently ignores them.
- Don't share a `--session` name between agent-browser and cloak-browser — the
  first to launch the daemon wins, so the other silently reuses its browser.
- The binary comes from nix-config (llm-agents.nix); this skill is docs only.
