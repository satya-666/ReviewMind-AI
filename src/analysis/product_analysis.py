"""Product-name groups are evidence proxies, not verified catalog products."""
import pandas as pd
from .dataset_analysis import summary, percent, counts

def product_analysis(frame,config):
    # shortcut: exact names proxy catalog identities; replace only when reliable product IDs arrive.
    groups = frame.groupby('product_group').agg(reviews=('review_id','size'),
        mean_rating=('rating','mean'),category=('product_category','first'))
    sizes = groups['reviews']
    ordered = sizes.sort_values(ascending=False)
    return {'identity_basis':'exact-name product_group proxy; true unique catalog-product count unavailable',
      'unique_product_name_groups':len(groups),'reviews_per_group':summary(sizes),
      'coverage_bands':{'fewer_than_5':int(sizes.lt(5).sum()),'5_to_20':int(sizes.between(5,20).sum()),
                        '21_to_100':int(sizes.between(21,100).sum()),'more_than_100':int(sizes.gt(100).sum())},
      'unweighted_mean_product_group_rating':float(groups['mean_rating'].mean()) if len(groups) else None,
      'product_group_rating_distribution':summary(groups['mean_rating']),
      'groups_by_category':counts(groups['category']),
      'top_1_review_share_percent':percent(int(ordered.head(1).sum()),len(frame)),
      'top_10_review_share_percent':percent(int(ordered.head(10).sum()),len(frame)),
      'review_concentration_hhi':float(((sizes/len(frame))**2).sum()) if len(frame) else None,
      'groups_below_provisional_threshold':int(sizes.lt(config['provisional_product_min_reviews']).sum()),
      'provisional_min_reviews':config['provisional_product_min_reviews'],
      'threshold_note':'A starting evidence floor, not proof of reliable ranking; validate with learning curves, independent customers, deduplication sensitivity and uncertainty intervals.',
      'per_group':{str(k):{'reviews':int(row.reviews),'average_rating':float(row.mean_rating) if pd.notna(row.mean_rating) else None,'category':row.category} for k,row in groups.iterrows()}}
