# ak2k-skills

LLM-useful CLI tools and agent skills, packaged with Nix.

Installs into both [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
and [opencode](https://opencode.ai) by default — each skill is symlinked into
every directory listed in `programs.ak2k-skills.skillDirs`.

Structure and approach is inspired by [Mic92/mics-skills](https://github.com/Mic92/mics-skills).

## Skills

| Skill | Description |
|-------|-------------|
| [atlassian-cli](atlassian-cli/) | Query and update Atlassian Jira, Confluence, and Compass via Atlassian's official Remote MCP; bundles 5 official workflow skills under `workflows/` |
| [claude-sessions](claude-sessions/) | List and search recent Claude Code sessions for resumption |
| [gemtts](skills/gemtts/) | Generate Gemini text-to-speech audio (voices, style, pace). Binary from [`paperfoot/gemtts`](https://github.com/paperfoot/gemtts). |
| [kagi](kagi/) | Search the web or summarize a URL via Kagi — no API credits used (session-token auth) |
| [krisp-cli](krisp-cli/) | Dynamic CLI for Krisp's MCP server — search meetings, action items, transcripts |
| `msgvault-query` | SQL analytics over a msgvault email/chat archive. Binary + skill from [`wesm/msgvault`](https://github.com/wesm/msgvault). |
| `pplx-agent-tools` | Query Perplexity via a Pro web session — `pplx search`, `pplx fetch --prompt`, `pplx snippets`. Binary + skill from [`ak2k/pplx-agent-tools`](https://github.com/ak2k/pplx-agent-tools). |
| [siplink](skills/siplink/) | Place a phone call via VoIP.ms (binary from elsewhere) |
| [stealth-browse](skills/stealth-browse/) | Drive a browser through anti-bot walls via the `cloak-browser` CLI (agent-browser + CloakBrowser stealth Chromium). CLI ships from nix-config; docs-only here. |

## Bundles

Bundles are skill sets re-exported from another flake as a single unit. Each
bundle contributes many entries to the registry, all sharing one package.

| Bundle | Description | Helper |
|--------|-------------|--------|
| `gws` | Google Workspace CLI from [`googleworkspace/cli`](https://github.com/googleworkspace/cli) — ~100 skills covering Gmail, Drive, Calendar, Sheets, Docs, Chat, Slides, Forms, Tasks, and more | `inputs.ak2k-skills.lib.bundles.gws` |

## Installation

Add as a flake input and import the home-manager module:

```nix
# flake.nix
inputs.ak2k-skills.url = "github:ak2k/ak2k-skills";
inputs.ak2k-skills.inputs.nixpkgs.follows = "nixpkgs-unstable";

home-manager.sharedModules = [
  inputs.ak2k-skills.homeManagerModules.default
];
```

```nix
# home.nix or darwin.nix
programs.ak2k-skills = {
  enable = true;

  # Default: every registered skill, including the entire gws bundle.
  # Pass an explicit list to install a subset:
  # skills =
  #   [ "claude-sessions" "krisp-cli" "msgvault-query" ]
  #     ++ inputs.ak2k-skills.lib.bundles.gws;

  # Default: [ ".claude/skills" ".opencode/skills" ].
  # Override to target only one harness:
  # skillDirs = [ ".claude/skills" ];
};
```

The module installs each selected skill's CLI (if one exists) into
`home.packages` and symlinks the skill definition at `~/<skillDir>/<name>/`
for every configured `skillDir`.

## Registry introspection

```sh
# List every registered skill:
nix eval .#legacyPackages.aarch64-darwin.skill-registry --apply builtins.attrNames

# List skills in the gws bundle:
nix eval .#lib.bundles.gws --json | jq
```

## Adding a new skill

1. Create `<name>/` with `<name>.py`, `pyproject.toml`, `default.nix`, plus
   the skill definition under `skills/<name>/SKILL.md`.
2. In `<name>/default.nix`, add a `postInstall` that copies `../skills/<name>/.`
   into `$out/share/skills/<name>/` (copy the shape from
   [`krisp-cli/default.nix`](krisp-cli/default.nix)).
3. Register the package in `flake.nix` under `perSystem.packages`.
4. Add a registry entry in [`nix/registry.nix`](nix/registry.nix) pointing
   `source` at `$out/share/skills/<name>` and `package` at the new package.

For a docs-only skill (no binary), skip the package and point `source` at
the source tree directly — see the `siplink` entry as an example.

## Adding a new bundle

Bundles re-use one upstream flake's binary across many skills. To add one:

1. Add the upstream flake as an input in `flake.nix`.
2. Re-export its binary in `perSystem.packages.<name>`.
3. Extend [`nix/registry.nix`](nix/registry.nix) to enumerate the upstream's
   `skills/` tree (`readDir` + `filterAttrs` by `SKILL.md` existence) and
   emit one registry entry per directory, each pointing at the same package
   and tagged `bundle = "<name>"`.
4. Expose `flake.lib.bundles.<name>` for ergonomic consumer composition.
