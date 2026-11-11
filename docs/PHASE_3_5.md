# Phase 3.5 — web integration and deployment preparation

## Status and scope

Implemented locally on `phase-3.5/web-integration`, based on Phase 3 commit `5eead1988d9465fb74efd6976642cd00942272d5`. No Phase 4/5 work, public deployment, paid resource creation, main merge or pull request is included.

The supplied design was found as `Downloads/index.html` (matching the described mock frontend), rather than `index(1).html`. Its source fingerprint is in `reports/phase3_5_frontend_source.json`. The original file is untouched. Its stylesheet is preserved as the prefix of `frontend/assets/styles.css`; appended rules support real result controls and correct mobile overflow. Pink/purple/lime colors, typography, layout, themes, sidebar, preferences, animations and modal design remain.

## Architecture and served model

Static HTML/CSS/JavaScript → centralized `frontend/assets/api-client.js` → FastAPI → one startup-loaded `ReviewPredictor` → SQLAlchemy prediction metadata/feedback storage. Local FastAPI also serves the frontend; Render separates static UI and Docker API. Only frontend assets are public, never data/model directories.

The actual serving checkpoint is `models/phase3/full/baseline/logistic_regression.joblib`, version `phase3-full-logistic_regression-seed42`, selected using Phase 3 validation macro F1. The 3,028,276-byte artifact has SHA-256 `edb379f3f5ed60fb3f8321b12a90bed4c08b3a408e2812112bf12b988b3462d0`. `backend/model_manifest.json` pins that identity and the service verifies it before joblib deserialization. Only use the trusted, owner-produced artifact; pickle/joblib is executable serialization.

Inference reuses `src/models/inference.py`, its training-time cleaning, saved TF-IDF pipeline and category-aware lexical aspect rules. No retraining or unrelated pretrained substitution occurs. One model copy, one process and one simultaneous inference are used. Internally the existing predictor supports lists, while the public API accepts one review. Torch/transformers are not imported by this serving path.

Overall labels are negative/neutral/positive, learned from rating-derived weak labels. Probabilities are uncalibrated. Aspect labels are heuristic, can differ from overall sentiment, and do not establish supervised ABSA accuracy or aspect percentages. English has weak-label evaluation; Hindi has no validated training/evaluation and Hinglish examples are insufficient. Language selection accepts input and displays these limitations, rather than claiming reliable multilingual NLP.

## API

| Endpoint | Behavior |
| --- | --- |
| `GET /api/health` | Model and live database readiness; 503 if either unavailable. |
| `GET /api/model-info` | Public version, labels, categories, capabilities and limitations; no internal paths. |
| `POST /api/analyze` | `{ "text": "The battery is excellent but the camera is disappointing.", "category": "Smartphones", "language": "en" }`; actual prediction, rule aspects, warnings and server UUID. |
| `POST /api/recommend` | Accepts existing query/preferences format; structured `not_available`, `analysis_only`, empty products. |
| `POST /api/feedback` | Server prediction UUID, integer rating 1–5, optional corrected label/message and `consent: true`; returns 201 only after commit, plus deletion token. |
| `DELETE /api/feedback/{id}` | Deletes feedback with returned `X-Delete-Token`. |

Input is bounded (review 5,000 characters, message 1,000, body 16 KiB). Invalid, missing/expired prediction, duplicate feedback, rate limit and unavailable model/storage responses are explicit safe errors. Development documentation is `/api/docs`; production docs/debug are disabled.

## Frontend and privacy

`frontend/index.html` retains the provided design; `assets/app.js` replaces the mock flow. Auto mode routes clear product questions to the unavailable-recommendation endpoint; explicit Analyze/Recommendation modes remain available because intent detection is deliberately simple. Real results show model identity and rule aspects without fabricated cards, percentages, trust scores, prices or evidence. Network, malformed response, busy model, rate limit and loading states are handled without a mock fallback.

Guest profile settings do not authenticate anyone. Plans retain their modal but upgrades and unsupported billing claims are disabled. Saved products, fake-review radar, comparisons and evidence are labeled upcoming/unavailable. No payments are integrated.

History persistence is opt-in on the current browser, stores structured messages (not saved HTML), and has a working clear function. Local history contains user text if enabled; shared-device users should clear it. Server prediction rows contain only UUID, model version, label and timestamp, never the raw review. Feedback requires consent; optional messages may contain personal information, so users should avoid including it. Feedback deletion uses an opaque token; only its hash is stored server-side. Losing the token prevents guest self-service deletion, so retain it until deletion or expiration.

SQLAlchemy uses local SQLite under ignored `.cache/web/`; production requires PostgreSQL and explicit Alembic migrations. Feedback is retained 30 days. Cleanup runs on startup, writes and hourly; expired prediction metadata is removed when no linked feedback remains. Availability interruptions may delay cleanup until the service resumes. No raw-review collection for training is implemented.

## Local setup

