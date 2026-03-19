---
name: travel-rewards
description: >
  Query and manage travel rewards, loyalty points, miles, and credit card benefits
  using the travel-rewards CLI. Track balances, unused benefits, expiring credits,
  and spend goals. Delegates to cardpointers CLI for "which card should I use at X?"
  recommendations. Use when the user mentions points, miles, rewards, credit cards,
  benefits, travel credits, or card recommendations.
allowed-tools: Bash(travel-rewards *), Bash(cardpointers *)
---

# Travel Rewards

Track credit card benefits, loyalty balances, travel credits, certificates, and spend goals.

## Routing

| Question | Tool |
|----------|------|
| "What benefits haven't I used?" | `travel-rewards unused --json` |
| "What's expiring soon?" | `travel-rewards expiring --json` |
| "How many points do I have?" | `travel-rewards balances --json` |
| "Show my cards" | `travel-rewards cards --json` |
| "Which card should I use at Whole Foods?" | `cardpointers recommend "Whole Foods"` |
| "What bank offers are available?" | `cardpointers offers` |

## Quick Start

Always run status first to understand the data state:

```bash
travel-rewards status --json
```

Then query as needed:

```bash
# Benefits
travel-rewards unused --json
travel-rewards card <card-id> --json
travel-rewards benefits --card <card-id> --json

# Balances & credits
travel-rewards balances --json
travel-rewards credits --json
travel-rewards certificates --json

# Expiring items
travel-rewards expiring --days 30 --json
```

## Mutations (confirm with user first)

```bash
# Import data
travel-rewards import cardpointers
travel-rewards import awardwallet <file.xls>

# Log benefit usage
travel-rewards use log <card-id> <benefit-name> [amount]
travel-rewards use undo <usage-id>

# Manual updates
travel-rewards balance set <program> <amount>
travel-rewards credits use <id> [amount]
travel-rewards certificates use <id>
```

## Error Handling

All commands support `--json`. Errors return:
```json
{"ok": false, "error": "message", "suggestions": ["similar-card-id"]}
```

Use the `suggestions` field for fuzzy matching when a card or benefit name doesn't match exactly.

For full command reference, see [commands.md](commands.md).
