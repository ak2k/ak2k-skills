{
  lib,
  config,
  ...
}:
let
  cfg = config.programs.ak2k-skills;

  # Skills with a corresponding package in this flake.
  packagedSkills = [
    "krisp-cli"
  ];

  # Skills that only provide a SKILL.md (package comes from elsewhere).
  skillOnlySkills = [
    "siplink"
  ];

  allSkills = packagedSkills ++ skillOnlySkills;
in
{
  options.programs.ak2k-skills = {
    enable = lib.mkEnableOption "ak2k-skills LLM agent tools";

    skills = lib.mkOption {
      type = lib.types.listOf (lib.types.enum allSkills);
      default = allSkills;
      description = ''
        Which skills to install. Each entry installs the CLI tool into
        `home.packages` and the corresponding skill definition into
        `~/.claude/skills/<name>/`.

        Defaults to all available skills.
      '';
      example = [
        "krisp-cli"
      ];
    };

    package = lib.mkOption {
      type = lib.types.attrsOf lib.types.package;
      description = ''
        Attribute set of ak2k-skills packages (e.g.
        `inputs.ak2k-skills.packages.''${system}`).
      '';
    };

    skillsSrc = lib.mkOption {
      type = lib.types.path;
      description = ''
        Path to the ak2k-skills source tree. Used to locate the `skills/`
        directory. Typically `inputs.ak2k-skills` (the flake source).
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = map (name: cfg.package.${name}) (builtins.filter (name: builtins.elem name packagedSkills) cfg.skills);

    # Symlink only the selected skill directories.
    home.file = lib.listToAttrs (
      map (name: {
        name = ".claude/skills/${name}";
        value.source = "${cfg.skillsSrc}/skills/${name}";
      }) cfg.skills
    );
  };
}
