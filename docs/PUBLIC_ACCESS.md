# Public portfolio access preparation

Status: **prepared for owner review; repository remains private**. The live demo is public and does not require sign-in for review analysis or shopping demo requests.

## What was checked

The remote branches were fetched before scanning all 34 locally reachable commits. A credential-pattern scan inspected 452 unique text blobs, including historical versions. No Google API key, GitHub token, AWS access key, Render token, private-key block, literal JWT or credential-bearing URL pattern matched. Three preliminary URL matches were inspected and were false positives crossing quoted fixture fields; the corrected URL pattern excludes quotes.

This is a bounded pattern scan, not a guarantee that no private material exists. Forty binary blobs (figures/screenshots and the serving artifact across history) were not scanned as text. The serving checkpoint SHA-256 and metadata were verified separately. [Machine-readable audit scope](../reports/publication_readiness.json).

No raw customer review datasets are tracked; the `data/` tree contains placeholders only. The evaluation command writes real error text into ignored local data files. Provider keys remain in Render environment settings. The Google OAuth client ID shown by the application is public configuration, not a client secret.

## What changing visibility exposes

GitHub visibility applies to the **whole repository**, not just the deployment branch:

- All branches, commit history, and Git author metadata.
- The ReviewMind source, aggregate evaluation reports and bundled trained classifier.
- **41 already-committed files under `relay/`**, a separate project in the same repository. Existing uncommitted Relay work was preserved locally and was not pushed with this release.

Deleting Relay only from a new commit would leave its older versions accessible in history. No history rewriting, force-push, Relay deletion or visibility change was performed. If Relay should stay private, keep this repository private and publish a separately reviewed ReviewMind-only repository instead.

## Portfolio landing page

The observed default GitHub branch is `phase-1/data-pipeline`, while the deployed application tracks `phase-3.5/web-integration`. The latter contains the current demo README, screenshot, architecture, commands, measured evaluation and limitations. Before sending recruiters a repository landing-page link, either merge the reviewed deployment branch through the normal PR process or deliberately select that branch as the default. No default-branch or branch-protection setting was changed.

The release is [43dc54b](https://github.com/satya-666/ReviewMind-AI/commit/43dc54b0d0df1fc71bfcabc400afa60f542e934b); the [live demo](https://reviewmind-web.onrender.com/) has been checked signed out, including a 390-pixel mobile layout.

## Licensing and owner approval

No source-code license file is present. Public visibility permits viewing; it does not itself grant an open-source reuse license. Select a code license only if you intend to grant those rights. No license was invented or applied on your behalf.

The dataset publisher's recorded ODbL/DbCL declarations, attribution and limitations remain documented in [Phase 1](PHASE_1.md) and [the README](../README.md). Dataset terms do not license this project's source code or prove every underlying marketplace right. The bundled model is a derived training artifact; its inclusion has been disclosed for the owner's publication decision.

The remaining approval is specific: whether to make **satya-666/ReviewMind-AI and its complete history, including the committed Relay project and serving model, publicly accessible**. No credentials need to be shared in chat to make that decision.
