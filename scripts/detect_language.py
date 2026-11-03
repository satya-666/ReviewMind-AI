"""Heuristic labels plus deterministic langdetect; confidence is not calibrated."""
import re
from functools import lru_cache
from langdetect import DetectorFactory, detect_langs, LangDetectException
DetectorFactory.seed = 42
HINDI_ROMAN = {'hai','hain','nahi','nahin','bahut','bohot','accha','achha','acha','achhi',
               'bekar','kharab','paisa','paise','mast','mat','lekin','mera','meri','iska','bhi','kaafi'}
INDIC_CODES = {'bn','gu','kn','ml','mr','ne','pa','ta','te','ur'}

@lru_cache(maxsize=100000)
def detect_language(text):
    tokens = re.findall(r'[a-z]+', text.lower())
    roman_hits = set(tokens) & HINDI_ROMAN
    latin = bool(tokens)
    deva = bool(re.search(r'[\u0900-\u097f]', text))
    if deva:
        # Devanagari also covers Marathi/Nepali; never equate script with Hindi.
        try:
            best = detect_langs(text)[0]
            if latin:
                return 'hinglish', None, True, 'mixed_script_heuristic'
            if best.lang == 'hi' and best.prob >= .95:
                return 'hindi', float(best.prob), False, 'langdetect_devanagari'
            if best.lang in INDIC_CODES and best.prob >= .95:
                return 'other_indic', float(best.prob), False, 'langdetect'
        except LangDetectException:
            pass
        return 'unknown', None, True, 'ambiguous_devanagari'
    if len(roman_hits) >= 2 or (roman_hits and len(tokens) <= 4):
        return 'hinglish', None, True, 'roman_hindi_lexicon'
    if len(tokens) < 4 and not re.search(r'[^\x00-\x7f]', text):
        return 'unknown', None, True, 'short_text'
    try:
        best = detect_langs(text)[0]
        confidence = float(best.prob)
        if confidence < .95 or roman_hits:
            return 'unknown', confidence, True, 'uncertain_langdetect'
        label = 'english' if best.lang == 'en' else 'other_indic' if best.lang in INDIC_CODES else 'other'
        return label, confidence, len(tokens) < 4, 'langdetect'
    except LangDetectException:
        return 'unknown', None, True, 'no_language_evidence'
