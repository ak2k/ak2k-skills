{
  lib,
  buildPythonApplication,
  hatchling,
  click,
  xlrd,
  pyyaml,
  rich,
}:

buildPythonApplication {
  pname = "travel-rewards";
  version = "0.1.0";

  src = ./.;

  pyproject = true;

  build-system = [ hatchling ];

  dependencies = [
    click
    xlrd
    pyyaml
    rich
  ];

  meta = {
    description = "CLI for tracking travel rewards, loyalty points, and credit card benefits";
    mainProgram = "travel-rewards";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
}
