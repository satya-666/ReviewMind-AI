# Starter inspection

Inspected original `ReviewMind_AI_Dataset_Starter.zip (Downloads folder)` on 2026-10-31. Workspace initially contained only `.git`.

ZIP contains `reviewmind_starter/{download.py,README.md,sources.csv,requirements.txt}`; no CSV/JSON/JSONL/Parquet customer-review files. `sources.csv` is a source registry, not review data. Extracted unchanged under `starter/`.

Executed original downloader with `--per-category 1 --out data/raw/starter_probe`. All five categories returned `ConnectError` under sandbox DNS restrictions. Retrieved current Amazon card and API inventory with network permission. Inventory revision `2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e` has raw review JSONL files and metadata Parquet, but no assumed `raw_review_<category>/*.parquet` paths. `Computers` is not an available raw category. No license field in cardData or explicit license in README was found, so Amazon remains excluded rather than downloading unclear-license reviews.

Replacement downloader uses the suggested, publicly accessible, version-1 Flipkart dataset, whose publisher API declares ODbL/DbCL licensing. It reuses the downloaded archive, validates ZIP integrity, checks its SHA-256, and refuses changed licensing or source schema. Existing raw data is not redownloaded. Archive checksum and byte count are in `download_manifest.json`.

The publisher says it scraped Flipkart in December 2022 and already cleaned text; the provided sentiment labels use VADER/manual adjustments. These labels are not promoted to ground truth. The CSV contains 205,052 data rows (the publisher's 205,053 includes one extra/header row). No data was manufactured.
