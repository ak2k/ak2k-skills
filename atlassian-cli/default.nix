{
  lib,
  buildPythonApplication,
  hatchling,
  click,
  httpx,
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
  skillSrc = ../skills/atlassian-cli;
  postInstall = ''
    mkdir -p $out/share/skills/atlassian-cli
    cp -r $skillSrc/. $out/share/skills/atlassian-cli/
  '';

  meta = {
    description = "Dynamic CLI for Atlassian's Remote MCP server over Streamable HTTP";
    mainProgram = "atlassian-cli";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
