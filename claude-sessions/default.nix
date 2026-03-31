{
  lib,
  buildPythonApplication,
  hatchling,
  click,
}:

buildPythonApplication {
  pname = "claude-sessions";
  version = "0.1.0";

  src = ./.;

  pyproject = true;

  build-system = [ hatchling ];

  dependencies = [ click ];

  meta = {
    description = "List and search recent Claude Code sessions for easy resumption";
    mainProgram = "claude-sessions";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
