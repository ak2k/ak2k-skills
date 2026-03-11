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

  meta = {
    description = "Dynamic CLI for Krisp's MCP server over Streamable HTTP";
    mainProgram = "krisp-cli";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
