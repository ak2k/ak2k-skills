{
  lib,
  buildPythonApplication,
  hatchling,
  click,
  httpx,
}:

buildPythonApplication {
  pname = "krisp-cli";
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
  skillSrc = ../skills/krisp-cli;
  postInstall = ''
    mkdir -p $out/share/skills/krisp-cli
    cp -r $skillSrc/. $out/share/skills/krisp-cli/
  '';

  meta = {
    description = "Dynamic CLI for Krisp's MCP server over Streamable HTTP";
    mainProgram = "krisp-cli";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
