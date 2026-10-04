# Partitions the upstream googleworkspace/cli skills tree into the skills that
# stay top-level vs. the verb-helpers that get nested under their service
# parent as references/ (progressive disclosure — see gws-skills/transform.py).
#
# Single source of truth for the membership rule, consumed by both flake.nix
# (lib.bundles.gws) and nix/registry.nix (gwsEntries). The transform script
# implements the SAME rule in bash; the derivation's dead-link assertion plus
# the registry pointing at the transformed output make any divergence fail
# loudly (broken symlink / dead link) rather than ship silently.
#
# Nesting rule: a directory `gws-<svc>-<verb>` is nested under `gws-<svc>` iff
# that parent directory exists AND the family is not `gws-workflow-*`. Workflow
# skills are compound entry points meant to stay discoverable at the top level,
# not detail pages; `gws-admin-reports` has no `gws-admin` parent so it stays
# standalone.
{
  lib,
  gwsSkillsDir,
}:
let
  hasSkill = name: builtins.pathExists "${gwsSkillsDir}/${name}/SKILL.md";

  # gws-<svc>-<verb> with an existing gws-<svc> parent, excluding workflows.
  isNestedHelper =
    name:
    let
      m = builtins.match "gws-([a-z]+)-(.+)" name;
    in
    m != null && (builtins.elemAt m 0) != "workflow" && hasSkill "gws-${builtins.elemAt m 0}";

  allNames = lib.attrNames (
    lib.filterAttrs (name: type: type == "directory" && hasSkill name) (builtins.readDir gwsSkillsDir)
  );
in
{
  # Skills registered as top-level entries (parents, standalones, recipes,
  # personas, workflows). These are what consumers list in their skills set.
  topLevel = lib.filter (n: !isNestedHelper n) allNames;

  # Verb-helpers folded into their parent's references/ by the transform.
  nested = lib.filter isNestedHelper allNames;
}
