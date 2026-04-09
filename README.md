# ak2k-skills

LLM-useful CLI tools and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills, packaged with Nix.

Structure and approach follows [Mic92/mics-skills](https://github.com/Mic92/mics-skills).

## Skills

| Skill | Description |
|-------|-------------|
| [claude-sessions](claude-sessions/) | List and search recent Claude Code sessions for resumption |
| [krisp-cli](krisp-cli/) | Dynamic CLI for Krisp's MCP server — search meetings, action items, transcripts |

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
};
```

## Adding a new skill

1. Create `<name>/` with `<name>.py`, `pyproject.toml`, `default.nix`, `README.md`
2. Create `skills/<name>/SKILL.md`
3. Add to `allSkills` in `home-manager.nix`
4. Add to `packages` in `flake.nix`
