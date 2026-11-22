# Google sign-in and public demo

Review analysis and shopping demo requests are available without login. Account chat APIs (`/api/chats`, including read/delete) require a verified Google identity; a supplied invalid token is rejected even on public demo requests. Guest conversations are tab-only unless the user enables device history. Signed-in chats are saved to their account until deletion. Third-party provider consent is separate from sign-in.

## Token verification

Google sign-in is required for account history and feedback. Public review and shopping demo requests remain available without a token. The browser sends a Google ID token in the Authorization header; the API verifies Google's signature, issuer, audience and expiration using google-auth and cached public certificates. A verified email is required, and Google's `sub` identifies the account. No Gmail read/send permission or client secret is used.

## Activate on the existing deployment

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) in the owner's Google Cloud project. Complete Branding and Audience as required. For an external app in Testing, add the intended test users; production customer access requires the appropriate published audience.
2. Under Clients, create an OAuth client with application type **Web application**. Add `https://reviewmind-web.onrender.com` as an **Authorized JavaScript origin**. The JavaScript button uses a popup callback; this implementation needs no redirect URI. Optionally add localhost origins for local sign-in testing.
3. Copy the public client ID ending in `.apps.googleusercontent.com`. Set `GOOGLE_CLIENT_ID` on **reviewmind-api** in Render and save/redeploy the backend. Keep client secrets out of source and chat; this flow does not need one. Frontend retrieves the public ID from `/api/auth/config`.
4. Deploy both services with the authentication change. Verify the Google button, account selection, successful authenticated chat and sign-out. An unauthenticated GET to `/api/chats` must return 401. With the ID missing in production, account routes return 503; public demo requests still work.

Do not deploy the production authentication gate before the client ID is configured. Development without a client ID retains local guest access for model tests. Set a client ID to exercise authentication locally.

## Session and history behavior

Tokens stay in browser memory and are never written to localStorage, URLs, transcripts or application logs. Reloading or expiry requires signing in again. Sign-out clears in-memory identity and displayed conversation state. An already running request may finish and save to its original account server-side, but its answer cannot populate a different account's history.

Chats are stored in the existing PostgreSQL database and keyed by the verified Google subject. Users can list, reopen and continue chats after signing in on another device. Each chat has a Delete control; Settings offers Delete all chats, both requiring confirmation. Ownership is checked on every read, append and deletion. Chat responses are saved directly from server execution, never accepted from client JSON. Chat text persists until deletion; feedback retains its separate 30-day retention. Database backups may retain deleted data according to the hosting provider's backup policy.

The current limits are 100 chats per account and 100 messages (50 exchanges) per chat, with a 1 MB maximum stored payload per chat. Full chats require starting a new one; reaching the account limit requires deleting an old chat. Old guest/device-only history stays on the original browser and is not imported or assigned to a Google account. Authentication does not request Gmail inbox access. Account email is not included in model prompts.

The new `0002_chats` migration runs through the existing `backend/start.sh` Alembic startup step. No database plan or paid infrastructure change is required. Chat content is stored only for authenticated users; development guest requests remain transient.

The API caches Google's public certificates according to their cache headers and bounds certificate network requests to five seconds. Browser and backend timeouts remain bounded. Browser Content Security Policy permits the Google Identity Services script, styles, frame and connection endpoints.

References: [Google ID-token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [Google sign-in button](https://developers.google.com/identity/gsi/web/guides/display-button), [client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

Tests use real RSA-signed fixture tokens to exercise the Google verification library (audience, issuer, expiration, signature and email verification). Browser lifecycle tests cover protected account credentials and public guest demo access, successful verification, expiry, sign-out and rejected credentials. These fixtures are not evidence of a live Google account login; that requires the owner's OAuth client setup.