Run from the repository root with Python 3.14 and the exact approved Phase 3 artifact already present:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/model_metadata.json models/phase3/full/baseline/logistic_regression.metadata.json
.venv/bin/python scripts/verify_serving_model.py
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Open http://127.0.0.1:8000. Development creates SQLite tables automatically. `.env.example` documents configuration; environment files are not automatically loaded, so export selected variables in your shell or hosting dashboard. Never commit a real `.env` or database URL. A fresh clone includes only the approved small serving checkpoint, not datasets or other research checkpoints. Reproduce Phase 1–3 for the full research suite. Docker also bundles `backend/model_metadata.json` next to the checkpoint. Missing/corrupt artifacts fail verification.

For PostgreSQL, provide a TLS-enabled database URL via `DATABASE_URL`, set `AUTO_CREATE_DB=false`, then run:

```sh
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

The adapter requires TLS (`sslmode=require`); it encrypts transport but does not pin a CA/verify hostname. Use Render's private database network and approved connection settings. Do not expose a local test database or its temporary test authentication configuration.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development` locally, `production` on Render. |
| `MODEL_PATH` | Trusted checkpoint path; `/app/runtime/model.joblib` in Docker. |
| `MODEL_MANIFEST_PATH` | Optional alternate manifest; defaults to bundled pinned manifest. |
| `DATABASE_URL` | Local SQLite or secret PostgreSQL URL. |
| `AUTO_CREATE_DB` | True only for development; false in production. |
| `ALLOWED_ORIGINS` | Comma-separated exact frontend origins; HTTPS required in production. |
| `ALLOWED_HOSTS` | Exact API hosts; defaults to Render-provided hostname in production. |
| `FRONTEND_API_URL` | Public API origin for static build; never a secret. Empty means same origin locally. |
| `RATE_LIMIT_PER_MINUTE` | Default 20 per observed client IP. |
| `GLOBAL_RATE_LIMIT_PER_MINUTE` | Default 120 mutations across the process. |
| `PORT` | Hosting port; defaults to 8000 in startup script. |

## Safeguards and limits

Exact CORS origins, origin checks on mutations, trusted hosts, bounded requests, escaped rendering, security headers, safe errors/logging and model checksum checks are implemented. Only `/assets` is mounted. Database connections use bounded pools/timeouts. Production configuration fails closed without HTTPS origins, hosts, PostgreSQL and explicit migrations. Access logging is disabled in startup commands.

The rate limiter is single-process/in-memory and resets at restart. It does not trust arbitrary forwarded IP headers; behind a hosting proxy multiple users may share a limit. It is suitable for a small guarded beta, not distributed abuse protection. A trusted edge/distributed limiter and proxy identity configuration need validation before wider traffic or additional workers. Anonymous callers can submit requests without browser Origin headers; CORS is not authentication. No accounts, moderation service, SLA, independent penetration test or high-load capacity claim is included. External Google Fonts are retained from the original design.

The runtime dependency audit queried public advisories on 2026-11-04: 32 packages, zero known findings (`reports/phase3_5_dependency_audit.json`). Re-audit before release; this is not proof of security. Source-code licensing has not been selected. Dataset publisher ODbL/DbCL notices are documented in Phase 1; underlying marketplace/author rights and model/public-use obligations are not independently cleared. Review these before public access. No review excerpts or datasets are redistributed by the web UI.

## Validation and measurements

The recorded full suite passed **89 tests**, including a real TLS PostgreSQL migration/persistence/deletion check. A later default run may skip the optional PostgreSQL case unless `TEST_POSTGRES_URL` is set. Existing Phase 1–3 tests remain in the suite. `reports/phase3_5_test_results.txt` preserves that executed full run; browser and runtime reports are separate.

```sh
# Development/test tools and original research dependencies:
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q
# Against a separately running local API on 8765; allow that origin and
# increase test-only rate limits to avoid throttling the workflow suite:
WEB_TEST_URL=http://127.0.0.1:8765 .venv/bin/python scripts/test_web_browser.py
.venv/bin/python scripts/benchmark_web.py
```

Full research tests require local prepared datasets/models. Optional database coverage uses `TEST_POSTGRES_URL` pointing to an isolated TLS test database; migrate that database first. Browser tests exercise actual English/Hindi/Hinglish inference, differing aspects, recommendations unavailable, persisted/deleted feedback, history refresh/clear, validation/HTML escaping, loading, language, mobile, themes and disabled billing. Error responses are deliberately intercepted only for error-path tests, not prediction tests. See `reports/phase3_5_browser.json` for the exact latest count and screenshots in `reports/figures/phase3_5_*`.

Fresh macOS Apple M3 process: app ready **4.13 s**, model load **1.94 s**, model-ready process RSS **257 MiB**, post-request RSS **227 MiB**. Thirty warmed sequential TestClient requests with actual inference and SQLite metadata writes: median **17.1 ms**, p95 **23.7 ms**, maximum **29.0 ms**. This excludes network latency and is not a Linux/Render or load benchmark. A clean environment containing only backend requirements also started and performed actual analysis without transformer imports. Docker build has **not** been verified: the local Docker daemon was unavailable. Render Blueprint was validated against its official JSON schema, not applied to an account.

## Render preparation and remaining deployment steps

