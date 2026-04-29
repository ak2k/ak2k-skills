{
  lib,
  buildPythonApplication,
  hatchling,
  click,
  httpx,
  atlassianMcpSkills,
}:

buildPythonApplication {
  pname = "atlassian-cli";
  version = "0.1.0";

  src = ./.;

  pyproject = true;

  build-system = [ hatchling ];

  dependencies = [
    click
    httpx
  ];

  # Ship the skill definition inside the package output so the home-manager
  # registry and non-home-manager consumers both find it at a stable path.
  #
  # Atlassian's 5 official workflow skills (triage-issue, spec-to-backlog,
  # capture-tasks-from-meeting-notes, generate-status-report,
  # search-company-knowledge) ride along under workflows/. They are NOT
  # registered as top-level skills in the registry — exposing 5 separate
  # entries adds ~625 idle tokens of always-on context (their description
  # frontmatter loads in every Claude Code session). Nesting them keeps the
  # idle cost to one description (~55 tokens, ours), and the agent loads a
  # specific workflow body via Read only after deciding the atlassian-cli
  # skill is relevant.
  skillSrc = ../skills/atlassian-cli;
  inherit atlassianMcpSkills;
  postInstall = ''
    mkdir -p $out/share/skills/atlassian-cli
    cp -r $skillSrc/. $out/share/skills/atlassian-cli/
    mkdir -p $out/share/skills/atlassian-cli/workflows
    cp -r $atlassianMcpSkills/. $out/share/skills/atlassian-cli/workflows/
  '';

  meta = {
    description = "Dynamic CLI for Atlassian's Remote MCP server over Streamable HTTP";
    mainProgram = "atlassian-cli";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
