# msgvault - local email/chat archive with DuckDB analytics, FTS5 and vector
# search (kenn-io/msgvault, Apache-2.0).
#
# Upstream ships no Nix packaging (kenn-io/msgvault#767), so this builds the
# tag tree that `inputs.msgvault` pins. `src` stays a flake input rather than a
# fetcher because consumers gate on it: ak2k/nix-config holds every msgvault
# bump for a human by comparing `nodes.msgvault` across its flake.lock.
#
# The web UI is not built. Its assets need a bun2nix lock regenerated whenever
# the frontend's dependencies change, so the binary serves the embedded
# stub.html instead.
{
  lib,
  buildGoLatestModule,
  sqlite,
  src,
  version,
}:

# Upstream raises its go.mod floor ahead of nixpkgs' default Go (0.20.0 needs
# 1.27.0 while `go` is 1.26).
buildGoLatestModule {
  pname = "msgvault";
  inherit src version;

  # Renovate refreshes this on every msgvault bump by running
  # `nix run .#msgvault-vendor-hash` (see renovate.json).
  vendorHash = "sha256-IwbOjkcaZuwf1QcHxVU3paZckSYZPG/5NUMXY1J0ZVc=";
  proxyVendor = true;

  subPackages = [ "cmd/msgvault" ];

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

  meta = {
    description = "Local email and chat archive with analytics and search";
    homepage = "https://github.com/kenn-io/msgvault";
    license = lib.licenses.asl20;
    mainProgram = "msgvault";
  };
}
