# Acceptance verification

Verified locally on 15 November 2026. Source reference remains unchanged at `design/relay.html`.

| Requested behavior | Result and evidence |
| --- | --- |
| Signup, simulated Gmail/Outlook connection, sync status | API integration test covers signup and Outlook; browser showed Gmail syncing and connected. Consent and onboarding are implemented; a fresh signup onboarding walkthrough was not browser-tested. |
| Owner, reason, confidence on every thread | API checks all 25 seeded threads. Reference invoice regression checked separately. |
| Low confidence goes to Needs review | Classification test and browser Sofia thread. |
| Manual owner persists | API mutation, refetch, and reclassification preserve manual source and 100% confidence. |
| Inbound triggers reclassification | API test forces previous manual assignment into review; browser Demo mode inserted an approval thread and updated counts. |
| Client isolation and handled/handoff | API tests unauthenticated, wrong-role and cross-tenant access, handled and handoff; browser signed in as Maya, saw only client threads and successfully handed the new arrival to Alex. |
| Draft editable, approval required | API asserts drafting creates no message, missing approval is rejected and edited text is stored after approval; browser generated an editable draft and showed approval disabled while composer was empty. |
| Ask example questions | All four questions tested through API, including ownership explanations; returned IDs are scoped. |
| Desktop/mobile, light/dark | Browser viewed desktop dashboard/detail and 390 × 844 mobile dashboard/detail, toggled light/dark. No exhaustive device/browser matrix. |
| Public deployment URL and demo logins | **Blocked**: no authenticated Vercel CLI session or Atlas database supplied; Railway initial API lookup failed. Deploy configuration and exact steps are in README. No public URL exists. |

`npm test`: includes tenant/auth checks, mock classification, manual override protection, client actions, draft approval, account lifecycle, input validation and provider-output fallback. `npm run build`: production Vite build. Dependency audit after the Zod update: zero reported vulnerabilities. Live OpenAI/Anthropic requests were not run without credentials. Simulated replies never reach a real mailbox.
