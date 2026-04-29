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

  # atlassian-mcp bundle: workflow skills shipped by Atlassian alongside
  # their Remote MCP server. They reference MCP tool names directly
  # (searchJiraIssuesUsingJql, getJiraIssue, createJiraIssue, etc.); our
  # atlassian-cli wrapper exposes the same names via `atlassian-cli call
  # <name>`, so the agent composes the two skills naturally — Atlassian's
  # workflow steps + our routing layer.
  atlassianMcpSkillsDir = "${inputs.atlassian-mcp-skills}/skills";
  atlassianMcpEntries =
    lib.mapAttrs
      (name: _: {
        source = "${atlassianMcpSkillsDir}/${name}";
        package = sysPkgs.atlassian-cli;
        bundle = "atlassian-mcp";
      })
      (
        lib.filterAttrs (
          name: type: type == "directory" && builtins.pathExists "${atlassianMcpSkillsDir}/${name}/SKILL.md"
        ) (builtins.readDir atlassianMcpSkillsDir)
      );

  # Skills whose files ship inside our own package outputs.
  ownEntries = {
    atlassian-cli = {
      source = "${sysPkgs.atlassian-cli}/share/skills/atlassian-cli";
      package = sysPkgs.atlassian-cli;
    };
    claude-sessions = {
      source = "${sysPkgs.claude-sessions}/share/skills/claude-sessions";
      package = sysPkgs.claude-sessions;
    };
    krisp-cli = {
      source = "${sysPkgs.krisp-cli}/share/skills/krisp-cli";
      package = sysPkgs.krisp-cli;
    };
    msgvault-query = {
      source = "${sysPkgs.msgvault}/share/skills/msgvault-query";
      package = sysPkgs.msgvault;
    };
    # Docs-only skill: no binary in this flake. The source lives in the repo
    # tree directly — home-manager treats it the same as any other path.
    siplink = {
      source = ../skills/siplink;
    };
  };
in
ownEntries // gwsEntries // atlassianMcpEntries
