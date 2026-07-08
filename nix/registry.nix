# Single source of truth for the skill name → { source, package?, bundle? }
# mapping. Consumed by home-manager.nix to wire skills into agent harness
# directories, and exposed at flake.legacyPackages.<system>.skill-registry
# for introspection (`nix eval .#legacyPackages.<system>.skill-registry
# --apply builtins.attrNames`).
#
# Entry fields (all optional except source):
#   source  — directory to symlink into each ~/<skillDir>/<name>/
#   package — added to home.packages, deduplicated across entries sharing it
#   bundle  — group marker; lets consumers treat a bundle as one unit
{
  lib,
  self,
  inputs,
  system,
}:
let
  sysPkgs = self.packages.${system};

  # gws bundle: every subdir of the upstream skills/ tree with a SKILL.md
  # becomes one registry entry pointing at the same `gws` binary.
  gwsSkillsDir = "${inputs.googleworkspace-cli}/skills";
  gwsEntries =
    lib.mapAttrs
      (name: _: {
        source = "${gwsSkillsDir}/${name}";
        package = sysPkgs.gws;
        bundle = "gws";
      })
      (
        lib.filterAttrs (
          name: type: type == "directory" && builtins.pathExists "${gwsSkillsDir}/${name}/SKILL.md"
        ) (builtins.readDir gwsSkillsDir)
      );

  # Skills whose files ship inside our own package outputs.
  ownEntries = {
    # atlassian-cli ships Atlassian's 5 official workflow skills as nested
    # subdirectories under workflows/ rather than as separate top-level
    # registry entries. Top-level registration would add ~625 idle tokens of
    # always-on context (5 description frontmatters loaded into every
    # session); nesting keeps the idle cost to one description (~55 tokens),
    # and the agent loads a workflow body via Read only after deciding the
    # atlassian-cli skill is relevant. See atlassian-cli/default.nix for
    # the bundling and skills/atlassian-cli/SKILL.md for the workflow index.
    atlassian-cli = {
      source = "${sysPkgs.atlassian-cli}/share/skills/atlassian-cli";
      package = sysPkgs.atlassian-cli;
    };
    claude-sessions = {
      source = "${sysPkgs.claude-sessions}/share/skills/claude-sessions";
      package = sysPkgs.claude-sessions;
    };
    gemtts = {
      source = "${sysPkgs.gemtts}/share/skills/gemtts";
      package = sysPkgs.gemtts;
    };
    kagi = {
      source = "${sysPkgs.kagi}/share/skills/kagi";
      package = sysPkgs.kagi;
    };
    krisp-cli = {
      source = "${sysPkgs.krisp-cli}/share/skills/krisp-cli";
      package = sysPkgs.krisp-cli;
    };
    msgvault-query = {
      source = "${sysPkgs.msgvault}/share/skills/msgvault-query";
      package = sysPkgs.msgvault;
    };
    # Umbrella skill only — its body routes to the 10 specialized skills
    # (pptx, word, excel, pitch-deck, financial-model, morph-ppt, ...) via
    # `officecli load_skill <name>` at runtime, keeping the idle-context
    # cost to one description (same reasoning as atlassian-cli's workflow
    # nesting above). SKILL.md is extracted from the binary at build time
    # (see officecliSkill in flake.nix), so it can't drift from the CLI.
    officecli = {
      source = "${sysPkgs.officecli-skill}/share/skills/officecli";
      package = sysPkgs.officecli;
    };
    pplx-agent-tools = {
      source = "${sysPkgs.pplx-agent-tools}/share/skills/pplx-agent-tools";
      package = sysPkgs.pplx-agent-tools;
    };
    # Docs-only skill: no binary in this flake. The source lives in the repo
    # tree directly — home-manager treats it the same as any other path.
    siplink = {
      source = ../skills/siplink;
    };
    # Docs-only: the CLIs these document ship from nix-config, not this flake.
    # cloak-browser = the stealth wrapper (scripts/cloak-browser.py);
    # agent-browser = general/authed browser automation (llm-agents binary).
    cloak-browser = {
      source = ../skills/cloak-browser;
    };
    agent-browser = {
      source = ../skills/agent-browser;
    };
    # surefetch: CLI binary from its own flake input; SKILL.md from this repo's tree.
    # `.browser` = the full ladder (core + the [browser] extra: camoufox render engine
    # + in-process adblock). The camoufox rung auto-joins the default ladder and
    # self-provisions its binary/filters on first walled fetch — no manual bootstrap.
    # Expose ONLY bin/surefetch: the `.browser` output is a full venv whose bin/python3
    # would collide with pplx-agent-tools' python3 in the merged home-manager profile.
    # The surefetch script's shebang references the venv's python by absolute path (and it
    # spawns camoufox via the Python API, not a PATH binary), so it still resolves its deps.
    surefetch = {
      source = ../skills/surefetch;
      package =
        let
          pkgs = inputs.nixpkgs.legacyPackages.${system};
        in
        pkgs.runCommand "surefetch-cli" { } ''
          mkdir -p $out/bin
          ln -s ${inputs.surefetch.packages.${system}.browser}/bin/surefetch $out/bin/surefetch
        '';
    };
  };
in
ownEntries // gwsEntries
