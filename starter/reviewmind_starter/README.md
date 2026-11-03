# ReviewMind AI — Dataset acquisition starter

**This ZIP contains a downloader and source documentation, not downloaded customer reviews.** The file-host network was inaccessible in the creation environment. No review data was fabricated.

## Run

```bash
python -m pip install -r requirements.txt
python download.py --per-category 2000 --out data
```

The script attempts a bounded sample from Amazon Reviews 2023 categories: Electronics, Cell Phones and Accessories, Computers, Video Games, Office Products. Category names/Parquet availability may change; unavailable categories are reported and skipped. The script reads remotely hosted Parquet files and can require substantial bandwidth or memory depending on server support.

## Sources

1. Amazon Reviews 2023, McAuley Lab: https://amazon-reviews-2023.github.io/ ; https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
2. Flipkart customer reviews (Kaggle, login may be needed): https://www.kaggle.com/datasets/niraliivaghani/flipkart-product-customer-reviews-dataset
3. Hinglish sentiment discovery: https://huggingface.co/datasets?search=hinglish%20sentiment

## License and provenance

- The public accessibility of a dataset **does not** establish a commercial redistribution or model-training license. Inspect the current dataset card, underlying rights, and applicable terms before use.
- Amazon Reviews 2023 is not specifically an India-market dataset.
- The Flipkart Kaggle dataset's uploader, provenance, license, and permitted uses must be verified independently; it is not included here.
- Hinglish datasets are listed for discovery only, and are not necessarily product reviews.
- Do not merge reviews of different product variants without product matching checks.
- Do not infer a review's country from language alone.
- Preserve dataset versions, download dates, and original source citations in your experiment logs.

## Suggested research use

Begin with a few thousand reviews per available category. Inspect class balance and duplicate rates. Split by product and time to reduce leakage. Add an independently licensed Indian-language evaluation set before claiming India-specific performance.
