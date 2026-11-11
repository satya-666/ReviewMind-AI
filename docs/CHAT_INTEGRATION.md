# ReviewMind AI chat integration

## Status

The code integrates a separate Gemini conversational provider and keeps the existing `phase3-full-logistic_regression-seed42` TF-IDF classifier unchanged. The replacement key is configured by the owner on Render, not supplied to this workspace. **A real response from the deployed Gemini backend was verified on 2026-11-12**: Who are you completed in 1.3 seconds with `response_source: gemini`, `provider_status: ready`. A real review completed in 0.47 seconds with the expected battery/display/camera rule results. Local provider fixtures still test contracts only; the separate live evidence is `reports/phase3_5_chat_live_verification.json`. No billing, plan changes or new hosting resources were enabled.

The owner's screenshot showed `reviewmind-web` tracking `phase-1/data-pipeline` at an older commit, while the maintained deployment branch is `phase-3.5/web-integration`. This explains why pushing UX fixes did not update that live service. Recheck both services' dashboard branch settings; pushing another branch does not deploy it. Do not merge or change the repository default branch to solve a hosting branch mismatch.

## Root causes and changes

- The previous form always called `/api/analyze`, which correctly classified arbitrary text but had no concept of message intent. `/api/chat` now performs explicit routing before any classification.
- No conversational provider existed. `backend/app/chat.py` adds the real Gemini REST adapter and a clearly labeled built-in guide when Gemini is unavailable or not authorized by the visitor.
- Old live frontend builds had a shorter timeout. The new client first warms the backend using a bounded GET, then makes one chat POST. No automatic provider POST retry or background keep-awake polling occurs.
- Optional/missing category meant no category-specific aspects. The API preserves this behavior and its warning. Chat users can select a category in Review settings; unselected category does not block greetings/questions. Ambiguous reviews can be explicitly routed with Review analysis mode.
- Dedicated scrolling feedback with a visible footer, consent/rating validation, per-prediction duplicate protection and token deletion remains in place. Only classifier results have prediction feedback.

## Architecture

`frontend` → `/api/chat` intent router → one of:

1. **Review:** existing startup-loaded classifier and lexical aspect rules via the same analysis function used by `/api/analyze`; normal prediction UUID and database metadata write. No Gemini call for review classification.
2. **Conversation/aspect question:** Gemini only if the backend key exists and the visitor opts in; otherwise an explicitly labeled built-in response.
3. **Explanation:** prior prediction UUID looked up in the database for the authentic label/version, then passed as separate grounding metadata to Gemini when authorized. With no provider, a deterministic explanation states the actual recorded label and limits. With no/expired reference, ask for a review instead of guessing a previous prediction. No exact feature attribution is claimed.
4. **Recommendation/comparison/product information:** `ProductData.lookup` is a fail-closed data boundary. With no verified catalogue, return no products, prices, rankings or evidence; explain the limitation and ask for budget/features. User-provided budget can be carried in bounded history, without being treated as a verified market fact. No shopping/search service is simulated.
5. **Unclear/unsupported:** ask clarification, or decline disclosure of credentials/internal instructions. This is routing, not polarity classification.

Rules are conservative, not a universally accurate intent model. Unusual phrasing can require clarification or explicit Review analysis mode. General language-model responses may still be mistaken; the product-data boundary avoids asking the model to produce verified recommendations. It does not establish a validated shopping engine. Aspect labels remain lexical heuristics, not a supervised ABSA model.

## Gemini provider and limits

Selected model: `gemini-3.1-flash-lite`. Google lists free input/output tokens for this model, subject to account/model quotas. Older 2.5 identifiers are not selected because current documentation lists availability/deprecation limitations. The reviewed model ID is allowlisted in settings; changing models requires an explicit pricing/compatibility review.

REST: `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent`, authenticated by a server-only `x-goog-api-key` header. The key is not placed in query strings, prompts, browser configuration, logs, Git or exception responses. Redirects are refused. No tools, search, URLs supplied by users, provider-side persistent sessions or automatic SDK retries are enabled. No new Python runtime dependency or GPU/local LLM is required.

Requests use fixed system instructions, bounded history and authenticated prediction metadata. Assistant/user history is explicitly untrusted input, never system instructions or independent product evidence. Output is displayed as escaped plain text, never executable HTML/Markdown. Empty, blocked, malformed, oversized, credential-echoing, URL or currency-price responses are rejected into a labeled fallback. These checks do not prove a generative model can never hallucinate or disclose its generic instructions; no secret is included in its prompt.

Provider limits per single backend process: 2 simultaneous calls, 10 starts/minute, 20-second socket/network timeout, 512 maximum output tokens and a 64 KiB response cap. Existing API global/IP limits, host/CORS restrictions and 16 KiB body limit still apply. Limits reset at process restart; wider deployment needs distributed abuse controls. Provider output truncation can occur at the token cap.

**Free-tier billing is an account setting, not something this code can guarantee.** Keep the Google project on the Free tier with billing disabled if free-only operation is required. A paid/billing-enabled project may incur charges even when using a model that offers a free tier. Do not enable paid fallback or auto recharge. API quota exhaustion produces a transparent rate-limited fallback; it never switches providers/models automatically.

