# Bounded language-label inspection

Inspected the private, contact-pattern-redacted sample produced by `run_phase2.py` on 2026-11-03. Seed 42 selects six records each from supplied `unknown`, `hinglish` and `other` labels after sorting review IDs. The 18 record IDs and text excerpts stay in ignored `data/interim/phase2_language_sample.json`; no excerpts are published here. Contact-pattern redaction cannot guarantee anonymization of arbitrary free text, so the sample remains local.

Observations from this inspection:

- The six `unknown` samples are short, predominantly English phrases; one contains profanity. Short text alone provides weak evidence for automatic language identification.
- The six `hinglish` samples plausibly mix Romanized Hindi with English, including very short mixed phrases and one longer code-mixed review. This does not validate every Hinglish label in the corpus.
- The six `other` samples appear English or contain English spelling/spacing errors rather than clearly demonstrating another language. This suggests label noise in this sample.

This is a small diagnostic inspection, not an independently annotated evaluation set or an accuracy estimate. No source labels were changed, and no fabricated Hindi examples were added. Future work needs independent annotators, a written labeling policy, disagreement handling and more licensed code-mixed examples. The sample contains no basis for inferring customer geography.
