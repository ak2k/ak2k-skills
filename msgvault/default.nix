# msgvault - local email/chat archive with DuckDB analytics, FTS5 and vector
# search (kenn-io/msgvault, Apache-2.0).
#
# Upstream ships no Nix packaging (kenn-io/msgvault#767), so this builds the
# tag tree that `inputs.msgvault` pins. `src` stays a flake input rather than a
# fetcher because consumers gate on it: ak2k/nix-config holds every msgvault
# bump for a human by comparing `nodes.msgvault` across its flake.lock.
{
  lib,
  stdenvNoCC,
  buildGoLatestModule,
  bun,
  nodejs,
  sqlite,
  src,
  version,
}:

let
  # Renovate refreshes both hashes on every msgvault bump by running
  # `nix run .#msgvault-update-hashes` (see renovate.json).
  webHash = "sha256-jlzfZOGDu3gf2SDP6RnMi8CP03kUGhb7q7q/c3Hoqjg=";
  vendorHash = "sha256-6Onwxqfv3w80Ve43yEgEudDoMItWyT94g4xksA0HwqY=";

  # The web UI that `msgvault serve` embeds; without it the binary carries
  # only a stub and answers 404 at `/`. Fixed-output so bun can fetch from
  # the npm registry. The built assets are platform-independent, so one hash
  # covers every system.
  web = stdenvNoCC.mkDerivation {
    pname = "msgvault-web";
    inherit src version;

    nativeBuildInputs = [
      bun
      nodejs
    ];

    dontConfigure = true;
    # Fixup would rewrite files in $out, and a fixed-output path may not
    # reference the store.
    dontFixup = true;

    # The same steps as upstream's `make web-embed`, including its check that
    # nothing hidden or credential-shaped reaches the embedded tree.
    buildPhase = ''
      runHook preBuild
      export HOME=$TMPDIR
      pushd web
      bun install --frozen-lockfile --no-progress
      # Vite's bin uses `#!/usr/bin/env node`, which the Linux sandbox lacks.
      patchShebangs node_modules
      bun run generate
      bun run build
      popd
      find internal/web/dist -mindepth 1 -maxdepth 1 ! -name stub.html -exec rm -rf {} +
      cp -R web/dist/. internal/web/dist/
      node scripts/check-web-assets.mjs
      runHook postBuild
    '';

    installPhase = ''
      cp -R internal/web/dist $out
    '';

    outputHashMode = "recursive";
    outputHash = webHash;
  };
in
# Upstream raises its go.mod floor ahead of nixpkgs' default Go (0.20.0 needs
# 1.27.0 while `go` is 1.26).
buildGoLatestModule {
  pname = "msgvault";
  inherit src version vendorHash;
  proxyVendor = true;

  subPackages = [ "cmd/msgvault" ];

  preBuild = ''
    cp -R ${web}/. internal/web/dist/
  '';
  # The module download needs no web assets.
  overrideModAttrs = _: { preBuild = ""; };

  # go-sqlite3, duckdb-go and sqlite-vec-go-bindings all link C code.
  env.CGO_ENABLED = 1;
  # sqlite-vec-go-bindings includes sqlite3.h but ships no sqlite source.
  buildInputs = [ sqlite ];

  tags = [
    "fts5"
    "sqlite_vec"
  ];

  # The `v` prefix matches upstream's release builds, which stamp the tag.
  ldflags = [
    "-s"
    "-w"
    "-X go.kenn.io/msgvault/cmd/msgvault/cmd.Version=v${version}"
    "-X go.kenn.io/msgvault/cmd/msgvault/cmd.Commit=${src.shortRev or "unknown"}"
  ];

  # The suite is upstream CI's job; this derivation only packages the tag.
  doCheck = false;

  postInstall = ''
    mkdir -p $out/share/skills/msgvault-query
    cp -r ${src}/skills/claude-code/. $out/share/skills/msgvault-query/
  '';

  passthru = { inherit web; };

  meta = {
    description = "Local email and chat archive with analytics and search";
    homepage = "https://github.com/kenn-io/msgvault";
    license = lib.licenses.asl20;
    mainProgram = "msgvault";
  };
}
