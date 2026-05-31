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

    # msgvault — local email/chat archive (Gmail, IMAP, WhatsApp, MBOX,
    # Apple Mail) with DuckDB analytics + FTS5 + optional vector search +
    # MCP server. Upstream flake ships the binary and one Claude Code skill;
    # we re-export with a corrected Version ldflag (upstream hardcodes
    # "nix-dev") and copy the skill tree into $out/share/skills/msgvault-query/
    # so it flows through the uniform registry like every other skill.
    #
    # NOTE: `msgvaultVersion` below must match the tag in this URL. Both are
    # tracked by one Renovate custom-manager entry, and the
    # `msgvault-version-matches` flake check fails the build on drift.
    msgvault.url = "github:wesm/msgvault/v0.14.0";

    # Atlassian's official Remote MCP server repo — we don't need the server
    # itself (our atlassian-cli wraps it remotely), but the repo ships 5
    # high-quality workflow skills (triage-issue, spec-to-backlog,
    # capture-tasks-from-meeting-notes, generate-status-report,
    # search-company-knowledge) under skills/. They are bundled INTO the
    # atlassian-cli package output under share/skills/atlassian-cli/workflows/
    # rather than registered as top-level skills — top-level registration
    # adds ~625 idle tokens of always-on context per session for the five
    # description frontmatters; nesting limits the cost to ours alone (~55
    # tokens). The agent loads a workflow body via Read only after deciding
    # the atlassian-cli skill is relevant.
    atlassian-mcp-skills.url = "github:atlassian/atlassian-mcp-server";
    atlassian-mcp-skills.flake = false;

    # pplx-agent-tools — agent toolkit for Perplexity (web-session cookie
    # auth, no API key). The flake ships a single `pplx` console script
    # and a SKILL.md at $out/share/skills/pplx-agent-tools/. We re-export
    # the package + register the skill via nix/registry.nix.
    # Pinned to a tag so Renovate's github-releases regex manager auto-bumps
    # us on every new pplx-agent-tools release.
    pplx-agent-tools.url = "github:ak2k/pplx-agent-tools/v0.3.3";
    pplx-agent-tools.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    inputs@{ flake-parts, nixpkgs, ... }:
    let
      inherit (nixpkgs) lib;

      # Keep in lockstep with `inputs.msgvault.url`'s tag. Renovate manages
      # both; the msgvault-version-matches check asserts they agree.
      msgvaultVersion = "0.14.0";

      # gws bundle membership is system-agnostic — derived from the upstream
      # source tree, the same list on every platform.
      gwsSkillsDir = "${inputs.googleworkspace-cli}/skills";
      gwsBundleSkills = lib.attrNames (
        lib.filterAttrs (
          name: type: type == "directory" && builtins.pathExists "${gwsSkillsDir}/${name}/SKILL.md"
        ) (builtins.readDir gwsSkillsDir)
      );
    in
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

      # Ergonomic helper for consumers: include a bundle in their skills list.
      #
      #     programs.ak2k-skills.skills =
      #       [ "claude-sessions" "msgvault-query" ]
      #         ++ inputs.ak2k-skills.lib.bundles.gws;
      flake.lib.bundles.gws = gwsBundleSkills;

      flake.homeManagerModules.default =
        { pkgs, ... }:
        let
          system = pkgs.stdenv.hostPlatform.system;
          registry = import ./nix/registry.nix {
            inherit lib system inputs;
            self = inputs.self;
          };
        in
        {
          imports = [ ./home-manager.nix ];
          _module.args.registry = registry;
        };

      perSystem =
        {
          pkgs,
          self',
          lib,
          system,
          ...
        }:
        let
          # Override upstream's package to (a) report the real version via
          # `msgvault --version` rather than "nix-dev", (b) correct the
          # derivation name (upstream's flake.nix at tag v0.14.0 still carries
          # a stale `version = "0.13.1"` literal), (c) ship the Claude Code
          # skill under $out/share/skills/msgvault-query/ for the registry.
          msgvaultPkg = inputs.msgvault.packages.${system}.default.overrideAttrs (old: {
            # We're intentionally replacing upstream's stale `version = "0.13.1"`
            # with the real tag; silence nixpkgs's warning about version bumps.
            __intentionallyOverridingVersion = true;
            version = msgvaultVersion;
            name = "msgvault-${msgvaultVersion}";
            ldflags = [
              "-X github.com/wesm/msgvault/cmd/msgvault/cmd.Version=v${msgvaultVersion}"
            ];
            postInstall = (old.postInstall or "") + ''
              mkdir -p $out/share/skills/msgvault-query
              cp -r ${inputs.msgvault}/skills/claude-code/. $out/share/skills/msgvault-query/
            '';
          });
        in
        {
          packages = {
            atlassian-cli = pkgs.python3.pkgs.callPackage ./atlassian-cli {
              atlassianMcpSkills = "${inputs.atlassian-mcp-skills}/skills";
            };
            claude-sessions = pkgs.python3.pkgs.callPackage ./claude-sessions { };
            gemtts = pkgs.callPackage ./gemtts { };
            kagi = pkgs.python3.pkgs.callPackage ./kagi { };
            krisp-cli = pkgs.python3.pkgs.callPackage ./krisp-cli { };
            gws = inputs.googleworkspace-cli.packages.${system}.default;
            msgvault = msgvaultPkg;
            pplx-agent-tools = inputs.pplx-agent-tools.packages.${system}.default;
          };

          # Debug handle. Inspect with:
          #   nix eval .#legacyPackages.<system>.skill-registry --apply builtins.attrNames
          legacyPackages.skill-registry = import ./nix/registry.nix {
            inherit lib system inputs;
            self = inputs.self;
          };

          checks =
            let
              packageChecks = lib.mapAttrs' (n: lib.nameValuePair "package-${n}") self'.packages;
            in
            packageChecks
            // {
              # Drift guard: Renovate manages the `inputs.msgvault.url` tag and
              # the `msgvaultVersion` literal in lockstep via one custom-manager
              # entry. If they somehow desynchronise, the binary's reported
              # version will not match the literal — and this check catches it
              # before the release goes out.
              msgvault-version-matches = pkgs.runCommand "msgvault-version-matches" { } ''
                got=$(${self'.packages.msgvault}/bin/msgvault version 2>&1 || true)
                echo "msgvault reports:"
                echo "$got"
                echo "$got" | grep -qF "v${msgvaultVersion}" || {
                  echo
                  echo "ERROR: 'msgvault version' does not report 'v${msgvaultVersion}'."
                  echo "This usually means the inputs.msgvault URL and the"
                  echo "msgvaultVersion literal in flake.nix have desynchronised."
                  echo "Fix both to match."
                  exit 1
                }
                touch $out
              '';
            };

          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            programs.ruff.format = true;
            programs.ruff.check = true;

            programs.mypy.enable = true;
            programs.mypy.directories = {
              "atlassian-cli" = {
                extraPythonPackages = with pkgs.python3.pkgs; [
                  click
                  httpx
                ];
              };
              "claude-sessions" = {
                extraPythonPackages = with pkgs.python3.pkgs; [
                  click
                ];
              };
              "kagi" = {
                extraPythonPackages = with pkgs.python3.pkgs; [
                  beautifulsoup4
                  types-beautifulsoup4
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
