# Delivery review

## Ready in this delivery

- The database can be migrated and seeded with the Guard IQ profile, logo, source priorities, and two-image defaults.
- News ingestion and screening are command-driven; screening runs in batches of up to 100.
- The supplied logo is composited by the application after white-image generation, so Gemini is no longer trusted to redraw brand identity.
- The image quality critic receives the real PNG as a multimodal image, rather than truncated base64 text.
- The client can replace the temporary handover password from Settings.
- A forgotten password can be reset locally with hidden Terminal input; no email reset service is exposed.
- A local backup command captures PostgreSQL and generated media before an update.
- Gemini and OpenAI/GPT each have one enforceable shared monthly limit, defaulting to $10 per provider.
- Backend and frontend startup scripts bind to `127.0.0.1` and the Mac launcher starts and stops both together.
- Real environment files, runtime media, databases, logs, dependencies, and browser sessions are ignored by Git.
- Production mode rejects placeholder JWT signing secrets.
- Production database TLS cannot disable certificate verification.
- Production dependency audits report zero known vulnerabilities for both backend and frontend lockfiles as reviewed on 18 August 2026.

## Security review

The intended deployment is local-only on one client Mac. Within that boundary, API keys stay in the backend `.env`, passwords are bcrypt-hashed in PostgreSQL, protected routes require JWT authentication, organisation data is scoped by the authenticated membership, and diagnostics redact configured secrets.

The application should not be exposed directly to the internet in its current form. Browser tokens are stored in local storage, refresh tokens are stateless, login has no dedicated brute-force rate limiter, and the local Vite preview server is not an internet-facing production server. These are acceptable only while both services remain bound to `127.0.0.1` on a trusted Mac. The candid technical boundary is recorded in `SECURITY.md` for the client’s review.

## Required before client handover

1. Run the full backend test suite and frontend TypeScript production build on the final code.
2. Run dependency vulnerability checks and review any reported production dependency issue.
3. Rehearse `INSTALLATION_GUIDE.md` once on the client’s Mac or another clean Mac account.
4. Confirm the client has their own OpenAI, Gemini, Azure Speech, and Azure Translator credentials and billing limits.
5. Rotate any provider key or password previously shared in chat, source control, screenshots, or email.
6. Give the client the project without `.env`, `.env.local`, database dumps, logs, generated media, virtual environments, `node_modules`, or developer-agent folders.
7. Make one encrypted backup after installation and confirm it can be restored.
8. Have the client change the temporary admin password in Settings during handover.

## Password handover

Preferred: the installation agent generates the temporary password on the client’s Mac and stores it in macOS Keychain, so no password is shared at all. If installation is performed remotely, send the temporary password through a one-time 1Password link or another end-to-end encrypted channel, separate from the project archive and login email. Never place it in a README, `.env.example`, commit, ordinary email, or chat transcript. The client must change it immediately in Settings.