Official references checked during implementation: [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [GenerateContent API](https://ai.google.dev/api/generate-content), [free-tier pricing and data use](https://ai.google.dev/gemini-api/docs/pricing), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## Privacy and context

The visitor's Gemini checkbox is off by default. It discloses sending messages and recent context, including previous reviews, to Google. Free-tier content may be used to improve Google's products; avoid private information. Review classification itself does not invoke Gemini, but subsequent opted-in conversation can include that review in recent context.

Up to eight recent messages, maximum 1,000 characters/message and 4,000 history characters, are sent from **only the current chat**. Browser requests further trim history to fit the unchanged body limit. Last prediction UUID is also scoped to the current chat. New Chat resets context and prediction reference. The server does not store raw chat transcripts or raw reviews; prediction metadata and existing consented feedback retain their original retention policies. Google processes opted-in requests under its own terms; no claim of zero external retention is made.

The existing opt-in `reviewmind_guest_history_v1` storage key remains compatible with old review-analysis messages. Local history is labeled as browser/device history, not an account or seeded activity. No sample conversations or fake results are shipped. UI conversation source badges distinguish Gemini, built-in guidance/fallbacks and actual classifier results.

## API and setup

Existing health, model-info, analyze, recommend and feedback routes remain compatible. Added:

- `GET /api/chat/status`: configured flag, reviewed model, consent requirement, context policy and whether a valid provider response has occurred since this process started. `configured` means a key is present, not that authentication/quota/model access has been verified. Missing Gemini does not make the existing classifier health check fail.
- `POST /api/chat`: `{text, category?, language?, mode: "auto" | "review", allow_gemini: false, history: [{role: "user" | "assistant", text}], analysis_request_id?}`. Only user/assistant roles accepted; no client system prompt or model metadata override. Responses are either the existing `type: analysis` payload or `type: chat` with reply, intent, response source and provider status.

Set **on the backend only**:

```text
GEMINI_API_KEY=<replacement secret configured in Render>
GEMINI_MODEL=gemini-3.1-flash-lite
```

The key is optional for local testing; missing configuration returns honest built-in responses. `.env.example` contains no key and environment files are not automatically loaded. Existing database/model/origin/host variables remain unchanged. Static frontend keeps `FRONTEND_API_URL=https://reviewmind-api.onrender.com`; never put a provider key on `reviewmind-web`.

## Timeouts and retries

The first message after a one-minute cache interval checks `/api/chat/status` with a 60-second timeout. This warmup GET is shared if needed, rather than duplicating POSTs. Once ready, chat POST has a 30-second timeout; backend provider network wait is capped at 20 seconds per socket operation. UI loading is bounded and submission is disabled until completion/error. User-controlled Retry is available for failed transport requests; provider fallbacks tell users to wait/rephrase/resend rather than claiming success. Feedback remains protected by the server's unique prediction constraint, including an ambiguous network failure followed by retry.

A free Render web service can sleep after 15 idle minutes and take about a minute to resume ([official Render documentation](https://render.com/docs/free)). This is conditional on the actual service plan, not a claim that the existing paid Blueprint service sleeps. A slower wakeup can still reach the bounded timeout; a clear retry is preferable to infinite loading. No keep-awake service or paid plan upgrade is introduced.

## Verification

- **137 pytest tests passed**, including existing Phase 1–3 and TLS PostgreSQL checks.
- **30 browser workflows passed**, including hello/identity (honestly built-in without a key), unsupported recommendation, real review inference, battery/display/camera rules, grounded follow-up, isolated new chat, device history, loading/cold-start GET, timeouts/retry/errors, prediction feedback independently inspected in TLS PostgreSQL, mobile/tablet layouts and keyboard navigation. No unhandled JavaScript errors.
- Provider fixtures test Gemini request headers/payload, role normalization, limits and sanitized failure/response handling. They are **not** live provider success evidence.
- Production frontend build passed with the existing API origin. Render Blueprint passes its official JSON schema. The existing model SHA and metadata verification pass; no weights or model behavior were retrained/replaced.
- Docker build was attempted but could not connect to the stopped local engine. Container runtime/build remains unverified.

Evidence: `reports/phase3_5_chat_tests.txt`, `reports/phase3_5_chat_browser.json`, `reports/phase3_5_chat_verification.json`, and chat screenshots in `reports/figures/`.

## Render release checklist

1. Keep the replacement Gemini key in **reviewmind-api → Environment** and the Google project on the intended free tier. Ensure `GEMINI_MODEL=gemini-3.1-flash-lite` (or let the code default apply).
2. In **both existing services**, select branch `phase-3.5/web-integration`; the owner's earlier screenshot showed an older phase-1 branch. Keep frontend API URL, backend CORS/hosts, PostgreSQL connection, single worker and bundled model intact. Do not create/reimport paid services or change plans just to deploy this update.
3. Manually deploy the latest backend and frontend if dashboard automatic deployment is off. Blueprint automatic deployment remains off; pushing another branch alone does not update an existing service tracking phase-1.
4. Verify `/api/chat/status` and `/api/health` over HTTPS. A missing route means an old backend. A true configured flag alone is not a live provider test.
5. In the deployed UI, opt in to Gemini and send Hello/Who are you. Confirm an actual Gemini source badge and `provider_status: ready`, and that status subsequently reports a provider response since startup. If authentication/quota/model access fails, fix the backend secret/account access rather than interpreting a built-in fallback as success.
6. Test a review with Smartphones selected, ask why it received its recorded label, start New Chat and verify old context is absent, then test feedback storage/deletion. Confirm recommendations still disclose missing verified data.
7. Check hosted memory/latency, browser errors and cold-start behavior. Do not claim the updated deployment or live Gemini success until these hosted checks pass.

## Live timeout diagnosis (2026-11-12)

The live frontend still serves the old exact message `Analysis timed out. Please retry.`, a 15,000 ms timeout and direct `/api/analyze` routing. It does not yet contain the new warmup or chat client. Meanwhile `/api/chat/status` is present and the backend has now returned a genuine Gemini response successfully. This is a mismatched static-site deployment, not evidence that the current chat code times out. The remaining fix is to deploy the current branch on the existing static site. The owner must sign in to Render before that dashboard change can be completed. No new timeout patch or model reload is necessary; the current source already has bounded warmup and separate chat request deadlines.
