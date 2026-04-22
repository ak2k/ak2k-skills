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

  # Ship the skill definition inside the package output so the home-manager
  # registry and non-home-manager consumers both find it at a stable path.
  skillSrc = ../skills/claude-sessions;
  postInstall = ''
    mkdir -p $out/share/skills/claude-sessions
    cp -r $skillSrc/. $out/share/skills/claude-sessions/
  '';

  meta = {
    description = "List and search recent Claude Code sessions for easy resumption";
    mainProgram = "claude-sessions";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
