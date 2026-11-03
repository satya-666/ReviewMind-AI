"""Category coverage with absent categories represented explicitly."""
from scripts.categorize import CATEGORIES
from .dataset_analysis import counts, summary, percent, LANGUAGES, SCHEMA
from .rating_analysis import rating_stats

def category_analysis(frame, config):
    result = {}
    for category in CATEGORIES[:-1]:
        group = frame.loc[frame['product_category'].eq(category)]
        sizes = group.groupby('product_group').size()
        indic = int(group['language'].isin(['hindi','hinglish','other_indic']).sum())
        missing_cells = int(group[SCHEMA].isna().sum().sum())
        result[category] = {'reviews':len(group),'unique_product_name_groups':len(sizes),
          'reviews_per_product_group':summary(sizes),'rating':rating_stats(group),
          'languages':counts(group['language'],LANGUAGES),'sources':counts(group['source_dataset']),
          'missing_schema_cells_percent':percent(missing_cells,len(group)*len(SCHEMA)),
          'largest_product_group_share_percent':percent(int(sizes.max()),len(group)) if len(sizes) else None,
          'insufficient_reviews':len(group)<config['insufficient_category_reviews_below'],
          'product_concentrated':bool(len(sizes) and sizes.max()/len(group)>.5),
          'indic_labeled_reviews':indic,'insufficient_indic_labeled_reviews':indic<config['indic_language_reviews_below']}
    return result
