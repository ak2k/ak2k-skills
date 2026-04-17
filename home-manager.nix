{
  lib,
  config,
  googleworkspaceCliSrc,
  ...
}:
let
  cfg = config.programs.ak2k-skills;

  # Skills with a corresponding package in this flake.
  packagedSkills = [
    "claude-sessions"
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

    skillSets = lib.mkOption {
      default = { };
      description = ''
        Bundled skill sets sourced from other flake inputs. Each enabled set
        installs its associated binary into `home.packages` and symlinks one
        entry per SKILL.md into `~/.claude/skills/<name>/`.
      '';
      type = lib.types.submodule {
        options.gws = lib.mkOption {
          default = { };
          description = ''
            Google Workspace CLI (`gws`) from `googleworkspace/cli` — binary
            plus ~100 agent skills covering Gmail, Drive, Calendar, Sheets,
            Docs, Chat, Slides, Forms, Tasks, and more.
          '';
          type = lib.types.submodule {
            options = {
              enable = lib.mkEnableOption "Google Workspace CLI skills";

              skills = lib.mkOption {
                type = lib.types.nullOr (lib.types.listOf lib.types.str);
                default = null;
                description = ''
                  Filter — list of upstream skill directory names to install.
                  If `null` (the default), installs every skill shipped by
                  `googleworkspace/cli`.
                '';
                example = [
                  "gws-gmail"
                  "gws-drive"
                  "gws-calendar"
                  "persona-exec-assistant"
                ];
              };
            };
          };
        };
      };
    };
  };

  config = lib.mkIf cfg.enable (
    let
      gwsCfg = cfg.skillSets.gws;
      gwsSkillsDir = "${googleworkspaceCliSrc}/skills";
      gwsAvailable = lib.attrNames (
        lib.filterAttrs (
          name: type: type == "directory" && builtins.pathExists "${gwsSkillsDir}/${name}/SKILL.md"
        ) (builtins.readDir gwsSkillsDir)
      );
      gwsSelected = if gwsCfg.skills == null then gwsAvailable else gwsCfg.skills;
      gwsFiles = lib.optionalAttrs gwsCfg.enable (
        lib.listToAttrs (
          map (name: {
            name = ".claude/skills/${name}";
            value.source = "${gwsSkillsDir}/${name}";
          }) gwsSelected
        )
      );
    in
    {
      home.packages =
        map (name: cfg.package.${name}) (
          builtins.filter (name: builtins.elem name packagedSkills) cfg.skills
        )
        ++ lib.optional gwsCfg.enable cfg.package.gws;

      # Symlink only the selected skill directories.
      home.file =
        lib.listToAttrs (
          map (name: {
            name = ".claude/skills/${name}";
            value.source = "${cfg.skillsSrc}/skills/${name}";
          }) cfg.skills
        )
        // gwsFiles;
    }
  );
}
