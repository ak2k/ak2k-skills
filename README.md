# ak2k-skills

LLM-useful CLI tools and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills, packaged with Nix.

Structure and approach follows [Mic92/mics-skills](https://github.com/Mic92/mics-skills).

## Skills

| Skill | Description |
|-------|-------------|
| [claude-sessions](claude-sessions/) | List and search recent Claude Code sessions for resumption |
| [krisp-cli](krisp-cli/) | Dynamic CLI for Krisp's MCP server — search meetings, action items, transcripts |
| [siplink](skills/siplink/) | Place a phone call via VoIP.ms (binary from elsewhere) |

## Skill sets

Bundled skill sets sourced from other flake inputs. Each set installs a binary
plus one `SKILL.md` per subdirectory of the upstream source.

| Set | Description |
|-----|-------------|
| `gws` | Google Workspace CLI from [`googleworkspace/cli`](https://github.com/googleworkspace/cli) — ~100 skills covering Gmail, Drive, Calendar, Sheets, Docs, Chat, Slides, Forms, Tasks, and more |

## Installation

Add as a flake input and enable via home-manager:

```nix
# flake.nix
inputs.ak2k-skills.url = "github:ak2k/ak2k-skills";
inputs.ak2k-skills.inputs.nixpkgs.follows = "nixpkgs-unstable";

# Pass to home-manager and import the module:
home-manager.extraSpecialArgs = {
  ak2k-skills = inputs.ak2k-skills;
};
home-manager.sharedModules = [
  inputs.ak2k-skills.homeManagerModules.default
];
```

```nix
# home.nix or darwin.nix
programs.ak2k-skills = {
  enable = true;
  package = ak2k-skills.packages.${pkgs.stdenv.hostPlatform.system};
  skillsSrc = ak2k-skills;
  skills = [ "krisp-cli" ];

  # Optional: enable the Google Workspace CLI skill set
  skillSets.gws.enable = true;
  # Or install only a subset:
  # skillSets.gws = {
  #   enable = true;
  #   skills = [ "gws-gmail" "gws-drive" "persona-exec-assistant" ];
  # };
};
```

## Adding a new skill

1. Create `<name>/` with `<name>.py`, `pyproject.toml`, `default.nix`, `README.md`
2. Create `skills/<name>/SKILL.md`
3. Add to `allSkills` in `home-manager.nix`
4. Add to `packages` in `flake.nix`

## Adding a new skill set

Skill sets bundle ~N upstream skills from another flake under a single
opt-in option. To add one:

1. Add the upstream flake as an input in `flake.nix`
2. Re-export its binary in `packages.<name>` (perSystem)
3. Thread the source into the module via `_module.args.<name>Src` in
   `flake.homeManagerModules.default`
4. Add a `skillSets.<name>` option to `home-manager.nix` with `enable` and
   optional `skills` filter; wire it to `home.packages` / `home.file`
