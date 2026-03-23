---
name: siplink
description: Place a phone call from the user's desk phone to a number. Use when the user asks to call someone, dial a number, or phone someone.
---

# Usage

The `call` shell function is the primary interface. It rings the user's desk phone first, then connects to the target number:

```bash
call <phone_number>
call 3055551234       # 10-digit numbers auto-prefixed with 1
call 13055551234      # full E.164 also works
```

# How it works

1. Calls the user's desk phone (17866000460) first — user answers
2. Transfers the call to the target number
3. Both parties are connected; siplink exits

# Environment

Credentials are fetched from Bitwarden (rbw) automatically by the `call` function.

If invoking `siplink` directly:
```bash
export VOIPMS_USER=$(rbw get "voip.ms subaccount sip" --field username) && \
export VOIPMS_PASS=$(rbw get "voip.ms subaccount sip") && \
export VOIPMS_SERVER="tampa1.voip.ms" && \
siplink <phone1> <phone2>
```

# Notes

- phone1 is called and answered first, then transferred to phone2
- Phone numbers must be dialable from VoIP.ms (US/Canada, 10 or 11 digits)
- Uses encrypted SIP (TLS) and G.722 HD voice (SRTP)
