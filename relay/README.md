# Relay

MERN prototype for assistants and their clients, faithfully ported from `design/relay.html`. This project is isolated from ReviewMind AI. Instrument Sans, palette, responsive layout, owner tags, dashboard, detail and client cards come from the reference. Auth and settings extend those same styles.

## Local setup

Requires Node 20+, npm and MongoDB 7+ (local or Atlas).

```sh
cd relay
npm ci
cp server/.env.example server/.env
# Set a random JWT_SECRET of at least 32 characters in server/.env.
# Start MongoDB, or set MONGODB_URI to your Atlas connection string.
npm run seed
npm run dev
```

Open [localhost:5173](http://localhost:5173). API runs on port 4000. Demo assistant: **alex@demo.com / demo1234**. Demo client: **maya@demo.com / demo1234**. Seed is additive and idempotent; it does not reset existing user changes. Use separate browser profiles to demonstrate simultaneous roles. Public signup creates an assistant and its client workspace; client logins are provisioned by the seed in this prototype, avoiding unauthenticated access to someone else's workspace.

Signup → Settings → Connect account → Gmail/Outlook → simulated consent → API-driven sync progress → inbox. Click a thread to read the full conversation, see confidence and reason, assign an owner, draft, edit and explicitly approve a reply. Use Demo mode for a new personal approval email. A demo inbound message can also be appended to a specific thread via `POST /api/dev/incoming {threadId,body}`; this flags prior manual ownership for review. The client view's handled and handoff changes appear through 10-second polling, including activity on the assistant's thread detail. “Assistant / Client view” is a preview restricted to the assistant's own workspace; actual client credentials are checked on the server.

## Environment

Server reads `server/.env` when run through workspace scripts:

| Variable | Purpose |
| --- | --- |
| MONGODB_URI | MongoDB connection; defaults to local `relay` database |
| JWT_SECRET | Required, at least 32 random characters |
| CLIENT_ORIGIN | Exact frontend origin; local default `http://localhost:5173` |
| PORT | API port, default 4000 |
| NODE_ENV | Set `production` for secure cookies |
| AI_PROVIDER | `openai` or `anthropic` |
| AI_API_KEY | Optional; absent means deterministic rules |
| AI_MODEL | Optional provider model override |

AI output is validated with zod, retried once, then falls back to review on provider failure. No API key means a deterministic working mock. Thread text is untrusted prompt input. An LLM cannot guarantee correct email ownership; the UI exposes confidence, reasoning and human overrides. The mock extracts explicit ISO dates only and does not inspect calendars or attachments.

## What is simulated

Gmail/Outlook consent, mailbox sync and email delivery use `MockEmailProvider`. Each account seeds 25 realistic sample threads using the reference emails, with inbound/outbound histories. No real OAuth scopes, tokens, provider reads or email sends occur. AI can use a real LLM; otherwise classification, questions and drafting use local rules. The provider interface has stub Gmail and Microsoft Graph classes for future real implementations. Disconnect removes that account's prototype threads, messages, drafts and activity after confirmation. No real mail is affected.

## Checks

```sh
# Start an isolated MongoDB on port 27019 before integration tests:
mkdir -p .runtime/mongo
mongod --dbpath "$PWD/.runtime/mongo" --bind_ip 127.0.0.1 --port 27019
# In another terminal:
npm test
npm run build
```

Tests use and erase **only** a database named `relay_test`. Override its address with `TEST_MONGODB_URI`; the database name must remain `relay_test`. Tests cover classification, manual overrides, inbound reclassification, role and tenant isolation, client actions, editable approval-gated drafts, ask examples, validation, cookie flags, simulated connect and disconnect. Production build is Vite's static bundle. `/api/health` returns 503 if MongoDB is unavailable.

## Deploy: Atlas + Render + Vercel

1. Create an Atlas cluster and a database user restricted to the `relay` database. Copy the `mongodb+srv` URI and configure network access for your backend's outbound IPs.
2. Push the repository to GitHub. In Render, select **New → Blueprint**, choose this repository and set Blueprint path to `relay/render.yaml`. Alternatively create a Node web service with root directory `relay`, build `npm ci`, start `npm start`, health check `/api/health`.
3. Set `MONGODB_URI`, generated `JWT_SECRET`, `NODE_ENV=production`, `CLIENT_ORIGIN=https://YOUR-VERCEL-DOMAIN`. Leave `AI_API_KEY` absent for rule-based mode. Deploy and verify `https://YOUR-RENDER-SERVICE.onrender.com/api/health` returns `{ok:true,simulated:true}`.
4. Run `npm run seed` once in the Render shell (or locally with the same Atlas URI), creating the demo users and sample inbox. Seeding is explicit to prevent automatically creating known passwords on an unrelated production database.
5. Replace `REPLACE-RENDER-SERVICE` in `client/vercel.json` with the actual Render service name. In Vercel, import the repo, choose root directory `relay/client`, framework Vite, install `npm install`, build `npm run build`, output `dist`. Deploy. The rewrite proxies `/api` through the frontend origin so the httpOnly SameSite=Lax cookie works without cross-site cookies. Do not point the browser straight to the Render domain.
6. Update Render `CLIENT_ORIGIN` to the exact final Vercel origin, redeploy the API, then verify both demo logins, client handoff and a simulated reply from the Vercel URL. Preview deployment origins are not automatically trusted.

No public deployment URL is claimed until the services are provisioned and these checks pass. This workspace has no authenticated Vercel session. Railway was unreachable during the initial deployment check. Source and configuration are ready; deployment requires authenticated hosting and an Atlas database.

## Architecture and limits

React Router handles pages; TanStack Query polls API resources every 10 seconds and invalidates them after writes. Express authenticates a signed JWT in an httpOnly cookie; queries enforce the assistant/client relationship before fetching messages, drafts or AI indexes. CORS and Origin checks protect browser writes; zod validates inputs. Auth, AI and demo endpoints are rate limited. Errors are centralized; email bodies and credentials are never logged. Deploy a single backend instance for the prototype's in-process rate limiter and account sync jobs. A crash during sync can leave a partial seed or a syncing status; upgrade to a durable job queue and transactional import before real provider ingestion. Replies are simulated and need no real delivery idempotency; add an outbox and provider idempotency before connecting real email.

Future email ingestion would emit a conversation-updated event into a durable queue, driving classification. Extracted dates could become proposed calendar events, never silent calendar writes. Tasks and approval records would reference thread IDs and reuse the same tenant scope and activity log. Approval remains explicit; sensitive actions require a separate auditable approval record before provider execution. This prototype stores drafts generated with AI; subsequent edits are sent at approval time, not autosaved. Provisioning additional real client users needs an invitation and acceptance flow.
