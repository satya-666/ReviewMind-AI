"""Pure cleaning/standardization helpers; originals remain untouched."""
import hashlib
import json
import math
import re
import unicodedata
import pandas as pd

SCHEMA = ['review_id','product_id','product_name','product_category','source_platform',
          'source_dataset','review_text','rating','review_date','language',
          'verified_purchase','helpful_votes','market','source_record_id']

def stable_id(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def clean_text(value):
    if value is None or pd.isna(value):
        return ''
    value = unicodedata.normalize('NFC', str(value))
    value = ''.join(c for c in value if not unicodedata.category(c).startswith('C') or c in '\n\t' or c == '\u200d')
    return ' '.join(value.split())

def normalize_rating(value, scale):
    if value is None or pd.isna(value) or scale is None:
        return None
    try:
        value = float(value)
        low, high = scale
        if not math.isfinite(value) or not low <= value <= high or high <= low:
            return None
        return 1 + 4 * (value-low)/(high-low)
    except (ValueError, TypeError):
        return None

def normalize_date(value):
    if value is None or pd.isna(value):
        return None
    try:
        date = pd.to_datetime(value, utc=True, errors='raise')
        if date > pd.Timestamp.now(tz='UTC'):
            return None
        return date.isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

def usable(text):
    return bool(text) and text.casefold() not in {'nan','none','null','n/a','na'} and any(c.isalnum() or ord(c) >= 0x1F000 for c in text)

def spam_like(text):
    return bool(re.search(r'(.)\1{9,}|https?://|\b(?:whatsapp|telegram)\b', text, re.I))
