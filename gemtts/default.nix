# gemtts - agent-friendly Gemini text-to-speech CLI (paperfoot/gemtts, MIT).
#
# Upstream publishes to crates.io but cuts no git tags, so we pin via
# `fetchCrate` (the published .crate tarball ships Cargo.lock for binaries).
# Conventions verified current against 2026 nixos-unstable:
#   - `hash` (SRI) on fetchCrate, plain `cargoHash` (useFetchCargoVendor is the
#     transparent default since 25.05 - do not set it).
#   - reqwest uses rustls-tls (ring backend), BUT the `self_update` dep pulls in
#     `openssl-sys` via native-tls (self-replace/zipsign-api), so we still need
#     pkg-config + openssl. This builds on darwin via the SDK's OpenSSL but fails
#     on Linux without them. No darwin.apple_sdk.frameworks (removed after the
#     unified Apple SDK move).
#   - `cargoDepsName = pname` keeps the vendor hash stable across version bumps
#     so Renovate's nix-update postUpgrade only has to refresh `hash`.
{
  lib,
  rustPlatform,
  fetchCrate,
  pkg-config,
  openssl,
}:

rustPlatform.buildRustPackage (finalAttrs: {
  pname = "gemtts";
  version = "0.1.4";

  src = fetchCrate {
    inherit (finalAttrs) pname version;
    hash = "sha256-FC7JYYLZNTYhaIwFE9j3Izrl5dfIWomuVkbMXLTavuk=";
  };

  cargoHash = "sha256-0SlEBYFm4rBNes5LHiJSXJoBRucneQy9MQnao8EOCkQ=";
  cargoDepsName = finalAttrs.pname;

  # openssl-sys (pulled in transitively by self_update) needs pkg-config to
  # locate openssl at build time.
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ openssl ];

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
