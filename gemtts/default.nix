# gemtts - agent-friendly Gemini text-to-speech CLI (paperfoot/gemtts, MIT).
#
# Upstream publishes to crates.io but cuts no git tags, so we pin via
# `fetchCrate` (the published .crate tarball ships Cargo.lock for binaries).
# Conventions verified current against 2026 nixos-unstable:
#   - `hash` (SRI) on fetchCrate, plain `cargoHash` (useFetchCargoVendor is the
#     transparent default since 25.05 - do not set it).
#   - reqwest uses rustls-tls (ring backend) => no openssl/pkg-config, and no
#     darwin.apple_sdk.frameworks (removed after the unified Apple SDK move).
#   - `cargoDepsName = pname` keeps the vendor hash stable across version bumps
#     so Renovate's nix-update postUpgrade only has to refresh `hash`.
{
  lib,
  rustPlatform,
  fetchCrate,
}:

rustPlatform.buildRustPackage (finalAttrs: {
  pname = "gemtts";
  version = "0.1.4";

  src = fetchCrate {
    inherit (finalAttrs) pname version;
    hash = "sha256-FC7JYYLZNTYhaIwFE9j3Izrl5dfIWomuVkbMXLTavuk=";
  };

  cargoHash = "sha256-l5bxKL/zsX8h3Rmqf+inEY6/uM66Hns8oP9M42tLCBM=";
  cargoDepsName = finalAttrs.pname;

  # Integration tests use assert_cmd and reach the live Gemini TTS API.
  doCheck = false;

  # Ship the skill definition inside the package output so the home-manager
  # registry and non-home-manager consumers both find it at a stable path.
  skillSrc = ../skills/gemtts;
  postInstall = ''
    mkdir -p $out/share/skills/gemtts
    cp -r $skillSrc/. $out/share/skills/gemtts/
  '';

  meta = {
    description = "Agent-friendly Gemini text-to-speech CLI for expressive voices, tags, and scripts";
    homepage = "https://github.com/paperfoot/gemtts";
    mainProgram = "gemtts";
    license = lib.licenses.mit;
    maintainers = [ ];
  };
})
