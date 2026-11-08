# prose-gate — deterministic AI-tell lint for external-bound prose.
#
# Wraps vale with four pinned community style packages plus a personal style
# compiled from the author's language-editing notes:
#
#   ai-tells / ai-tells-commits (tbhb/vale-ai-tells) — AI-prose fingerprints,
#     plus commit-message tells (self-narration, buzzword pairs, attribution
#     trailers, gitmoji).
#   ai-tells-experimental (same upstream) — document-level density and
#     uniformity metrics plus per-token vocabulary and formatting checks, all
#     at warning level. It supplies the length signal: without it the default
#     config had none at all (a 142-word sentence drew no finding), and only
#     `--ste` caps length, at 25 words, which fights the house register.
#   Slop (Syntaf/vale-llm-slop) — slop vocabulary, fake enthusiasm, comments
#     that restate code.
#   Personal — the private-review vocabulary and internal-tooling names that
#     must never reach external readers (error level: these are what make the
#     gate exit nonzero).
#
# Every style is pinned at build time, so there is no `vale sync` and no
# network at runtime. The ai-tells packages come from the vale-ai-tells flake
# input's source tree (`valeAiTells`). vale-llm-slop stays a release-zip
# fetchzip; its hash is a fetchzip NAR hash (its postFetch chmod normalization
# means `nix-prefetch-url --unpack` values do NOT match — take the hash from
# the mismatch error on a fake-hash build). The fix half of the gate is the
# `humanizer` skill; the orchestration is skills/prose-gate/SKILL.md.
{
  valeAiTells,
  ponytail,
  fetchzip,
  runCommand,
  symlinkJoin,
  writeShellApplication,
  vale,
}:
let
  llmSlop = fetchzip {
    url = "https://github.com/Syntaf/vale-llm-slop/releases/download/v0.1.0/vale-llm-slop.zip";
    hash = "sha256-kaQ3lSuCkN9pAhZVxyj8hNlHTNuudKruvdLhdq6u4A4=";
    stripRoot = false;
  };

  # The vale-llm-slop zip wraps its content in one top-level directory (kept,
  # since stripRoot = false); the globs step over it without naming it.
  styles = runCommand "prose-gate-styles" { } ''
    mkdir -p "$out"
    cp -r ${valeAiTells}/styles/ai-tells "$out/ai-tells"
    mkdir -p "$out/ai-tells-commits"
    cp ${valeAiTells}/styles/ai-tells-commits/*.yml "$out/ai-tells-commits/"
    cp -r ${valeAiTells}/styles/ai-tells-experimental "$out/ai-tells-experimental"
    # vale resolves a `script:` rule against <StylesPath>/config/scripts, so
    # the Tengo files come from the sibling config/scripts directory
    # (upstream keeps them beside the style directory, never inside it).
    mkdir -p "$out/config/scripts"
    cp ${valeAiTells}/styles/config/scripts/*.tengo "$out/config/scripts/"
    cp -r ${llmSlop}/*/styles/Slop "$out/Slop"
    cp -r ${llmSlop}/*/styles/STE "$out/STE"
    # vale hands an occurrence rule's observed count to its message as a
    # string, so any such rule whose message uses %d renders "%!d(string=3)"
    # in place of the number. Five enabled rules carry it, each patched until
    # the pin that supplies it ships a fix; the three STE ones are
    # Syntaf/vale-llm-slop#2. Slop/EmDash has the same defect and is left
    # alone, being off in every mode.
    chmod -R u+w "$out/STE" "$out/ai-tells" "$out/ai-tells-experimental"
    for f in \
      STE/SentenceLength \
      STE/ProcedureLength \
      STE/ParagraphLength \
      ai-tells/VerbTricolonDensity \
      ai-tells-experimental/NegationDensity; do
      substituteInPlace "$out/$f.yml" --replace-fail '%d' '%s'
    done
    cp -r ${./styles/Personal} "$out/Personal"
  '';

  # Package-rule overrides, tuned on the author's own agent-written commits and
  # PR bodies (2026-08-26; re-measured 2026-11-08 at v1.37.0 over 40 merged PR
  # bodies and 60 commit bodies: tuned, the PR bodies draw 42 errors, 11
  # warnings and 26 suggestions, 19 of 40 with an error; the commit bodies draw
  # 26 errors in prose mode and 30 with --commit-msg). The invariant every pass
  # serves: only a tell
  # that is almost always right in this register may exit 1. A rule that fires
  # on the literal technical sense of a word in already-accepted text is off;
  # a real tell that is merely too common in the house vocabulary to fail on
  # drops to warning.
  #
  # Off, because each fires on text the corpus has already accepted: the
  # punctuation rules fight deliberate house style; FormalRegister
  # flags plain technical vocabulary ("implements"); NegatedObject and
  # NegatedSubject flag ordinary caveats ("expect no output", "nothing
  # checks"); the Bare* rules flag "holds", "names" and "reaches" in their
  # literal senses. The experimental passive rules join them for a different
  # reason — they fire in 37 of 40 accepted PR bodies, and passive voice is
  # opt-in here through --ste (STE.PassiveVoice).
  #
  # Warning, not error, because they are real tells over words the corpus also
  # uses literally: "shape", "gates on", "survives a restart", and the
  # anthropomorphism rules v1.34 widened and added ("the warning cannot
  # decide", "the healthy poll"). AnthropomorphicJustification stays at error;
  # it has no literal reading here. ConsequenceClause joins them for the
  # construction rather than a word: the ", so the check goes red" inference
  # appears in 3 of 40 accepted PR bodies.
  #
  # Advisory, kept visible but never fatal: VerbTricolon's regex over-matches
  # across line breaks, CataphoricForecasting flags ordinary forward
  # reference, and NegatedPair hit twice in 100 documents and is a sibling of
  # the Negated* rules that are off outright.
  sharedOverrides = ''
    ai-tells.EmDashUsage = NO
    ai-tells.SemicolonUsage = NO
    ai-tells.DoubleHyphen = NO
    ai-tells.FormalRegister = NO
    ai-tells.NegatedObject = NO
    ai-tells.VerbTricolon = suggestion
    ai-tells.CataphoricForecasting = suggestion
    ai-tells.BareHolds = NO
    ai-tells.BareNames = NO
    ai-tells.BareReaches = NO
    ai-tells.NegatedSubject = NO
    ai-tells.NegatedPair = suggestion
    ai-tells.FigurativeShape = warning
    ai-tells.MortalityMetaphors = warning
    ai-tells.MotionMetaphors = warning
    ai-tells.EnforcementMetaphors = warning
    ai-tells.AnthropomorphicCognition = warning
    ai-tells.AnthropomorphicAdjectives = warning
    ai-tells.ConsequenceClause = warning
    ai-tells-experimental.PassiveVoice = NO
    ai-tells-experimental.PassiveVoiceAdverb = NO
    ai-tells-experimental.PassiveDensity = NO
  '';

  # vale 3.14.2 treats an override naming a rule that does not exist as a
  # silent no-op, so a misspelled key above would disable nothing and say
  # nothing. Every `Style.Rule = level` line must resolve to a rule file.
  checkedIni =
    name: text:
    runCommand name
      {
        inherit text;
        passAsFile = [ "text" ];
      }
      ''
        cp "$textPath" "$out"
        for key in $(sed -nE 's/^[[:space:]]*([A-Za-z0-9-]+\.[A-Za-z0-9]+)[[:space:]]*=.*/\1/p' "$out"); do
          test -f "${styles}/''${key%%.*}/''${key#*.}.yml" || {
            echo "prose-gate: ${name} overrides unknown rule $key" >&2
            exit 1
          }
        done
      '';

  proseIni = checkedIni "prose-gate-prose.ini" ''
    StylesPath = ${styles}
    MinAlertLevel = suggestion

    [*]
    BasedOnStyles = ai-tells, ai-tells-experimental, Slop, Personal
    Slop.EmDash = NO
    ${sharedOverrides}
  '';

  commitIni = checkedIni "prose-gate-commit.ini" ''
    StylesPath = ${styles}
    MinAlertLevel = suggestion

    [formats]
    COMMIT_EDITMSG = md

    [*]
    BasedOnStyles = ai-tells, ai-tells-commits, ai-tells-experimental, Personal
    ai-tells-commits.CommitFigurativeVerbs = suggestion
    ${sharedOverrides}
  '';

  # --ste opt-in: ASD-STE100-inspired controlled-English rules from
  # vale-llm-slop (short sentences, one instruction per sentence, no passive,
  # no contractions). Deliberately not in the default set — upstream marks it
  # strict opt-in and it fights the house register; reach for it when a doc
  # wants maximum plainness.
  steIni = checkedIni "prose-gate-ste.ini" ''
    StylesPath = ${styles}
    MinAlertLevel = suggestion

    [*]
    BasedOnStyles = ai-tells, ai-tells-experimental, Slop, STE, Personal
    Slop.EmDash = NO
    # STE.Contractions rejects contractions at error level, so the
    # experimental rule that asks for more of them can only send a writer
    # into the error. Off in this mode only; it still runs by default.
    ai-tells-experimental.ContractionAvoidance = NO
    ${sharedOverrides}
  '';

  cli = writeShellApplication {
    name = "prose-gate";
    runtimeInputs = [ vale ];
    text = ''
      PROSE_INI=${proseIni}
      COMMIT_INI=${commitIni}
      STE_INI=${steIni}
    ''
    + builtins.readFile ./prose-gate.sh;
  };
in
# Ship the skill definition inside the package output so the home-manager
# registry and non-home-manager consumers both find it at a stable path.
symlinkJoin {
  name = "prose-gate";
  paths = [ cli ];
  skillSrc = ../skills/prose-gate;
  # ponytail's description claims every coding task, so a top-level install
  # would load it in every session; nested here, the skill reads it on demand.
  postBuild = ''
    mkdir -p $out/share/skills/prose-gate/references
    cp -r $skillSrc/. $out/share/skills/prose-gate/
    cp -r ${ponytail}/skills/ponytail $out/share/skills/prose-gate/references/ponytail
    cp -r ${ponytail}/skills/ponytail-review $out/share/skills/prose-gate/references/ponytail-review
  '';
  meta = {
    description = "Deterministic AI-tell lint for prose bound for external readers";
    mainProgram = "prose-gate";
  };
}
