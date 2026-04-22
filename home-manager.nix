# Home-manager module that installs ak2k-skills CLI binaries and symlinks
# skill definitions into one or more agent harness directories. Reads the
# registry via `_module.args.registry` (threaded in by flake.nix).
{
  lib,
  config,
  registry,
  ...
}:
let
  cfg = config.programs.ak2k-skills;
  allSkills = builtins.attrNames registry;
in
{
  imports = [ ./nix/skills-common.nix ];

  options.programs.ak2k-skills = {
    enable = lib.mkEnableOption "ak2k-skills LLM agent tools";

    skills = lib.mkOption {
      type = lib.types.listOf (lib.types.enum allSkills);
      default = allSkills;
      description = ''
        Skills to install. Each entry installs the CLI (if its registry
        entry has a `package`) into `home.packages` and symlinks the skill
        definition into every directory in `programs.ak2k-skills.skillDirs`.

        Defaults to every registered skill — including bundles like gws.
        To install a subset, pass an explicit list. The
        `inputs.ak2k-skills.lib.bundles.<name>` helper returns the skill
        names for a given bundle so you can compose them ergonomically:

            skills = [ "claude-sessions" "msgvault-query" ]
              ++ inputs.ak2k-skills.lib.bundles.gws;
      '';
      example = lib.literalExpression ''
        [ "claude-sessions" "krisp-cli" "msgvault-query" ]
          ++ inputs.ak2k-skills.lib.bundles.gws
      '';
    };

    skillsSrc = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Deprecated. Skill files now ship inside each package at
        `$out/share/skills/<name>/` (or are sourced directly from the flake
        input for external bundles); this option is ignored.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    warnings =
      lib.optional (cfg.skillsSrc != null)
        "programs.ak2k-skills.skillsSrc is deprecated and ignored; skill files now ship inside each package or are sourced from the flake input directly.";

    home.packages = lib.unique (
      lib.filter (p: p != null) (map (name: registry.${name}.package or null) cfg.skills)
    );

    home.file = lib.listToAttrs (
      lib.concatMap (
        name:
        map (dir: {
          name = "${dir}/${name}";
          value.source = registry.${name}.source;
        }) cfg.skillDirs
      ) cfg.skills
    );
  };
}
