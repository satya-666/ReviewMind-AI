"""Unicode-aware counts; no language-wide stopword removal or aspect inference."""
from collections import Counter
import unicodedata
from .dataset_analysis import summary, percent
from .language_analysis import redact

def tokens(text):
    current = []
    result = []
    for character in unicodedata.normalize('NFC',str(text)).casefold()+' ':
        if unicodedata.category(character)[0] in {'L','M','N'}:
            current.append(character)
        elif current:
            word = ''.join(current)
            if len(word)>1 and any(unicodedata.category(c)[0]=='L' for c in word):
                result.append(word)
            current = []
    return result

def frequent_terms(frame,config):
    unigram = Counter(); bigram = Counter()
    for text in frame['cleaned_text']:
        words = tokens(redact(text,limit=None))
        unigram.update(set(words))
        bigram.update(set(zip(words,words[1:])))
    def top(counter):
        pairs = sorted(((k,v) for k,v in counter.items() if v>=config['min_term_document_frequency']),key=lambda p:(-p[1],p[0]))[:config['top_terms']]
        return [{'term':' '.join(k) if isinstance(k,tuple) else k,'review_document_frequency':v} for k,v in pairs if k!='redacted' and 'redacted' not in k]
    product_terms = {'battery','sound','quality','charging','charger','laptop','headphones','speaker','keyboard','display','performance','router','network','power','watch','price'}
    return {'unigrams':top(unigram),'bigrams':top(bigram),
      'selected_product_related_terms':{k:unigram[k] for k in sorted(product_terms) if unigram[k]>=config['min_term_document_frequency']},
      'method':'Unicode letters/marks/numbers; NFC+casefold, no stopwords; document frequency, not validated aspects. Contact-like strings redacted; minimum document frequency applied. Selected product-related terms use an English diagnostic lexicon, not an exhaustive multilingual aspect taxonomy.'}

def text_analysis(frame,config):
    characters = frame['cleaned_text'].fillna('').str.len()
    words = frame['cleaned_text'].fillna('').str.split().str.len()
    result = {'character_length':summary(characters),'whitespace_word_count':summary(words),
      'extremely_short_count':int(words.lt(config['short_words_below']).sum()),
      'extremely_short_percent':percent(int(words.lt(config['short_words_below']).sum()),len(frame)),
      'extremely_long_count':int(words.gt(config['long_words_above']).sum()),
      'extremely_long_percent':percent(int(words.gt(config['long_words_above']).sum()),len(frame)),
      'short_definition':f"fewer than {config['short_words_below']} whitespace-separated words",
      'long_definition':f"more than {config['long_words_above']} whitespace-separated words",
      'empty_cleaned_text_count':int(characters.eq(0).sum()),
      'empty_cleaned_text_percent':percent(int(characters.eq(0).sum()),len(frame)),
      'encoding_warning_count':int(frame.get('encoding_warning',characters.lt(0)).fillna(False).sum()),
      'terms':frequent_terms(frame,config)}
    result['empty_or_encoding_warning_percent'] = percent(int((characters.eq(0) | frame.get('encoding_warning',characters.lt(0)).fillna(False)).sum()),len(frame))
    for column in ['product_category','language','rating']:
        result['by_'+column] = {str(k):{'characters':summary(characters.loc[g.index]),'whitespace_words':summary(words.loc[g.index])} for k,g in frame.groupby(column)}
    return result
