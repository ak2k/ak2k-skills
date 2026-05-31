---
name: gemtts
description: Generate speech audio from text with Google's Gemini TTS. Use when the user asks to synthesize speech, create a voiceover or voicemail greeting, or narrate text.
---

# gemtts — Gemini text-to-speech CLI

`gemtts` turns text into expressive speech via the Gemini TTS API. Stdout is
always data — a human table in a TTY, a JSON envelope (`{data, status,
version}`) when piped or with `--json`. Audio is written to the `-o` path, never
to stdout; progress and errors go to stderr.

Run `gemtts agent-info` first for the full machine-readable contract (commands,
flags, exit codes, examples).

## Auth

Reads the API key from `GEMINI_API_KEY` (or `GOOGLE_API_KEY` /
`GOOGLE_AI_API_KEY`), else `~/.config/gemtts/config.toml`. The key is in
Bitwarden (rbw) — export it, then invoke:

```bash
export GEMINI_API_KEY=$(rbw get "aistudio.google.com API Key")
gemtts doctor --live   # verify creds + a real round-trip before a batch
```

This keeps the key in the env only (never written to disk), matching the
rbw pattern the other skills use. `gemtts auth import-env` / `gemtts auth set`
can persist it to `~/.config/gemtts/config.toml` if you prefer.

## Generate speech

```bash
# Simplest: default voice + default model.
gemtts speak "Say warmly: your appointment is confirmed." -o out.wav

# Choose a voice; add director notes for delivery (Gemini is prompt-steered).
gemtts speak "Thank you for calling." --voice Sulafat \
  --style "warm, welcoming, professional" --pace "slightly brisk, natural" \
  -o greeting.wav --play

# Use the newer Gemini 3.1 Flash TTS model explicitly:
gemtts speak "..." --voice Sulafat --model gemini-3.1-flash-tts-preview -o out.wav

# Read from a file; emit mp3 (compressed formats need ffmpeg on PATH):
gemtts speak script.txt --text-file --voice Achernar -o narration.mp3 --format mp3
```

Key `speak` flags: `--voice`, `--model`, `--style`, `--pace`, `--accent`,
`--language`, `--tag "[warmly]"`, `--format {auto,wav,pcm,mp3,m4a,flac}`,
`--text-file`, `--play`, `--raw` (use the text verbatim as the prompt).

## Pick a voice / shape a prompt

```bash
gemtts voices list                       # all prebuilt voices + characters
gemtts voices recommend "warm clinic receptionist"
gemtts tags list                         # inline delivery tags like [whispers]
gemtts script "Welcome back" --style "calm expert narrator"  # build prompt only
gemtts lint script.txt                   # check a prompt before spending tokens
```

## Notes

- Voices are timbres, not languages — Gemini auto-detects transcript language;
  use `--language`/`--accent` for non-English, keep `[tags]` in English.
- Native output is WAV/PCM (24 kHz, 16-bit, mono) — ideal for downstream tools
  (e.g. a Google Voice voicemail upload).
- Prefer short takes; regenerate to vary delivery (Gemini TTS is
  non-deterministic). `gemtts usage summary` shows token/cost estimates.
