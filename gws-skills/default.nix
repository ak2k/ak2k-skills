# Transformed gws skills tree: the upstream googleworkspace/cli skills with
# each service's verb-helpers nested under references/ (see transform.py).
# Shipped at $out/share/skills/<name>/ so nix/registry.nix can symlink each
# top-level skill from a stable path, the same shape as our other packages.
{
  lib,
  runCommandLocal,
  python3,
  gwsSkillsSrc,
}:
# transform.py nests verb-helpers and applies the authored description overrides
# (overrides/gws-descriptions.json, produced by generate-descriptions.py), then
# asserts no dead links and full verb coverage.
runCommandLocal "gws-skills"
  {
    meta = {
      description = "googleworkspace/cli Claude Code skills, verb-helpers nested as references/";
      license = lib.licenses.asl20;
    };
  }
  ''
    mkdir -p "$out/share/skills"
    cp -r ${gwsSkillsSrc}/. "$out/share/skills/"
    chmod -R u+w "$out/share/skills"
    ${python3}/bin/python3 ${./transform.py} "$out/share/skills" ${./overrides/gws-descriptions.json}
  ''
