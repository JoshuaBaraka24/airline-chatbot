# Deployment guide

The system can run in two ways:

- **Locally**, as four processes on one machine (see the README).
- **On a server**, as Docker containers behind HTTPS. This guide uses an Azure
  virtual machine paid for by the Azure for Students credit, but the same files
  work on any Ubuntu server with a public IP address.

## How the server deployment works

`deploy/compose.yaml` runs two containers:

| Container | What runs in it | Reachable from the internet |
|---|---|---|
| `app` | PostgreSQL, the action server, the Rasa server and the FastAPI gateway with the portal (`deploy/Dockerfile`, started by `deploy/start.sh`) | No, only through Caddy |
| `caddy` | Caddy web server: gets and renews a free HTTPS certificate and forwards requests to `app` | Ports 80 and 443 |

The database is stored in a Docker volume, so bookings, accounts and conversation
transcripts survive restarts and redeployments. The demo data is loaded when the database is first
created. If any server inside `app` stops, the container stops and Docker restarts it.

## Cost

Azure for Students gives $100 of credit for 12 months, without a credit card.
A B2als_v2 virtual machine (2 vCPUs, 4 GB of memory) in Central India costs about
$18 a month, plus a few dollars for the disk and public IP address.

- **Stop the VM** (*Stop* in the portal, which deallocates it) when you are not
  demonstrating. Compute is then not charged; the disk and IP address still are.
- Set **auto-shutdown** on the VM so it stops each night if you forget.
- When the credit runs out, the subscription is disabled and the site goes offline.

## 1. Create the virtual machine (once)

1. Activate Azure for Students at azure.microsoft.com/free/students with your
   university email address.
2. Create an SSH key on your PC (press Enter twice to skip the passphrase, or set one):

   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\azure_airline
   ```

3. In the Azure portal choose **Create a resource → Virtual machine**:
   - **Image:** Ubuntu Server 24.04 LTS (x64)
   - **Region:** one your subscription allows (the portal lists the others as *Ineligible*)
   - **Size:** Standard_B2als_v2. Sizes with a "p", such as B2pls_v2, are Arm64 and will not work.
   - **Authentication:** SSH public key, username `azureuser`, *Use existing public key*,
     and paste the contents of `$HOME\.ssh\azure_airline.pub`
   - **Inbound ports:** SSH (22), HTTP (80) and HTTPS (443)
   - **Disk:** Standard SSD, 30 GB is enough
4. When it is created, open the VM's **public IP address** resource, choose
   **Configuration**, set a **DNS name label** such as `airline-demo` and save.
   The VM is now reachable as `airline-demo.<region>.cloudapp.azure.com`.
5. Recommended: under the VM's **Networking**, limit the SSH rule's source to your
   own IP address, and under **Auto-shutdown** set a nightly stop time.

## 2. Fill in the server settings (once)

Copy `deploy\env.production.example` to `.env.production` in the project root and
fill it in. Git ignores this file, so the secrets are never committed.

| Setting | Required | Value |
|---|---|---|
| `SITE_ADDRESS` | Yes | The VM's DNS name, for example `airline-chatbot.centralindia.cloudapp.azure.com` |
| `ALLOWED_ORIGINS` | Yes | `https://` followed by the same name |
| `DEMO_ADMIN_PASSWORD` | Yes | Staff account password. The system refuses to start without it, because the default is in the public code. |
| `DEMO_PASSWORD` | Yes | Password for the sample passenger accounts, required for the same reason. Avoid `$`, `#`, quotes and spaces in both, because Compose gives them special meaning in this file. |
| `RESET_DEMO_DATA` | No | `true` reloads the demo data on every start |
| `CHAT_PER_...` | No | Chat message limits: 20 a minute per conversation, 60 a minute and 600 an hour per network address. Raise the last two if a large audience shares one Wi-Fi network; 0 switches a limit off. |
| `SMTP_*`, `EMAIL_REDIRECT_TO` | For email | The same Gmail settings as your local `.env`. Azure blocks only port 25, so Gmail on port 587 works. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | For Google sign-in | The same values as your local `.env` |
| `GOOGLE_REDIRECT_URI` | For Google sign-in | `https://<DNS name>/api/auth/google/callback`. Add it to the OAuth client's authorised redirect URIs in Google Cloud Console. |

The database and Rasa addresses are set inside the container, so they are not needed here.

## 3. Publish

From the project root, with your changes committed (the newest model in `models` is used):

```powershell
.\deploy\push_server.ps1 -Server azureuser@airline-demo.<region>.cloudapp.azure.com
```

Some Wi-Fi networks block SSH (port 22). If the connection times out, publish from
another network, such as a phone hotspot.

If your key has a passphrase, the script asks for it twice: before the upload and
after it. Enter it within two minutes each time, or the server closes the connection.

The script uploads the last commit, the model and `.env.production`, installs
Docker and a swap file on the first run, then builds and starts the containers.
The first build takes 15 to 25 minutes; later ones reuse the installed packages.

Follow the start-up with:

```powershell
ssh -i $HOME\.ssh\azure_airline azureuser@<DNS name> sudo docker compose -f airline-assistant/deploy/compose.yaml logs -f app
```

Near the top, the email check shows whether the email server can be reached:

```
Email check: smtp.gmail.com:587 (configured) reachable
```

The site is ready when Uvicorn reports that it is running and `https://<DNS name>/api/health`
shows `"status": "ok"`. The language model takes a minute or two to load after the
container starts.

To update the server later, commit your changes and run the same command again.
`-DryRun` prepares the upload without sending it.

## Everyday tasks

Run these over SSH (`ssh -i $HOME\.ssh\azure_airline azureuser@<DNS name>`), in `~/airline-assistant`:

| Task | Command |
|---|---|
| Reset the demo data | `sudo docker compose -f deploy/compose.yaml exec -T -e DB_HOST=127.0.0.1 -e DB_PORT=5432 -e DB_NAME=airline_db -e DB_USER=user -e DB_PASSWORD= app python database/init_db.py` |
| Restart the system | `sudo docker compose -f deploy/compose.yaml restart` |
| See the logs | `sudo docker compose -f deploy/compose.yaml logs --tail 100 app` |
| Stop the system | `sudo docker compose -f deploy/compose.yaml down` (the data volume is kept) |

The reset command passes the database settings itself, because `start.sh` sets them only for
the servers it starts and the `.env` file does not contain them. The reset replaces every
booking, account, login session and dashboard conversation with the sample data, and the demo
passwords become `DEMO_PASSWORD` and `DEMO_ADMIN_PASSWORD` from `.env` again.

The sample flights are dated relative to the day the data was loaded, so reset the demo data
shortly before a demonstration. Booking BK003 departs at noon on the day after a reset, so its
online check-in can be shown only until 11:00 that day.

## Limitations of this deployment

- One VM with 2 burstable CPU cores: after a few minutes of heavy use Azure
  throttles the CPU, and replies slow down further than in the load test
  (Section 5.6.4 of the report).
- No monitoring, backups or second Rasa instance, so it suits demonstrations,
  not production use.
- Email is sent from a personal Gmail account, and Google sign-in stays in
  Google's testing mode, which allows only listed test users.
