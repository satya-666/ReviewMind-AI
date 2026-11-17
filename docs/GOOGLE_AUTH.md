# Google sign-in

Production requires Google sign-in before chat, review analysis, recommendations or feedback. Health checks and public configuration remain accessible. The browser sends a Google ID token in the Authorization header; the API verifies Google's signature, issuer, audience and expiration using google-auth and cached public certificates. A verified email is required, and Google's `sub` identifies the account. No Gmail read/send permission or client secret is used.

## Activate on the existing deployment

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) in the owner's Google Cloud project. Complete Branding and Audience as required. For an external app in Testing, add the intended test users; production customer access requires the appropriate published audience.
2. Under Clients, create an OAuth client with application type **Web application**. Add `https://reviewmind-web.onrender.com` as an **Authorized JavaScript origin**. The JavaScript button uses a popup callback; this implementation needs no redirect URI. Optionally add localhost origins for local sign-in testing.
3. Copy the public client ID ending in `.apps.googleusercontent.com`. Set `GOOGLE_CLIENT_ID` on **reviewmind-api** in Render and save/redeploy the backend. Keep client secrets out of source and chat; this flow does not need one. Frontend retrieves the public ID from `/api/auth/config`.
4. Deploy both services with the authentication change. Verify the Google button, account selection, successful authenticated chat and sign-out. An unauthenticated POST to `/api/chat` must return 401. With the ID missing in production, protected routes return 503 rather than allowing guest access.

Do not deploy the production authentication gate before the client ID is configured. Development without a client ID retains local guest access for model tests. Set a client ID to exercise authentication locally.

## Session and history behavior

Tokens stay in browser memory and are never written to localStorage, URLs, transcripts or application logs. Reloading or expiry requires signing in again. Sign-out clears in-memory identity and displayed conversation state. An already running request may finish server-side, but its answer cannot populate a different account's history.

Optional device history is keyed by verified Google subject. Existing guest history remains on the device and is not assigned to a Google account. Sign-out does not delete saved device history. This change adds authentication, not cloud chat storage or inbox integration. Google profile email is displayed locally and is not included in the model prompt.

The API caches Google's public certificates according to their cache headers and bounds certificate network requests to five seconds. Browser and backend timeouts remain bounded. Browser Content Security Policy permits the Google Identity Services script, styles, frame and connection endpoints.

References: [Google ID-token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [Google sign-in button](https://developers.google.com/identity/gsi/web/guides/display-button), [client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

Tests use real RSA-signed fixture tokens to exercise the Google verification library (audience, issuer, expiration, signature and email verification). Browser lifecycle tests cover signed-out gating, successful verification, expiry, sign-out and rejected credentials. These fixtures are not evidence of a live Google account login; that requires the owner's OAuth client setup.
