---
name: cloak-browser
description: Stealth browsing — an agentic, anti-detect browser. Drive through anti-bot / bot-detection walls (Cloudflare Turnstile, fingerprinting, sannysoft-class checks) via the cloak-browser CLI (agent-browser + CloakBrowser's source-patched stealth Chromium). Use when the user asks for "stealth" browsing, or when a fetch or plain agent-browser is blocked, challenged, or bot-walled on an anonymous (not logged-in) site. Not for authenticated sessions.
---

# cloak-browser

`cloak-browser` is a drop-in stealth front-end to `agent-browser`: identical CLI
and verbs, but it drives CloakBrowser's source-patched Chromium, whose
fingerprint stealth is compiled into the binary (`navigator.webdriver` = false,
real Chrome UA not HeadlessChrome, spoofed GPU / cores / memory). Because the
stealth lives in the binary, it survives agent-browser driving over CDP.
Verified 56/56 on bot.sannysoft.com (vs 52/56 for plain agent-browser).

Use it exactly like `agent-browser` — every argument is forwarded. See the
`agent-browser` skill (or `agent-browser skills get core --full`) for the full
verb / session reference:

```bash
cloak-browser --session s open https://target.example
cloak-browser --session s snapshot
cloak-browser --session s eval "document.title"
cloak-browser --session s close
```

## When to use which

| Situation | Tool |
|---|---|
| Anonymous site that blocks/challenges bots (Cloudflare, fingerprinting, sannysoft) | **cloak-browser** |
| Logged-in / authenticated / persistent profile (real cookies, `--state`, rookiepy) | **agent-browser** with real Chrome — your genuine, stable identity |
| Logged-in AND bot-walled | **cloak-browser with `CLOAK_SEED`** (stable fake identity) |

Don't point default `cloak-browser` at an authenticated session: its fingerprint
rotates per launch, and a logged-in account whose device fingerprint changes
every visit reads as account-takeover.

## Modes (opt-in env knobs)

- Default — random fingerprint per launch (anonymous, rotating).
- `CLOAK_SEED=<int>` — pin the fingerprint (stable fake device across launches);
  required when reusing a profile or an injected session.
- `CLOAK_QUOTA=<MB>` — set storage quota so a persistent `--profile` reads as a
  real profile, not incognito.

```bash
# stable stealth identity with a persistent profile
CLOAK_SEED=42424 CLOAK_QUOTA=5000 cloak-browser --profile ./acct --session s open https://target.example
```

## Notes

- First run downloads CloakBrowser's Chromium (~350 MB, cached in `~/.cloakbrowser`).
- For the hardest sites the biggest lever is a clean/residential IP, not the
  browser — pass `--proxy` when datacenter IPs get reputation-blocked.
- This is fingerprint stealth, not behavioral: CloakBrowser's `humanize`
  (mouse/keyboard timing) is not available when driving via agent-browser.
- Don't share a `--session` name with plain `agent-browser` — the first to
  launch the daemon wins, so the other silently reuses its browser.
- macOS presents a native-Mac fingerprint; Linux presents a Windows profile.
- The `cloak-browser` CLI ships from nix-config (`scripts/cloak-browser.py`);
  this skill is documentation only.
