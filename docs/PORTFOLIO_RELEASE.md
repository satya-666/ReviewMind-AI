# Portfolio release verification

## Release setup

- Existing branch: `phase-3.5/web-integration`; existing services `reviewmind-api` (Docker/free) and `reviewmind-web` (static). No new service, plan or database is requested.
- Backend dashboard last deployed `1f0f73b` before this release; deploy history shows automatic deployments on pushes. The checked-in blueprint disables automatic deploys and is not an exact export of the existing live services.
- The public GitHub API returned 404 for the given repository URL on 2026-11-22. The signed-in GitHub repository page also displayed Private; the URL is correct. Visibility is not changed without owner approval.
- Backend Google public client ID was saved in the existing Render environment before pushing account-enabled code. No provider keys were read, copied or committed.

## Diagnosis

The supplied wireless-earbuds request was posted to the original live backend with consent and returned HTTP 503 `timeout` after 34.00 seconds. Gemini was configured, SerpApi was configured, and Render warns that the free service can take at least 50 seconds to wake from inactivity. Render application logs independently recorded `Chat provider failed (code=timeout http=None intent=comparison)` for this request. This establishes an upstream generation timeout for the reproduced warm request, rather than an empty shopping result. The prior browser loading observation alone did not establish an infinite server request.

Explicit shopping requests now retrieve source listings first (12-second search socket timeout). Gemini has a 30-second per-request timeout and at most two model rounds. A failed generation retains actual source cards when retrieved; search outage, missing configuration and successful zero-results searches have distinct statuses. No fabricated comparison is used. The frontend bounds cold-start GET warm-up (60s) and chat POST (90s), clears loading on every completion path, retains the draft, and retries without automatically repeating a POST or adding a duplicate user bubble. Provider timeout fixtures and real UI-handler tests cover these paths.

## Evaluation

Run `scripts/evaluate_portfolio.py`. See [measured report](../reports/portfolio_evaluation.md). TF-IDF train-only refit, all test predictions, split/source IDs, token-canonical keys and seeded approximate duplicate audit were verified. The current serving model has macro F1 0.672835 versus majority 0.281653 on 2,451 weakly labeled reviews. There is no independent human sentiment/ABSA benchmark. Private real-error text is generated locally and excluded from Git; public report contains IDs and observed labels.

## Final checks

- Full Python suite: **189 passed, 1 skipped** (PostgreSQL integration requires `TEST_POSTGRES_URL`). Two existing Alembic deprecation warnings remain.
- Node transport/auth/UI handler checks: **8 passed**, including editable sample, review routing without third-party consent, bounded transport, and timeout retry without duplicate user bubbles.
- After the last fallback-label adjustment, focused provider/history regression: **19 passed**.
- Production frontend build and serving model SHA-256/metadata verification passed. The acquired dataset archive hash matches its recorded provenance manifest.
- Local Chrome smoke: sample produces Neutral (0.414 uncalibrated score), camera positive, battery negative, charging speed negative; exact evidence shown. Shopping produces a recoverable missing-provider status with no local secrets configured.
- Screenshot in `docs/images/review-analysis.png` captures actual local classifier output.
- Both existing Render services automatically built and deployed `cc0e3fd`; backend deployment succeeded in 1m 26s. `/api/health` reported model/storage ready. `/api/auth/config` returned the configured public client ID; signed-out `/api/chats` returned 401.
- Clean Chrome Incognito production smoke at **390 CSS pixels**: the editable sample ran without sign-in or third-party permission; Neutral overall, positive camera, negative battery and charging, with evidence quotes. A small label-wrap issue found during this check was corrected in the follow-up CSS.
- The exact shopping request returned HTTP 200 in **8.87 seconds**, with actual provider source cards and `product_status=ok`. The generated comparison failed the grounding guard (`ungrounded_response`), so a clearly labeled built-in notice and Retry were shown instead. The production browser also showed retrieved prices/source links, unknown specifications, unconfirmed availability, restored draft and an enabled Send button. This is a verified recoverable comparison failure, not a claim that generated comparison quality passed.
- Follow-up regression: **20 passed** after canonical URL encoding, three-option request handling and the mobile label fix. Static production build passed again. Google account login itself was not exercised; identity signature and account-isolation tests passed locally. No user chats were deleted in production.
- The repository remains private; changing visibility requires owner approval. All pre-existing `relay/` work was excluded from the release.
