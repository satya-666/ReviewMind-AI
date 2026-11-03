"""Keep repeated customer phrases; group exact text and high similarity for splitting."""
import re
from datasketch import MinHash, MinHashLSH
from clean_data import stable_id

def shingles(text):
    text = ' '.join(re.findall(r'\w+', text.casefold()))
    return {text[i:i+5] for i in range(max(1, len(text)-4))}

def duplicate_groups(frame, config):
    parent = list(range(len(frame)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i,j):
        i,j = find(i),find(j)
        parent[max(i,j)] = min(i,j)
    texts = {}; exact_pairs = []; near_pairs = []
    lsh = MinHashLSH(threshold=.75, num_perm=config['permutations'])
    features = {}
    for i, text in enumerate(frame['cleaned_text']):
        key = text.casefold()
        if key in texts:
            union(i,texts[key]); exact_pairs.append((texts[key],i)); continue
        texts[key] = i
        if len(key) < config['min_characters']:
            continue
        grams = shingles(key)
        signature = MinHash(num_perm=config['permutations'], seed=42)
        signature.update_batch([g.encode() for g in sorted(grams)])
        for match in sorted(lsh.query(signature), key=int):
            j = int(match); other = features[j]
            similarity = len(grams & other)/len(grams | other)
            if similarity >= config['jaccard_threshold']:
                union(i,j); near_pairs.append((j,i,similarity))
        lsh.insert(str(i),signature); features[i] = grams
    groups = [stable_id('text_group',frame.iloc[find(i)]['review_id']) for i in range(len(frame))]
    return groups, {'exact_text_pairs': len(exact_pairs), 'near_text_pairs': len(near_pairs),
                    'exact_pairs': exact_pairs, 'near_pairs': near_pairs}
