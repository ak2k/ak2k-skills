---
name: siplink
description: Bridge two phone calls via VoIP.ms SIP. Use when the user asks to make a call, connect two numbers, or bridge a call.
---

# Usage

```bash
# Bridge two calls: siplink calls phone1, then transfers to phone2
siplink <phone1> <phone2>

# 10-digit US numbers get auto-prefixed with 1
siplink 3055551234 7865559876

# Full E.164 format also works
siplink 13055551234 17865559876
```

# Environment

Credentials are fetched from Bitwarden (rbw) at call time. Use the `call` shell function which handles this automatically:

```bash
# The call function sets up credentials and calls siplink
call <phone_number>   # bridges 17866000460 (home) → <phone_number>
```

If invoking siplink directly, set these env vars:
```bash
export VOIPMS_USER=$(rbw get "voip.ms subaccount sip" --field username) && \
export VOIPMS_PASS=$(rbw get "voip.ms subaccount sip") && \
export VOIPMS_SERVER="tampa1.voip.ms" && \
siplink <phone1> <phone2>
```

# How it works

1. Registers with VoIP.ms over SIP/TLS (port 5061)
2. Sends INVITE to phone1 (G.722 HD voice, SRTP)
3. Once phone1 answers, sends REFER to transfer to phone2
4. Exits — the call continues server-side between the two parties

# Notes

- Phone numbers must be dialable from VoIP.ms (US/Canada numbers work with 10 or 11 digits)
- The tool exits after initiating the transfer; it does not stay running
- Uses encrypted SIP (TLS) and SRTP for secure signaling and media negotiation
