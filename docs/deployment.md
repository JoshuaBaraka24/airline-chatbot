# Deployment guide

The system can run in two ways:

- **Locally**, as four processes on one machine (see the README).
- **On a Hugging Face Docker Space**, as one container that runs all four parts. This
  gives a public HTTPS link for demonstrations at no cost.

## How the Space container works

A Space runs one container with one public port, so `deploy/Dockerfile` puts the
whole system in a single image and `deploy/start.sh` starts it:

| Part | Port | Reachable from outside |
|---|---|---|
| PostgreSQL | 5432 | No (bound to 127.0.0.1) |
| Action server | 5055 | No (Spaces expose only the app port) |
| Rasa server | 5005 | No (bound to 127.0.0.1) |
| FastAPI gateway and portal | 7860 | Yes, over HTTPS |

On every start the database is rebuilt from `database/seed.sql`, so each restart
gives fresh demo data. If any of the servers stops, the container stops and the
Space restarts it.

Free Spaces have 2 CPU cores and 16 GB of memory, enough for the BERT model.
They sleep after about 48 hours without visitors; the first visit after that
takes a few minutes while the container starts.

## First deployment

1. **Create the Space.** Sign in at huggingface.co, choose *New Space*, pick the
   **Docker** SDK with the *Blank* template and the free *CPU basic* hardware.
   A public Space can be opened by anyone with the link; a private one only by
   signed-in members of your account.
2. **Add the secrets** under *Settings → Variables and secrets* (see the table below).
   At least `DEMO_ADMIN_PASSWORD` is required, or the container refuses to start.
3. **Create an access token** with *write* permission under
   *Settings → Access Tokens* on Hugging Face.
4. **Publish.** From the project root, with the trained model in `models/final.tar.gz`:

   ```powershell
   .\deploy\push_space.ps1 -Space your-hf-username/airline-assistant
   ```

   When Git asks, enter your Hugging Face username and the token as the password.
   The script publishes the last commit only, so commit your changes first.
5. **Watch the build** on the Space's *Logs* tab. The first build takes roughly
   15 to 25 minutes, mostly installing Rasa and TensorFlow.
6. **Open the app at its own address**, `https://<username>-<space-name>.hf.space`.
   Inside the Hugging Face page the app runs in a frame, and browsers do not keep
   the sign-in cookie there.

To update the Space later, commit and run step 4 again.

## Secrets and variables

| Name | Required | Value |
|---|---|---|
| `DEMO_ADMIN_PASSWORD` | Yes | Password for the staff account. Never use the default from `init_db.py` on a public site. |
| `DEMO_PASSWORD` | Recommended | Password for the sample passenger accounts. |
| `ALLOWED_ORIGINS` | Yes | `https://<username>-<space-name>.hf.space` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | For email | Email relay settings (see below). |
| `SMTP_STARTTLS` | No | `true` (default) for ports 587 and 2525. |
| `EMAIL_REDIRECT_TO` | Recommended | Sends every email to one inbox, so sample accounts are never mailed. |
| `SMTP_CHECK_PORTS` | No | Extra ports to test at start-up (default `587,2525`). |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | For Google sign-in | From Google Cloud Console. |
| `GOOGLE_REDIRECT_URI` | For Google sign-in | `https://<username>-<space-name>.hf.space/api/auth/google/callback`. Also add it to the OAuth client's authorised redirect URIs. |

The start script sets the database and Rasa addresses itself, and turns on secure
cookies, so these do not need secrets.

## Email on a Space

Hugging Face Spaces block some outgoing email ports, including Gmail's port 587.
The email code sends through any SMTP server, so the fix is a relay that listens
on port 2525, such as SMTP2GO or Brevo:

1. Create an account with the relay and verify the sender address you will send from.
2. Set `SMTP_HOST`, `SMTP_PORT=2525`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM`
   from the relay's SMTP settings.
3. Restart the Space and look for lines like these near the top of the logs:

   ```
   Email check: mail.example.com:587 BLOCKED or unreachable
   Email check: mail.example.com:2525 (configured) reachable
   ```

4. Make a booking in the chat and check the `EMAIL_REDIRECT_TO` inbox, including
   the spam folder: email from a Gmail address sent through a relay is often
   marked as spam.

If port 2525 is also blocked, the alternative is the relay's HTTPS API, which
needs a small change to `actions/notify.py`.

## Limitations of the Space deployment

- Data does not persist: bookings and accounts reset when the Space restarts or sleeps.
- One container on 2 CPU cores: replies slow down under concurrent use, as in the
  load test (Section 5.6.4 of the report).
- It is a demonstration, not a production deployment: no monitoring, backups or
  second Rasa instance.
