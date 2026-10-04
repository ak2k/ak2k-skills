{
  lib,
  buildPythonApplication,
  hatchling,
  beautifulsoup4,
}:

buildPythonApplication {
  pname = "kagi";
  version = "0.3.0";

  src = ./.;

  pyproject = true;

  build-system = [ hatchling ];

  dependencies = [ beautifulsoup4 ];

  # Ship the skill definition inside the package output so the home-manager
  # registry and non-home-manager consumers both find it at a stable path.
  skillSrc = ../skills/kagi;
  postInstall = ''
    mkdir -p $out/share/skills/kagi
    cp -r $skillSrc/. $out/share/skills/kagi/
  '';

  meta = {
    description = "Multi-verb CLI for Kagi (search + summarize) using session tokens";
    mainProgram = "kagi";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
