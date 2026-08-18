# Mac installation guide

This guide is written so the project folder and this file can be given to Claude Code or Codex on the client’s Mac. The agent should complete the installation, stopping only when the client must enter private API keys.

## Instructions for the installing agent

- Work only inside the supplied project folder unless installing Homebrew packages.
- Do not reset or delete an existing database. If this appears to be an existing installation, stop and back up PostgreSQL and `ai-content-platform-backend/data/media` before changing anything.
- Never print, log, commit, or send API keys, database passwords, JWT secrets, or the admin password in chat.
- Bind both services to `127.0.0.1`. This installation is local to one Mac and is not designed to be exposed directly to the internet.
- Do not commit `.env`, `.env.local`, database dumps, media, logs, or browser credentials.

## 1. Confirm the project and Mac

Open Terminal in the project root—the folder containing this guide, `ai-content-platform-backend`, and `ai-content-platform-frontend`. Confirm the working folder, supported macOS version, and Mac architecture:

```bash
pwd
sw_vers
uname -m
```

Allow at least 10 GB of free disk space. Use macOS 13 or later where possible.

## 2. Install system prerequisites

If Homebrew is not installed, install it from [brew.sh](https://brew.sh/). Then run:

```bash
brew update
brew install python@3.12 postgresql@16 node@22
brew services start postgresql@16
export PATH="$(brew --prefix postgresql@16)/bin:$(brew --prefix python@3.12)/bin:$(brew --prefix node@22)/bin:$PATH"
python3.12 --version
node --version
psql --version
```

Add the same `export PATH=...` line to `~/.zprofile` if Homebrew says a package is keg-only.

## 3. Create the local database

Generate a database password without displaying it, then create a dedicated local role and database. A generated hexadecimal password is safe to insert into the connection URL without URL encoding.

```bash
DB_PASSWORD="$(python3.12 -c 'import secrets; print(secrets.token_hex(24))')"
if ! psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='content_app'" | grep -q 1; then
  psql postgres -c "CREATE ROLE content_app LOGIN PASSWORD '$DB_PASSWORD'"
else
  psql postgres -c "ALTER ROLE content_app WITH PASSWORD '$DB_PASSWORD'"
fi
if ! psql postgres -tAc "SELECT 1 FROM pg_database WHERE datname='ai_content_platform'" | grep -q 1; then
  createdb --owner=content_app ai_content_platform
fi
```

Keep `DB_PASSWORD` available in this Terminal until the backend `.env` is configured. Do not echo it.

## 4. Install application dependencies

From the project root:

```bash
cd ai-content-platform-backend
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cd ../ai-content-platform-frontend
npm ci
cd ..
```

## 5. Configure private environment files

Create the local files and restrict their permissions:

```bash
cp ai-content-platform-backend/.env.example ai-content-platform-backend/.env
cp ai-content-platform-frontend/.env.example ai-content-platform-frontend/.env.local
chmod 600 ai-content-platform-backend/.env ai-content-platform-frontend/.env.local
```

Generate two different JWT secrets and a temporary admin password. Do not display them:

```bash
JWT_ACCESS_SECRET="$(python3.12 -c 'import secrets; print(secrets.token_hex(32))')"
JWT_REFRESH_SECRET="$(python3.12 -c 'import secrets; print(secrets.token_hex(32))')"
ADMIN_PASSWORD="$(python3.12 -c 'import secrets; print(secrets.token_urlsafe(18))')"
security add-generic-password -U -a "$USER" -s "Guard IQ Content Platform Admin" -w "$ADMIN_PASSWORD"
```

Edit `ai-content-platform-backend/.env` without showing its contents in chat or terminal output. Replace:

- `CHANGE-DATABASE-PASSWORD` with `DB_PASSWORD`.
- Both JWT placeholders with `JWT_ACCESS_SECRET` and `JWT_REFRESH_SECRET` respectively.
- `SEED_ADMIN_PASSWORD` with `ADMIN_PASSWORD`.
- `GEMINI_API_KEY` and `OPENAI_API_KEY` with the client’s own keys.
- Azure Speech and Translator values with the client’s own Azure keys and regions so voice capture and translation work.

The client should enter provider keys directly on their Mac when the agent pauses. The frontend file should remain:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Build the frontend only after `.env.local` is in place, because Vite embeds this value at build time:

```bash
cd ai-content-platform-frontend
npm run build
cd ..
```

## 6. Prepare the database

```bash
cd ai-content-platform-backend
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_database.py
cd ..
```

After a successful seed, set `SEED_ADMIN_PASSWORD=` to blank in the backend `.env`; it is not needed for normal operation. Clear the temporary shell variables:

```bash
unset DB_PASSWORD JWT_ACCESS_SECRET JWT_REFRESH_SECRET ADMIN_PASSWORD
```

## 7. Start and verify the app

```bash
chmod +x start_mac.sh ai-content-platform-backend/scripts/*.sh ai-content-platform-frontend/scripts/*.sh
./start_mac.sh
```

The browser should open at `http://127.0.0.1:3000`. Keep the Terminal window open while using the app; press Control-C once to stop both services.

The login email is `admin@guardiq.com`. Retrieve the temporary password from macOS Keychain without showing it to the installing agent:

```bash
security find-generic-password -a "$USER" -s "Guard IQ Content Platform Admin" -w
```

Immediately open **Settings → Change password**, choose a new unique password, and sign in again. Then delete the temporary Keychain entry:

```bash
security delete-generic-password -a "$USER" -s "Guard IQ Content Platform Admin"
```

## 8. Acceptance checks

The installing agent should verify all of the following without making paid AI calls unless the client agrees:

1. `curl --fail http://127.0.0.1:8000/api/v1/health` returns a healthy response.
2. The login page loads and the client can sign in with the new password.
3. Sources shows the seeded source list, including the priority sources.
4. **Run sources** creates articles and **Screen next 100** runs only on command.
5. Draft generation creates both configured image styles when automatic images are enabled.
6. The white image contains the exact supplied Guard IQ logo added by the app, not a redrawn approximation.
7. Voice capture and translation work if Azure credentials were supplied.
8. Stop the app with Control-C and start it again with `./start_mac.sh`; existing data remains present.

## Daily use

From the project root, run:

```bash
./start_mac.sh
```

The app runs only on this Mac at `http://127.0.0.1:3000`. It does not need Redis or a separate background worker. PostgreSQL starts automatically through Homebrew.

## If the password is forgotten

There is no email reset flow because this is a local single-user installation. Stop the app, then run:

```bash
cd ai-content-platform-backend
.venv/bin/python scripts/reset_admin_password.py
cd ..
./start_mac.sh
```

The new password is entered twice with hidden Terminal input. The old password is not required and is never displayed.

## Back up before every update

Code updates and Alembic migrations are designed to preserve PostgreSQL data. Generated media also lives outside Git. Nevertheless, stop the app and create a backup before pulling or replacing code:

```bash
cd ai-content-platform-backend
.venv/bin/python scripts/backup_local.py
cd ..
```

This creates a timestamped ZIP under `ai-content-platform-backend/backups/` containing a PostgreSQL custom-format dump, generated media, and a non-secret manifest. The folder is ignored by Git. Copy the ZIP to encrypted storage away from the project folder; a backup left only beside the app will be lost if the Mac or folder is lost.

To update safely:

```bash
cd ai-content-platform-backend
.venv/bin/python scripts/backup_local.py
cd ..
git pull --ff-only
cd ai-content-platform-backend
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
cd ../ai-content-platform-frontend
npm ci
npm run build
cd ..
./start_mac.sh
```

Never run a database reset or development cleanup script during an update. If restoration is required, stop the app and ask the delivery team or a PostgreSQL administrator to verify the ZIP and run `pg_restore`; restoration replaces current data and should not be improvised.

## Monthly AI budgets

Open **Settings → Monthly AI provider budgets** after installation. Gemini has one shared **$10 USD per UTC month** limit across all Gemini models. OpenAI/GPT has a separate shared **$10 USD per UTC month** limit across all OpenAI models. In-progress calls reserve their estimated cost, and further calls are blocked when the provider’s remaining amount is insufficient. Image generation, retries, and text calls all count against the provider that performed them.

The totals are application estimates, not invoices. Configure billing alerts in [Google AI Studio](https://aistudio.google.com/welcome), the [OpenAI Platform](https://platform.openai.com/login), and Azure Cost Management as a second layer. Azure Speech and Translator are not token models and require separate Azure alerts.

## Security boundary

This setup is appropriate for local use on the client’s Mac. Binding to `127.0.0.1` means only software on that same Mac can connect; devices on the Wi-Fi/LAN and the public internet cannot reach the services. Do not forward ports 3000 or 8000, bind either service to `0.0.0.0`, or expose them through a public tunnel. Internet hosting requires HTTPS, secure cookies or another hardened token strategy, login rate limiting, managed backups, monitoring, and a proper production web server. See [SECURITY.md](SECURITY.md) for the complete review and known limitations.
