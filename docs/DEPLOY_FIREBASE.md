# Firebase Hosting for EmberWriter

EmberWriter can use Firebase Hosting for its React/Vite UI while keeping manuscripts, Story Intelligence, project databases, and local AI services on the author's computer.

## Recommended deployment today: hosted UI, local data

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
        +-- optional local Stable Diffusion service
```

This provides a stable HTTPS UI without moving author-owned project files or local model access into disposable cloud storage.

Modern browsers treat loopback resources such as `127.0.0.1` and `localhost` specially. A browser implementing Local Network Access may prompt the user to allow the Firebase site to reach the local service. Allow that permission for the EmberWriter Firebase origin when prompted.

References:

- Firebase Hosting: https://firebase.google.com/docs/hosting
- MDN Local network access: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Local_network_access
- MDN Secure contexts: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts

## Reproducible frontend install

The frontend has a committed `package-lock.json`; use the locked install:

```powershell
cd frontend
npm ci
```

`firebase-tools` is intentionally not installed as a frontend application dependency. The package scripts invoke the pinned deployment CLI on demand with `npx`, which keeps Firebase CLI transitive packages out of the production/development application dependency tree while preserving the same commands.

## One-time Firebase setup

Sign in:

```powershell
npm run firebase:login
```

Create a dedicated Firebase project for EmberWriter in Firebase, or create one with the Firebase CLI. Do not reuse an unrelated application project. Bind this repository to the EmberWriter project:

```powershell
npm run firebase:use
```

`firebase use --add` writes the selected project into a local `.firebaserc` file. Commit `.firebaserc` after the EmberWriter Firebase project ID is final if the repository should always deploy to that project.

## Deploy the UI

From `frontend/`:

```powershell
npm run firebase:deploy
```

`firebase.json` runs the production Vite build before Hosting deploys `frontend/dist`. The SPA rewrite sends browser routes back to `index.html`.

The default local-first production mode can still target:

```text
http://127.0.0.1:8000/api
```

when the hosted UI is intended to talk to the author's local EmberWriter service. CI also verifies the alternate hosted-API build path so a deployment configured with `VITE_API_BASE_URL` does not leak hard-coded localhost API URLs.

## Run EmberWriter with the hosted UI on Windows

After deployment, start the local API and open the Firebase-hosted UI with:

```powershell
.\start-hosted.ps1 -FirebaseProjectId YOUR_FIREBASE_PROJECT_ID
```

The launcher allows the two standard Firebase Hosting origins for that project:

```text
https://YOUR_FIREBASE_PROJECT_ID.web.app
https://YOUR_FIREBASE_PROJECT_ID.firebaseapp.com
```

It starts FastAPI on `127.0.0.1:8000` and opens the hosted UI. Keep the PowerShell window open while using EmberWriter.

On macOS or Linux:

```bash
chmod +x start-hosted.sh
./start-hosted.sh YOUR_FIREBASE_PROJECT_ID
```

## Browser permission

A browser may ask whether the EmberWriter website can access devices or services on the local network / this device. Allow loopback or local-network access for the EmberWriter Firebase site. If that permission is denied, the hosted UI cannot reach the local FastAPI process and will behave as though the API is offline.

The local API still enforces CORS. The hosted launcher sets `EMBER_CORS_ORIGINS` for the selected EmberWriter Firebase project rather than allowing arbitrary websites to call the API.

## Using a remote API later

The frontend can target an HTTPS API instead of localhost. Copy:

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

## Do not put author data on disposable container storage

EmberWriter stores author-owned project files directly under `EMBER_DATA_DIR` and uses SQLite files inside those projects. The backend container defaults `EMBER_DATA_DIR` to `/data` so a real persistent volume can be mounted there.

Do **not** treat an ordinary Cloud Run instance filesystem as durable manuscript storage. Cloud Run's writable container filesystem is disposable when an instance stops. A future fully cloud-hosted backend therefore needs both durable storage designed for project files/database state and authentication/authorization before the API is exposed to the public internet.

The current backend is not presented as a public multi-user service, so the local-first Firebase mode remains the recommended hosted configuration until those controls exist.

Cloud Run filesystem reference:
https://cloud.google.com/run/docs/container-contract#file_system

## Backend container

`backend/Dockerfile` is included for staging and for deployment onto a host that supplies durable storage. It expects:

```text
PORT=8080
EMBER_DATA_DIR=/data
```

Mount durable storage at `/data`, configure `EMBER_CORS_ORIGINS`, and put the service behind HTTPS plus authentication before using it for real manuscripts.

## Deployment checklist

- Create a dedicated EmberWriter Firebase project.
- `cd frontend && npm ci`.
- `npm run firebase:login`.
- `npm run firebase:use` and select the EmberWriter project.
- `npm run firebase:deploy`.
- Start the local API with `start-hosted.ps1` or `start-hosted.sh` using the same Firebase project ID.
- Allow the browser's loopback/local-network permission when prompted.
- Create a test project, type a paragraph, save, reload, and confirm the paragraph is still present locally.
- Verify revision history before moving important manuscript work to the hosted UI.
