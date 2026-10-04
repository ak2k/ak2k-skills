---
name: surefetch
description: Verified web fetch/search — use INSTEAD OF WebFetch (and curl) to read a public web page, search the web, extract clean article text, or crawl/map a site. Returns trustworthy main content or an honest abstention (never a login page, bot wall, or nav shell passed off as the article); the exit code encodes the outcome. `search` blends the user's Kagi/Perplexity subscriptions and can verify each result. NOT for logged-in/authenticated pages (use agent-browser) or anonymous bot-walled sites (use cloak-browser).
---

# Usage

```bash
# Fetch + verify one URL. Plain mode is the right agent path: clean markdown content
# on stdout, verdict on stderr, and the EXIT CODE tells you the outcome (branch on it).
surefetch fetch https://example.com/article        # → markdown content on stdout

# Search the web — auto-blends the user's Kagi + Perplexity subs (RRF), falls back to ddgs
surefetch search "your query" -n 8                 # ranked candidate links (UNVERIFIED)
surefetch search "your query" --scrape -n 5        # verify each hit through the ladder

surefetch extract page.html                        # deterministic HTML/PDF → clean text (no fetch)
surefetch map https://example.com                  # discover a site's URLs
surefetch crawl https://example.com --depth 1      # bounded, every page verified
surefetch doctor                                   # which rungs / search providers are active
```

# Output: prefer plain, use `--json` only for metadata

Plain mode is best for *reading* fetched content — markdown is token-efficient and LLM-native,
and the exit code gives deterministic routing with no JSON tax:

| kind | exit | meaning |
|---|---|---|
| `success` | 0 | verified, complete content (on stdout) |
| `uncertain` | 3 | retrieved but not confidently complete (soft paywall / partial) — verify before trusting |
| `not_found` | 4 | authoritative 404/410 |
| `blocked` | 5 | walled (bot challenge) — re-route (search, or cloak-browser) |
| `unreachable` | 6 | network/transport failure |

Add `--json` only when you must process metadata programmatically — the sealed
`{kind, content, engine, provenance, …}`, or iterating per-result outcomes from `search --scrape`.

# Notes

- The stealth **browser rung auto-joins when provisioned** (`surefetch doctor` shows it) — needed
  for bot-walled sites; core `fetch` is wheels-only (http/archive) otherwise.
- Latency knobs: `SUREFETCH_HEDGE=1` (concurrent probes, faster), `SUREFETCH_LATENCY_BUDGET=<sec>`.