`render.yaml` describes a static site, a single Docker API and private PostgreSQL in Singapore. Automatic deployments are off. **Importing/applying the Blueprint still creates paid resources: obtain owner approval before doing so.** Nothing was deployed or uploaded for hosting during Phase 3.5.

The API uses `backend/Dockerfile` and `backend/start.sh` with repository-root build context (`dockerContext: .`). The sole approved 2.9 MiB checkpoint is explicitly allowed by Git/Docker ignore rules and copied to `/app/runtime/model.joblib`, with bundled metadata at `/app/runtime/model.metadata.json`. `scripts/verify_serving_model.py` checks the pinned SHA-256 and metadata version during the image build and again at startup, before migrations and the single API worker. ModelService retains its independent checksum/version checks before deserialization. No network fetch, external model storage or `MODEL_ARTIFACT_URL` is required. All other checkpoints, datasets, caches and secrets remain excluded. The non-root user can read the model.

GitHub authenticated API visibility check on 2026-11-11 reported this repository as **private**. Publishing the model here was explicitly authorized for this deployment. Anyone with repository or image access can extract it; Docker does not provide confidentiality. Do not make either public without explicit approval and rights review.

After owner approval and rights review:

1. Build/test the Docker image on a working Docker engine and rerun dependency audit. Validate Linux startup/memory under the chosen plan before inviting users.
2. Confirm the deployment branch contains the exact approved checkpoint and keep the repository private. No external model artifact provisioning is necessary.
3. Review current Render prices/credit eligibility/expiration in the account, then import the Blueprint from this branch. Approve charges explicitly. Keep automatic deployments off.
4. Keep API `MODEL_PATH=/app/runtime/model.joblib`; set exact static-site HTTPS `ALLOWED_ORIGINS`, and host configuration if using a custom domain. The Blueprint supplies internal `DATABASE_URL`; keep external database IP access disabled and automatic schema creation off.
5. Set static-site `FRONTEND_API_URL` to the API HTTPS origin. Its Node-only build writes `frontend/assets/config.js`; no Python runtime or frontend framework is required.
6. Manually deploy the API, checking bundled-model verification, migration and health readiness without exposing secret logs. Build/deploy the static site; use the final assigned frontend origin in API CORS.
7. Repeat smoke tests over HTTPS: actual model identity/inference, unsupported recommendations, error/rate paths, real PostgreSQL feedback and deletion, responsive UI, history/privacy and security headers. Verify proxy-rate behavior and memory/CPU metrics.
8. Invite a limited beta only after these checks, rights review and explicit public-launch approval. Monitor credits, billing, memory and latency; configure account budget alerts and stop paid resources when no longer needed.

The initial recommendation is API `0.5c-512mb` (512 MiB, one worker) with PostgreSQL `0.1c-256mb` and 1 GB database storage. Local measurements suggest the baseline can fit, but do not guarantee Render peak memory; verify before launch and upgrade only if measured limits require it. Transformer checkpoints are not proposed for 512 MiB.

At the official pricing checked during preparation, API about $7/month + PostgreSQL $6/month + 1 GB storage at $0.30/GB/month gives **about $13.30/month**, with the static site/workspace assumed within free allowances. $50 would cover roughly 3.7 months at that constant rate **only if those charges are credit-eligible**, excluding taxes and overages; expiry may shorten this. Confirm live account prices before purchase. References: [Render compute plans](https://render.com/docs/compute-plans), [Blueprint specification](https://render.com/docs/blueprint-spec), [pricing](https://render.com/pricing), [published example plan costs](https://render.com/articles/production-rails-hosting-guide), [storage pricing explanation](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses).

Public beta assessment: **local integration verified, hosting preparation complete; not yet publicly deployed or cleared for public release**. Deployment approval, rights review, a real container build and hosted acceptance checks remain explicit launch gates.

## Bundled-model deployment validation (2026-11-11)

The external-fetch script is replaced by a local verification script. See `reports/bundled_model_validation.json` for this change’s executed checks and limits. Historical Phase 3.5 reports describe the original implementation; the bundled-model report supersedes their external-storage strategy. No Render resources were created or deployed by this change.

Required production API variables: `APP_ENV=production`, `AUTO_CREATE_DB=false`, `MODEL_PATH=/app/runtime/model.joblib`, secret `DATABASE_URL` (Blueprint internal PostgreSQL), exact HTTPS `ALLOWED_ORIGINS`, and exact `ALLOWED_HOSTS` or the automatically supplied `RENDER_EXTERNAL_HOSTNAME`. Keep rate limits at 20/client/minute and 120/global/minute unless deliberately reviewed. The static site requires `FRONTEND_API_URL=https://<your-api-host>` and builds with `node scripts/build_frontend.mjs`, publishing `frontend`. Backend is `reviewmind-api`, Docker runtime, branch `phase-3.5/web-integration`, Dockerfile `backend/Dockerfile`, root/context repository root, health `/api/health`. Startup remains `sh backend/start.sh`; migrations and all existing API/frontend contracts are preserved. Remove any stale `MODEL_ARTIFACT_URL` from manually configured Render settings.
