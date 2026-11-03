"""Conservative metadata-only assignment; review text is never evidence."""
import re

CATEGORIES = ['smartphones', 'laptops', 'audio_devices', 'wearables', 'tvs_monitors',
              'accessories', 'tablets', 'networking_devices', 'chargers_power_banks', 'unknown']
RULES = [
 ('chargers_power_banks', r'\b(power bank|charger|charging adapter|charging pad|charging cable)\b'),
 ('wearables', r'\b(smartwatch|smart watch|fitness band|smart band|fitness tracker)\b'),
 ('networking_devices', r'\b(wi-?fi router|wireless router|modem|range extender|network switch)\b'),
 ('audio_devices', r'\b(headphones?|headsets?|earbuds?|earphones?|bluetooth speaker|soundbar|home theatre|car speaker|laptop/desktop speaker)\b'),
 ('accessories', r'\b(external hard disk|external hard drive|external solid state|pendrive|pen drive|microsdxc|memory card|mouse|keyboard|usb hub|webcam)\b'),
 ('tablets', r'\b(ipad|galaxy tab|tablet computer)\b'),
 ('tvs_monitors', r'\b(smart tv|led tv|oled tv|qled tv|computer monitor|ips monitor)\b'),
 ('laptops', r'\b(laptop|notebook|macbook|chromebook)\b'),
 ('smartphones', r'\b(smartphone|iphone|galaxy s\d+|galaxy m\d+|galaxy a\d+|redmi note|realme narzo)\b'),
]
EXCLUDE = re.compile(r'\b(stand|holder|table(?:finish)?|desk|shelf|shelves|case|cover|protector|stabilizer|remote|cabinet|skin|mount|microphone|cushion|sofa\w*|streaming|guitar interface|replacement strap|strap for)\b', re.I)

def categorize(name):
    name = re.sub(r'(Smartwatch)(?=[A-Z])', r'\1 ', str(name or ''))
    # Source mojibake is glued to English device nouns; change only the matching view.
    name = re.sub(r'[^\x00-\x7f]', ' ', name).lower()
    if EXCLUDE.search(name):
        return 'unknown'
    for category, pattern in RULES:
        if re.search(pattern, name):
            return category
    return 'unknown'
