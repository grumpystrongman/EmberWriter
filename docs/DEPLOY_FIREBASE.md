# Firebase Hosting for EmberWriter

EmberWriter can use the same Firebase Hosting pattern as Family Canasta for its React/Vite UI, but its backend needs different treatment because EmberWriter is intentionally local-first.

## Recommended deployment today: hosted UI, local data

The safest first deployment is:

```text
Firebase Hosting (HTTPS)
        |
        | browser requests
        v
EmberWriter UI
        |
        | http://127.0.0.1:8000/api
        v
Local FastAPI service
        |
        +-- data/projects/*
        +-- project .ember/story.db files
        +-- local Ollama / configured model service
```

This gives EmberWriter a stable Firebase URL while manuscripts, project files, revision databases, and local model access stay on the author's computer.

Modern browsers treat loopback resources such as `127.0.0.1` and `localhost` specially. A browser that implements Local Network Access may prompt the user to allow the Firebase site to reach the local/loopback service. Allow that permission for the EmberWriter Firebase origin when prompted.

References:

- Firebase Hosting: https://firebase.google.com/docs/hosting
- MDN Local network access: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Local_network_access
- MDN Secure contexts: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts

## One-time Firebase setup

Install the frontend dependencies first:

```powershell
cd frontend
npm install
```

Sign in with the Firebase CLI:

```powershell
npm run firebase:login
```

Create a dedicated Firebase project for EmberWriter in Firebase, or create one with the Firebase CLI. Do not reuse the Family Canasta project. Then bind this repository to that project:

```powershell
npm run firebase:use
```

`firebase use --add` writes the selected project into a local `.firebaserc` file. Commit `.firebaserc` after the EmberWriter Firebase project ID is final if the repository should always deploy to that project.

## Deploy the UI

From `frontend/`:

```powershell
npm run firebase:deploy
```

`firebase.json` runs the production Vite build before Hosting deploys `frontend/dist`. The SPA rewrite sends browser routes back to `index.html`, matching the Family Canasta hosting pattern.

The default production build still points API calls at:

```text
http://127.0.0.1:8000/api
```

That is intentional for the recommended local-first hosted mode.

## Run EmberWriter with the hosted UI on Windows

After deployment, start only the local API and open the Firebase-hosted UI with:

```powershell
.\start-hosted.ps1 -FirebaseProjectId YOUR_FIREBASE_PROJECT_ID
```

The launcher automatically allows both of the standard Firebase Hosting origins for that project:

```text
https://YOUR_FIREBASE_PROJECT_ID.web.app
https://YOUR_FIREBASE_PROJECT_ID.firebaseapp.com
```

It then starts FastAPI on `127.0.0.1:8000` and opens the hosted UI. Keep the PowerShell window open while using EmberWriter.

On macOS or Linux:

```bash
chmod +x start-hosted.sh
./start-hosted.sh YOUR_FIREBASE_PROJECT_ID
```

## Browser permission

A browser may ask whether the EmberWriter website can access devices or services on the local network / this device. Allow loopback or local-network access for the EmberWriter Firebase site. If that permission is denied, the hosted UI cannot reach the local FastAPI process and will behave as though the API is offline.

The local API still enforces CORS. The hosted launcher sets `EMBER_CORS_ORIGINS` only for the selected EmberWriter Firebase project rather than allowing arbitrary websites to call the API.

## Using a remote API later

The frontend can also target an HTTPS API instead of localhost. Copy:

```text
frontend/.env.production.example
```

to:

```text
frontend/.env.production.local
```

and set:

```text
VITE_API_BASE_URL=https://your-api-host.example.com/api
```

The `.local` file is ignored by Git so deployment-specific endpoints do not need to be committed.

The backend accepts additional browser origins through:

```text
EMBER_CORS_ORIGINS=https://your-project.web.app,https://your-project.firebaseapp.com
```

## Important: do not put the current data directory on disposable container storage

EmberWriter stores author-owned project files directly under `EMBER_DATA_DIR` and uses SQLite files inside those projects. The repository's backend container defaults `EMBER_DATA_DIR` to `/data` so a real persistent volume can be mounted there.

Do **not** treat an ordinary Cloud Run instance filesystem as durable manuscript storage. Cloud Run's writable container filesystem is disposable when an instance stops. A future fully cloud-hosted EmberWriter backend therefore needs both:

1. durable storage designed for the project files and database state; and
2. authentication/authorization before the API is exposed to the public internet.

The current backend does not yet implement per-user cloud authentication, so the local-first Firebase mode is the recommended hosted configuration until that work is completed.

Cloud Run filesystem reference:
https://cloud.google.com/run/docs/container-contract#file_system

## Backend container

`backend/Dockerfile` is included for staging and for future deployment onto a host that supplies durable storage. It expects:

```text
PORT=8080
EMBER_DATA_DIR=/data
```

Mount durable storage at `/data`, configure `EMBER_CORS_ORIGINS`, and put the service behind HTTPS and authentication before using it for real manuscripts.

## Deployment checklist

- Create a dedicated EmberWriter Firebase project.
- `cd frontend && npm install`.
- `npm run firebase:login`.
- `npm run firebase:use` and select the EmberWriter project.
- `npm run firebase:deploy`.
- Start the local API with `start-hosted.ps1` or `start-hosted.sh` using the same Firebase project ID.
- Allow the browser's loopback/local-network permission when prompted.
- Create a test project, type a paragraph, save, reload, and confirm the paragraph is still present locally.
- Verify revision history before moving any important manuscript workflow to the hosted UI.
