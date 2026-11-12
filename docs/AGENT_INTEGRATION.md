# Contextual ReviewMind agent — response-routing repair

## Confirmed root cause

Before the repair, live requests with Gemini enabled returned:

- `hellow` → `intent: unclear`, `response_source: built_in`, `provider_status: not_used`.
- `yes` → the same `unclear` route and identical generic paragraph.
- `Who are you?` → `response_source: gemini`, `provider_status: ready`.

The reported repetition was therefore caused by application routing, not a missing key or failed Gemini call. Product requests separately bypassed Gemini with a fixed catalogue disclaimer. Finally, the output guard rejected all currency amounts, including the user's own budget; that could trigger another generic fallback. Short replies had bounded history available but never reached the model that could interpret it.

## Architecture

`POST /api/chat` delegates to `ReviewMindAgent` (`backend/app/agent.py`). It explicitly selects tools; it is not an autonomous browsing/shopping agent or a new training pipeline.

- **Review instructions/review text:** invoke the existing TF-IDF + Logistic Regression inference path and category-specific lexical aspect rules. Strip an explicit `Analyze this review:` prefix before inference. Return real model scores, recorded prediction UUID and normal feedback support. Empty/unusable extracted reviews get validation guidance without a false analysis claim.
- **Normal conversation, typos, short replies, preferences and questions:** invoke Gemini when configured and the visitor opts in. Unknown text defaults to contextual conversation, not a canned introduction or sentiment classification. Explicit review mode remains available if heuristic routing misunderstands unusual wording.
- **Product research/comparison/recommendation:** pass `ProductData.lookup` output as tool context to Gemini. It currently returns unavailable with empty products/sources. The model can ask preference questions and explain general trade-offs, while admitting no catalogue/live prices are connected. There is no fabricated shopping/search integration or ranked product card.
- **Analysis follow-ups:** load the recorded classifier label/version from the database and mark that exact feature attribution is unavailable. Never trust a user-supplied claimed label as a tool result. Gemini can explain the label and limitations, not infer causal feature importance.
- **Secret/internal-instruction requests:** return a short refusal without exposing keys or prompts.

`GET /api/chat/status` reports `agent_version: 2` to identify the deployed routing revision cheaply. The same Gemini model (`gemini-3.1-flash-lite`), key environment variable, fixed REST endpoint, token/concurrency/rate bounds and no-redirect policy remain. No model was retrained or replaced; no new Python package, paid provider or GPU service was introduced.

## Dedicated identity and grounding

`backend/app/prompts.py` contains the ReviewMind system instruction. It asks for concise, contextual conversation, one relevant clarification, no repeated introductions or repeated catalogue paragraphs, use of stated preferences, and explicit separation of generated guidance from verified market facts and classifier results.

The currency guard allows amounts already supplied by the user, so referring to their budget is not treated as a fabricated price. Amounts seen only in assistant history are not trusted. New currency amounts, key echoes and URLs are still rejected. A check rejects common first-person claims of having run/classified a review when no recorded prediction exists. Prompts and these focused checks reduce unsupported claims; they are not a proof that an LLM can never hallucinate. Recommendations/current prices still require a genuine verified product source. User-supplied brand names and preferences are not verified product specifications.

## Conversation memory and privacy

Memory stays scoped to each browser chat. Recent history is bounded to eight messages, 1,000 characters per message and 4,000 history characters. Each chat also keeps bounded user-stated budget, brand and priority notes (up to 200 characters per field); these notes occupy one user-role context entry within the same limits. They survive trimming of the recent-message window and are retained preferentially when reducing request bytes. They are untrusted user preferences, not model-generated facts or verified product data.

New Chat creates a new empty preference object, history and prediction reference. Existing stored chats remain compatible; preference notes can be reconstructed from retained user messages. No server transcript/session table or destructive migration is added. The existing optional browser-storage key and server feedback retention remain. Visitor consent for sending chat context to Google is still required. Built-in notices and failed-provider messages are excluded from future LLM context so they do not reinforce repeated boilerplate.

## Failures and Retry

Provider failures now return explicit error responses rather than HTTP 200 generic fallback paragraphs. Safe diagnostics record only an enumerated error code, upstream HTTP status when available, and routing intent—never key values, message text or provider response bodies.

- Local rate limit is distinguished from Google's quota/rate-limit response.
- Invalid credentials/access, rejected configuration, unavailable provider, network errors, timeout, blocked output and unusable/ungrounded output have separate safe messages.
- The UI shows the corresponding error and Retry, preserving the message and original bounded request context.
- Retry makes one new user-requested POST, replaces the failed assistant entry, and does not duplicate the user bubble or infer a successful Gemini answer. There are no automatic POST retries.
- Draft text edited after a failure is not overwritten by retrying an older message. Existing duplicate-feedback constraints and token deletion remain unchanged.

## Verification

Local verification includes **159 pytest tests passed**, **32 browser workflows passed** with actual classifier inference and isolated TLS PostgreSQL feedback, and a Node built-in transport regression passed. The final extracted-review validation check was also run separately after the full suite. Fixtures test provider success/error contracts; they do not prove live Gemini success.

Coverage includes Hello/hellow/yes/Who are you/How are you, phone-buying requests, budgets, Samsung preference, battery priority, real prefixed review inference, recorded-label follow-up grounding, new-chat isolation, preference retention beyond the recent-message window, provider failures/quota/auth errors, Retry without duplicate user messages, persisted/deleted prediction feedback, keyboard/mobile UI, bounded context and no fabricated product catalogue.

Evidence: `reports/phase3_5_agent_tests.txt`, `reports/phase3_5_agent_browser.json`, screenshots in `reports/figures/phase3_5_agent_*`, and `node --test tests/test_api_client.mjs`. Full research tests require existing local Phase 1–3 datasets/checkpoints; optional TLS PostgreSQL coverage requires an isolated configured database. No production database records are deleted by local tests.

## Deployment and live checks

Push the existing `phase-3.5/web-integration` branch. Both existing Render services now track that branch; their dashboard automatic deployment can publish the update. Static builds keep `SKIP_INSTALL_DEPS=true`, `FRONTEND_API_URL=https://reviewmind-api.onrender.com`, and the Node standard-library build. Backend Docker continues to load the pinned bundled checkpoint and existing PostgreSQL migrations/security configuration.

Check `/api/chat/status` for `agent_version: 2`. Then send an opted-in real multi-turn conversation containing budget, preferred brand and battery priority, verifying `response_source: gemini` and context-sensitive replies without invented models/prices. Run actual review inference and a follow-up with its prediction UUID. Respect existing provider quotas; do not bypass rate limits or enable billing to make tests pass. A configured flag or contract fixture is not a successful live provider test. Final live results are reported after the deployment is verified, separately from local fixtures.

The remaining product-data limitation is deliberate: no verified catalogue/search provider is connected. A future approved implementation can supply verified products and source records through the existing product-data boundary. This change neither creates a fake integration nor adds paid services.
