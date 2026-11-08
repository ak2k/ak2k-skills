---
name: prose-gate
description: Detect and fix AI-sounding prose before it reaches external readers — PR bodies, commit messages, READMEs, issue and review comments. Runs the deterministic vale gate (prose-gate CLI), then drives the humanizer skill for rewrites with an optional length budget. The Ponytail cut (state the why, cut what the diff shows) is the default for commit messages, code comments, PR bodies and review or issue replies another person reviews. Use before pushing prose to any repo other people read, or when asked to de-AI, humanize, tighten, or ponytail text.
---

# prose-gate: de-AI external-bound prose

Two layers: a deterministic lint (the `prose-gate` CLI) that catches the
mechanical tells every time, and a judgment rewrite (the `humanizer` skill)
for what regex cannot see. Detect first, then fix, then re-run the gate.

## 1. Detect

```bash
prose-gate draft.md README.md        # files
prose-gate < draft.md                # stdin (parsed as markdown)
prose-gate --commit-msg              # .git/COMMIT_EDITMSG
git log -1 --format=%B | prose-gate --commit-msg /dev/stdin
gh pr view N --json body --jq .body | prose-gate   # a PR body
prose-gate --output=JSON draft.md    # machine-readable
prose-gate --ste spec.md             # + ASD-STE100 controlled English (strict, opt-in)
```

Exit 1 = error-level findings. Two kinds land there: the personal hard bans —
private-review vocabulary ("load-bearing", "supersedes", "by construction",
…) and internal tooling names (subagent, reviewer persona, ce-* skill
names) — which are non-negotiable for external text, and the style packages'
own high-confidence tells (ShipOveruse, FigurativeCarries,
ContrastiveFormulas, …), which are almost always right but deserve a read
rather than blind obedience. Warnings and suggestions are judgment calls:
apply the ones that are right, ignore the ones that fight the author's
deliberate voice.

Density findings (`ai-tells-experimental.AverageSentenceLength`,
`SentenceLengthVariance`, `ParagraphLengthVariance`) are warnings, never
errors. The usual cause here is semicolon chaining, which the gate
deliberately does not flag. Vale ends a sentence at `.`, `!` or `?` only, so
wrapping the line after the semicolon changes nothing; acting on the warning
means replacing the semicolon with a period, which makes two sentences. A
deliberate semicolon pair is a warning step 3 leaves standing.

## 2. Fix — humanizer, a length budget, the Ponytail cut

Load the `humanizer` skill (`~/.claude/skills/humanizer`) and apply its
rewrite process, with these additions to its defaults:

- **Length budget.** If the user gives a target ("~150 words", "half this"),
  hit it. When none is given and the draft is flabby, cut 20–30% without
  dropping a claim; text about a code change takes the Ponytail cut below
  instead. PR bodies for external repos calibrate to the
  maintainer's accepted size — read 2–3 recently merged PRs first.
- **Public text is flag-propose-wait.** For anything already drafted that
  will publish under the user's name (PR body, review comment, email): quote
  the problem, propose the rewrite, wait for the call. Never silently
  paraphrase — exact wording of public text matters.
- Keep every claim; never invent facts; match the user's terse register.
- **Mannered prose is a rewrite target the lint cannot see.** Fresh metaphor
  is not enumerable by regex, and the gate catches few metaphors, so apply
  this definition as a criterion on every sentence ([Fable 5.1 prompting
  guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1#writing-density)):
  "Mannered prose substitutes metaphor and flourish for direct statement.
  Instead of 'a parameter worth varying,' the mannered writer produces 'a dial
  worth turning.' Instead of 'this point still matters,' they write 'this
  point earns its keep.' The phrases exist to display the writer, not to
  convey the idea, and readers can tell. That is why mannered prose irritates:
  it makes the reader work harder so the writer can perform. It is also
  imprecise. Metaphors drag in connotations the writer did not choose and
  cannot control. The fix is to say what you mean. When a literal phrase is
  available, use it." When you brief another writer to draft public text, put
  the same paragraph in the brief; the short form "Please remove all mannered
  prose." also works.
- **`--ste` findings route to the `asd-ste100` skill**
  (`~/.claude/skills/asd-ste100`), not humanizer: STE-flavored mode for
  READMEs and PR bodies, Strict for tool descriptions, error strings, and
  agent-facing instructions. It preserves hedges — "may have failed" never
  becomes "failed".

### The Ponytail cut: the default for text about a code change

It applies without being asked to commit messages, code comments, PR bodies,
and review or issue replies that another person reviews. It does not apply to
prose with no diff (email, docs prose), or to the user's own configuration-repo
commits and internal text; the line is whether anyone other than the user will
read it.

- **State the why; never restate what the diff shows.** The one prose rule in
  the `ponytail` skill (`~/.claude/skills/ponytail`) is
  "Comment only the why the code cannot show, in one line." The rest of
  this pass is ours; Ponytail itself is a code-minimalism skill.
- **Match the code.** Follow the changed file's comment density and style, and
  keep a commit message within the lengths of that path's own `git log`.
- Drop a commit body when the diff, or doc text in the same series, already
  says why. A reply is one line where one line answers, and one or two words
  where those answer.
- **The bar for a cut.** For each sentence and clause, ask whether the reader
  loses a fact they need if it goes. If not, cut it. A sentence that restates
  what the reader already has, or argues for what the diff already shows,
  goes. Keep every fact a reviewer asked for or needs to verify the change.
  The pass cuts; it does not reword for style alone.
- **Acceptance question, naming the actual reviewers:** would <reviewer> read
  it as LLM output? Take the names, and what they said about earlier drafts,
  from the PR's threads.
- **Invariants.** Drop no claim, make no claim untrue, and add none. Leave
  quotations, trailers, any required disclosure sentence and the project's templates alone. US
  spelling, and literal sentences per the mannered-prose bullet above.
- **Who runs it.** Public text gets the pass from a separate opus session,
  briefed with every reviewer comment on the PR, the surrounding code and the
  acceptance question. The pass covers the code and its comments too; for the
  code, point that session at the installed `ponytail` skill
  (`~/.claude/skills/ponytail`), and use `ponytail-review`
  (`~/.claude/skills/ponytail-review`) to review the diff. Text written or
  changed after a pass gets the pass again, PR bodies included. Then step 3.

## 3. Re-run the gate

Rewrites can introduce new tells — fixes themselves need the pass. Run
`prose-gate` again; done when it exits 0 and the remaining warnings are
deliberate choices.

## Notes

- Config and styles are nix-pinned (`prose-gate/` in ak2k-skills); no
  `vale sync`, no network at runtime.
- Tuned: the punctuation-register rules, FormalRegister, NegatedObject,
  NegatedSubject and the `Bare*` rules are OFF — each fires on text the tuning
  corpus has already accepted — as are the experimental passive rules, since passive
  voice stays `--ste`-only. FigurativeShape, the mortality, motion and
  enforcement metaphor rules, AnthropomorphicCognition and
  AnthropomorphicAdjectives warn rather than fail, being house vocabulary, and
  so does ConsequenceClause, a house construction;
  VerbTricolon, CataphoricForecasting and NegatedPair are advisory. Under
  `--ste`, ContractionAvoidance is off too, since STE bans contractions
  outright. Rationale in `prose-gate/default.nix`.
- Commit-message rules (`ai-tells-commits`) only run in `--commit-msg` mode.
- This skill file itself names the banned tokens as examples; the gate is for
  external-bound text, not internal notes.
