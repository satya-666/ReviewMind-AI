# Product research and default conversation

Gemini is the primary conversational route after one-time permission. The normal composer has no provider checkbox. The customer screen asks for buying needs and budget; optional review controls live in Settings. Answers omit provider labels and focus on up to three evidence-backed suggestions. Consent is stored separately from optional transcripts under `reviewmind_processing_consent_v1`; unknown means ask, declined remains declined across reloads. Settings lets visitors withdraw or grant consent. Retry always uses current consent, so old requests cannot override withdrawal. Review analysis mode works without third-party permission. Existing deployments did not persist the old checkbox, so no earlier acceptance is inferred.

## Provider research (2026-11-13)

| Option | Coverage / cost | Decision and limitations |
| --- | --- | --- |
| [SerpApi Google Shopping](https://serpapi.com/google-shopping-api) | India locale (`gl=in`, `google.co.in`), listing prices, links, optional ratings and specifications. [Pricing](https://serpapi.com/pricing): free 250 searches/month, 50/hour; Starter $25/month for 1,000. | Selected optional adapter. Use only a free account, with no additional credits or paid upgrade. No account created by this change. |
| [Gemini Search grounding](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite) | Search grounding for the configured 3.1 Flash-Lite model is unavailable on its free tier. | Not enabled: would require billing approval. |
| [Google Merchant API](https://developers.google.com/merchant/api/overview) | Manages a merchant's own catalogue, rather than searching the Indian retail market. | Does not satisfy this application's broad product discovery need. |

Use is subject to [SerpApi terms and privacy](https://serpapi.com/legal). The owner must review and accept provider terms when configuring their account. The API is a third-party search-results provider, not a retailer-authorized price feed or a guarantee of upstream licensing. Review deployment obligations before enabling it; this code does not scrape retailer sites, fetch arbitrary URLs or bypass access restrictions.

## Setup

1. Owner creates or uses a SerpApi **Free** account after reviewing its terms. Do not activate paid extra credits.
2. Add `SERPAPI_API_KEY` to the existing Render **backend** environment only, then redeploy. Never put it in frontend configuration, source control, logs or chat.
3. Keep the existing `GEMINI_API_KEY`, fixed model, PostgreSQL connection, Docker service, model checksum and plans unchanged.
4. `/api/chat/status` reports `product_provider_configured`. Configuration alone is not evidence of live retrieval.
5. Accept the application's third-party disclosure and ask for an Indian smartphone under ₹20,000, then Samsung only, then battery preference. Confirm returned cards match the provider's source URLs and INR prices. Compare named returned products and verify missing specifications stay unknown. Record retrieval dates and live results before claiming operational recommendations.

Until a valid key has passed that test, product retrieval is **not operational**. Missing keys return no product cards. Provider quota, auth and network failures are explicit status values, never fabricated products.

## Execution and boundaries

Gemini receives typed function declarations for product search, details and comparison when configured and permitted, plus existing sentiment/aspect tools. The backend validates arguments and executes at most one shopping request per turn; comparisons/details retrieve listing evidence through the same India Shopping endpoint, not a full manufacturer-specifications service. There is one bounded tool round (up to three function calls), followed by a grounded final response. Provider thought signatures are retained in the function-call roundtrip. A second round requesting tools is rejected. Both Gemini HTTP starts count against the existing ten/minute gate; no automatic POST retries.

Explicit review requests still use the real classifier directly without Gemini. Sentiment/aspect function calls invoke the same analysis implementation and return actual saved prediction metadata. Tool-triggered analysis replies use the actual label and attribution limitation; generated causal prose is discarded because the live model invented an averaging mechanism during acceptance testing. No model retraining or replacement.

The backend derives budget from user context, including INR/₹/Rs, commas, k/thousand/lakh. Budget filtering excludes unknown currency/price and over-budget listings. Explicit only/prefer brand preferences are derived from user context and filtered against listing titles; otherwise a tool brand argument must occur in user context. Gemini incorporates category, brand and feature priorities into the search; those are not guaranteed catalogue classifications. Returned specifications and aggregate ratings are listing evidence, not independently verified facts or text-review sentiment. Missing battery specs cannot justify a battery winner. Stock and checkout price are always unconfirmed.

Cards are generated from backend retrieval results, never LLM JSON or sample products. They escape text, validate HTTPS source links, label listing ratings, show UTC retrieval timestamps, and omit unavailable prices/specifications. A timestamp records when this app retrieved a provider response; upstream search results may themselves be cached or stale. There is no persistent product cache or cross-chat data store.

Requests have bounded payload/response sizes, a 12-second product timeout, no redirects and no arbitrary fetch targets. A process-local forty/hour product gate conserves the free allowance; this is **not a durable monthly billing cap**, and resets on restart. The provider account's free plan is the billing boundary. Product queries pass through the selected provider under consent; never include sensitive information. Secrets are excluded from diagnostics and client responses.

## Validation

`tests/test_products.py` uses explicit fixtures for India locale, budget/brand filtering, absent fields, unsafe URLs, provider quota, consent, and the Gemini function-call roundtrip. Fixtures are not live integration evidence. Existing classifier, PostgreSQL, browser and transport regressions remain required. Live retrieval requires the owner-provided credential; no demo products are shipped.
