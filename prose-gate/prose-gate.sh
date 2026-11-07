# shellcheck shell=bash
# prose-gate — lint external-bound prose for AI tells. See default.nix beside
# this file for the style packages and tuning rationale. Wrapped by
# writeShellApplication: PROSE_INI / COMMIT_INI are assigned above this file's
# contents, and vale is on PATH via runtimeInputs.

: "${PROSE_INI:?assigned by the writeShellApplication wrapper (default.nix)}"
: "${COMMIT_INI:?assigned by the writeShellApplication wrapper (default.nix)}"
: "${STE_INI:?assigned by the writeShellApplication wrapper (default.nix)}"

usage() {
  cat <<'EOF'
prose-gate — deterministic AI-tell lint for prose bound for external readers

usage:
  prose-gate FILE...                 lint files
  prose-gate < draft.md              lint stdin (parsed as markdown)
  prose-gate --commit-msg [FILE]     lint a commit message (default: .git/COMMIT_EDITMSG)
  prose-gate --ste FILE...           add ASD-STE100 controlled-English rules (strict, opt-in)
  prose-gate --output=JSON FILE      unrecognized flags pass through to vale

exit: 0 = clean or advisory only; 1 = error-level findings — the packages'
high-confidence AI tells plus the personal hard bans (private-review
vocabulary, internal tooling names).
EOF
}

mode=prose
flags=()
files=()
for a in "$@"; do
  case "$a" in
  -h | --help)
    usage
    exit 0
    ;;
  -c | --commit-msg) mode=commit ;;
  --ste) mode=ste ;;
  -*) flags+=("$a") ;;
  *) files+=("$a") ;;
  esac
done

# Vale always prepends the platform styles dir (~/Library/Application
# Support/vale/styles on darwin) to the config's StylesPath, so a style
# synced there by any `vale sync` shadows the nix-pinned copy of the same
# name. Point HOME at an empty directory so the pinned styles are the only
# styles vale can see.
HOME="$(mktemp -d)"
export HOME

config="$PROSE_INI"
case "$mode" in
commit)
  config="$COMMIT_INI"
  if [ ${#files[@]} -eq 0 ] && [ -f .git/COMMIT_EDITMSG ]; then
    files=(.git/COMMIT_EDITMSG)
  fi
  ;;
ste) config="$STE_INI" ;;
esac

if [ ${#files[@]} -eq 0 ]; then
  # stdin: vale needs --ext to pick a parser
  exec vale --config="$config" --ext=.md "${flags[@]}"
fi
exec vale --config="$config" "${flags[@]}" "${files[@]}"
