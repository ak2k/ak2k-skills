# Travel Rewards Command Reference

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | Output as structured JSON envelope |
| `--data-dir PATH` | Override data directory (env: `TRAVEL_REWARDS_DATA_DIR`) |

## Commands

### Setup

| Command | Description |
|---------|-------------|
| `init` | Create config directory and template card_mapping.yaml |
| `config` | Print config directory path |

### Import

| Command | Description |
|---------|-------------|
| `import cardpointers` | Import cards + benefits from CardPointers local SQLite |
| `import awardwallet <file.xls>` | Import balances from AwardWallet .xls export |

Import is idempotent — running it again updates existing records.

### Cards

| Command | Description |
|---------|-------------|
| `cards [--issuer X]` | List all cards |
| `card <id>` | Show card with all benefits |
| `cards add --name X --issuer X [--last-four X] [--annual-fee N] [--anniversary-month N]` | Add card |
| `cards edit <id> [--name X] [--issuer X] [--annual-fee N]` | Edit card |
| `cards remove <id>` | Delete card (cascades to benefits) |

### Benefits

| Command | Description |
|---------|-------------|
| `benefits [--card X]` | List benefits |
| `benefits add --card X --name X --value N --frequency TYPE [--category X]` | Add benefit |
| `benefits edit <id> [--name X] [--value N] [--frequency TYPE]` | Edit benefit |
| `benefits remove <id>` | Delete benefit |
| `unused [--card X]` | Show unused benefits |

Frequency types: `calendar_year`, `cardmember_year`, `monthly`, `quarterly`, `semi_annual`, `one_time`

### Usage Tracking

| Command | Description |
|---------|-------------|
| `use log <card-id> <benefit-name> [amount]` | Log benefit usage |
| `use undo <usage-id>` | Reverse a usage record |
| `usage [--card X]` | Show usage history |

### Balances

| Command | Description |
|---------|-------------|
| `balances` | List all program balances |
| `balances set <program> <amount>` | Set balance manually |

### Credits

| Command | Description |
|---------|-------------|
| `credits` | List active travel credits |
| `credits add --name X --value N [--issuer X] [--expiration DATE] [--passenger X]` | Add credit |
| `credits use <id> [amount]` | Use credit (decrements remaining) |

### Certificates

| Command | Description |
|---------|-------------|
| `certificates` | List certificates |
| `certificates add --name X [--program X] [--expiration DATE] [--details X]` | Add certificate |
| `certificates use <id>` | Mark certificate used |

### Spend Goals

| Command | Description |
|---------|-------------|
| `spend-goals` | List spend goals |
| `spend-goals add --card X --target N [--deadline DATE] [--reward X]` | Create goal |
| `spend-goals update <id> <amount>` | Record incremental spend |

### Queries

| Command | Description |
|---------|-------------|
| `status` | Compact summary (cards, unused, expiring) |
| `expiring [--days 30]` | Items expiring within N days |

## JSON Envelope

Success: `{"ok": true, "data": ..., "count": N}`

Error: `{"ok": false, "error": "message", "suggestions": ["hint1"]}`

## Data Directory

Default: `~/.config/travel-rewards/`

Contains:
- `rewards.db` — SQLite database
- `card_mapping.yaml` — AwardWallet suffix → card ID mapping
