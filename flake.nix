{
  description = "LLM-useful CLI tools and skills";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";

    # Google Workspace CLI — upstream flake ships binary + ~100 agent skills
    # (Gmail, Drive, Calendar, Sheets, Docs, Chat, Slides, Forms, Tasks, etc.)
    # Pinned to a release tag so Renovate can track it via github-releases.
    googleworkspace-cli.url = "github:googleworkspace/cli/v0.22.5";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];

      imports = [
        inputs.treefmt-nix.flakeModule
      ];

      flake.homeManagerModules.default =
        { ... }:
        {
          imports = [ ./home-manager.nix ];
          _module.args.googleworkspaceCliSrc = inputs.googleworkspace-cli;
        };

      perSystem =
        {
          pkgs,
          self',
          lib,
          system,
          ...
        }:
        {
          checks =
            let
              packages = lib.mapAttrs' (n: lib.nameValuePair "package-${n}") self'.packages;
            in
            packages;

          packages = {
            claude-sessions = pkgs.python3.pkgs.callPackage ./claude-sessions { };
            krisp-cli = pkgs.python3.pkgs.callPackage ./krisp-cli { };

            # Re-exported from upstream so consumers can pull binary + skills
            # from ak2k-skills as a single input.
            gws = inputs.googleworkspace-cli.packages.${system}.default;
          };

          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            programs.ruff.format = true;
            programs.ruff.check = true;

            programs.mypy.enable = true;
            programs.mypy.directories = {
              "claude-sessions" = {
                extraPythonPackages = with pkgs.python3.pkgs; [
                  click
                ];
              };
              "krisp-cli" = {
                extraPythonPackages = with pkgs.python3.pkgs; [
                  click
                  httpx
                ];
              };
            };

            settings.global.excludes = [
              "*.lock"
              "*.toml"
              "*.png"
              "*.svg"
            ];
          };
        };
    };
}
