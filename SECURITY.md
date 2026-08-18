# Security and deployment boundary

## Supported deployment

This delivery is designed for one authorised user on a trusted Mac. The frontend and backend listen only on `127.0.0.1`, so other devices on the local network—and the public internet—cannot connect to them. The client accesses the app from the same Mac.

Do not change either service to `0.0.0.0`, forward ports 3000 or 8000, or expose the app through a tunnel. A network or internet deployment needs a separate review and, at minimum, HTTPS, a production web server, secure cookie-based sessions or equivalent hardened token handling, login rate limiting, monitoring, and managed backups.

## Controls in this delivery

- Passwords are bcrypt-hashed; plaintext passwords are never stored in PostgreSQL.
- Protected API routes require a signed access token and organisation membership.
- Provider credentials remain in the backend `.env`, which is excluded from Git.
- CORS allows only configured local frontend origins and does not allow credentialed cross-origin cookies.
- Remote PostgreSQL connections require verified TLS in production.
- Diagnostics redact configured secrets.
- Paid AI calls have durable per-provider monthly limits, set in **Settings**. Gemini shares one limit across all Gemini models, and OpenAI/GPT shares another. In-progress calls reserve budget so concurrent work cannot bypass a limit.
- Database and generated-media backups are created by a local command, never exposed as a browser download.

## Mac protections the client should enable

- FileVault full-disk encryption.
- A strong macOS account password and automatic screen locking.
- `chmod 600` permissions on backend `.env` and frontend `.env.local`.
- Provider-side spend alerts or hard project limits. In-app costs are estimates; the provider billing pages are authoritative.
- Encrypted, off-device storage for backup ZIPs.

## Known limitations

- Browser access and refresh tokens are stored in local storage. Malicious JavaScript running in the app origin could read them.
- Refresh tokens are signed and time-limited but are not backed by a server-side revocation list.
- Login has no dedicated brute-force rate limiter.
- API keys are stored in the local `.env` rather than macOS Keychain. The file is restricted to the owning macOS account; Keychain integration would be a stronger optional hardening step but would add launcher and recovery complexity.
- Local HTTP is used instead of HTTPS because traffic never leaves the Mac.
- Azure Speech and Translator usage is not priced by the AI provider budgets. Configure Azure Cost Management alerts separately.

## Secret storage on macOS

For this single-user local installation, the supported baseline is a backend `.env` owned by the client with mode `600`, together with FileVault and a strong macOS login. Do not put credentials directly in a `.sh` file: shell files are easy to copy, inspect, log, or commit accidentally.

macOS Keychain is the stronger native option for API keys at rest. If it is adopted later, a launcher script may retrieve keys from Keychain and pass them to the backend process as environment variables, but the script itself must contain no secret values. The temporary installation password already uses Keychain and is deleted after the client changes it; the client’s permanent application password should be remembered or stored in their password manager, not in the project.

These limitations are reasonable only inside the supported local-only boundary above. They are not claims of internet-production hardening.

## Lost-password recovery

There is intentionally no email-based “forgot password” link in this single-user local delivery. Someone with authorised Terminal access to the Mac and database can reset the administrator password without seeing the old password:

```bash
cd ai-content-platform-backend
.venv/bin/python scripts/reset_admin_password.py
```

The command reads the replacement password with hidden input. Stop the app first, then restart it after the command succeeds.

## Reporting a security issue

Do not include credentials, database dumps, client content, or generated media in an ordinary email or issue. Send a redacted diagnostics export first and arrange an encrypted transfer separately if sensitive evidence is required.
