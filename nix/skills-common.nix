# Shared option module imported by the main home-manager module.
# `skillDirs` controls which agent harnesses receive skill definitions —
# defaults to both Claude Code and opencode so a single `enable` reaches
# every agent the user is likely to run.
{ lib, ... }:
{
  key = "ak2k-skills/common";

  options.programs.ak2k-skills = {
    skillDirs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        ".claude/skills"
        ".opencode/skills"
      ];
      example = [ ".claude/skills" ];
      description = ''
        Home-relative directories into which each enabled skill is symlinked
        as `<dir>/<skill>/`. One entry per agent harness that should discover
        the skills.
      '';
    };
  };
}
