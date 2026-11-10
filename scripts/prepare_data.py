"""Preserve supplied source columns; unknown structured facts remain null."""
from pathlib import Path
from html import unescape
import re
import sys
import pandas as pd

SOURCE_COLUMNS = ['make', 'model', 'trim', 'year', 'title', 'description', 'photo_url']
MONEY = r'([\d,]+(?:\.\d+)?)'
COLORS = r'(white|black|blue|red|silver|grey|gray|green|gold|brown|beige|orange|yellow)'
FUELS = r'(petrol|gasoline|diesel|electric|hybrid)'

BODY_TYPES = [
    ('SUV', r'\bSUV\b|sport utility vehicle'),
    ('sedan', r'\bsedan\b|\bsaloon\b'),
    ('coupe', r'\bcoup[eé]\b'),
    ('hatchback', r'\bhatchback\b'),
    ('convertible', r'\bconvertible\b|\bcabriolet\b|\broadster\b'),
    ('pickup', r'\bpick[ -]?up\b'),
    ('van', r'\bvan\b|\bminivan\b'),
    ('wagon', r'\bwagon\b|\bestate\b'),
]

def asking_price(text):
    # Prefer explicit current prices over older prices, fees and finance examples.
    explicit = re.findall(
        r'\b(?:asking|selling|cash|final|sale) price\s*[:=]?\s*(?:AED\s*)?' + MONEY
        + r'|\b(?:buy now for|now only)\s+AED\s*' + MONEY
        + r'|\bAED\s*' + MONEY + r'\s*(?:in cash|cash price)\b', text, re.I)
    candidates = [next(value for value in groups if value) for groups in explicit]
    if not candidates:
        for match in re.finditer(r'\bAED\s*' + MONEY + '|' + MONEY + r'\s*AED\b', text, re.I):
            before = text[max(0, match.start()-28):match.start()]
            after = text[match.end():match.end()+30]
            if (re.search(r'\b(?:original(?:ly)?(?:\s+price)?|was|down payment|deposit|monthly)\s*[:=]?\s*$', before, re.I)
                    or re.match(r'\s*(?:original price|per month|/month|monthly|down payment|deposit)\b', after, re.I)):
                continue
            candidates.append(match[1] or match[2])
    amounts = {float(value.replace(',', '')) for value in candidates}
    # Explicit asking prices can be below the cutoff used for unlabeled amounts.
    plausible = {value for value in amounts if (0 < value if explicit else 10_000 <= value) and value <= 10_000_000}
    return next(iter(plausible)) if len(plausible) == 1 else None


def extract_fields(title, description):
    text = unescape(re.sub(r'<[^>]+>', '\n', f'{title}\n{description}'))
    result={key:None for key in ['price','mileage_km','body_type','color','transmission','fuel_type','warranty','dubizzle_managed']}
    mileage=re.search(r'\b(?:mileage|odometer|only)\s*:?\s*([\d,]+)\s*kms?\b'
                      r'|\bGCC Specs\s*[:\-]?\s*([\d,]+)\s*kms?\b'
                      r'|\b([\d,]+)\s*kms?\s+driven\b',text,re.I)
    if mileage:
        result['mileage_km']=int(next(group for group in mileage.groups() if group).replace(',',''))
    elif re.search(r'\b0\s*kms?\b', str(title), re.I):
        result['mileage_km'] = 0
    price = asking_price(text)
    result['price'] = int(price) if price is not None and price.is_integer() else price
    for body_type,pattern in BODY_TYPES:
        if re.search(pattern,text,re.I): result['body_type']=body_type; break
    color=re.search(r'\b(?:exterior|body)(?:\s+colou?r)?\s*:\s*'+COLORS+r'\b',text,re.I)
    if not color:
        color=re.search(r'(?<!interior )\bcolou?r\s*:?\s*'+COLORS+r'\b',text,re.I)
    if color: result['color']=color[1].lower().replace('gray','grey')
    transmission=re.search(r'\b(?:transmission|gearbox)\s*:?\s*(?:\d+[- ]speed\s+)?(automatic|manual|cvt)\b'
                           r'|\b(automatic|manual|cvt)\s+(?:(?:\d+[- ]speed)\s+)?(?:transmission|gearbox)\b'
                           r'|\b\d+[- ]speed\s+(automatic|manual|cvt)\b'
                           r'|\b(automatic|manual)\s+export only\b',text,re.I)
    if transmission: result['transmission']=next(group for group in transmission.groups() if group).lower()
    fuel=re.search(r'\b(?:fuel(?: type)?|powertrain)\s*:?\s*'+FUELS+r'\b'
                   r'|\b\d+(?:\.\d+)?\s*l\s+(?:\d+[- ]?(?:cyl(?:inder)?|cyls)\s+)?'+FUELS+r'\b',text,re.I)
    if fuel: result['fuel_type']=next(group for group in fuel.groups() if group).lower().replace('gasoline','petrol')
    elif re.search(r'\b(?:all[- ]electric|fully electric|electric motor|electric (?:sedan|suv|hatchback|vehicle))\b',text,re.I):
        result['fuel_type'] = 'electric'
    if re.search(r'\b(no|without)\s+(?:remaining\s+)?warranty\b',text,re.I): result['warranty']=False
    elif re.search(r'\b(?:under warranty|warranty (?:included|valid|until|covers)|comes with (?:a )?warranty)\b',text,re.I): result['warranty']=True
    elif re.search(r'\b\d+[- ]years?\s+(?:(?:agency|factory|dealer)\s+)?warranty\b',str(title),re.I): result['warranty']=True
    elif re.search(r'\b(?:agency|factory|manufacturer) warranty\b',str(title),re.I): result['warranty']=True
    if re.search(r'\b(?:not|no longer|never)\s+(?:managed by dubizzle|dubizzle[ -]managed)\b', text, re.I):
        result['dubizzle_managed'] = False
    elif (
        re.search(r'\b(?:managed by dubizzle|dubizzle[ -]managed)\b', text, re.I)
        or (
            re.search(r'\bbuy this car with confidence from dubizzle cars\b', text, re.I)
            and re.search(r'\bwe manage the interaction between the buyer and seller\b', text, re.I)
        )
    ):
        result['dubizzle_managed'] = True
    return result

def prepare(force=False):
    root = Path(__file__).resolve().parents[1]
    target = root / 'data/cars.csv'
    if target.exists() and not force:
        print('Existing cars.csv preserved')
        return
    df = pd.read_excel(root / 'Copy_of_sample_cars_dataset.xlsx', sheet_name='raw dataset',
                       usecols=SOURCE_COLUMNS)
    df.insert(0, 'car_id', [f'CAR-{i:03}' for i in range(1,len(df)+1)])
    fields=['price','mileage_km','body_type','color','transmission','fuel_type','warranty','dubizzle_managed']
    for key in fields: df[key] = None
    # Conservative extraction: explicit source text only; never infer from model names.
    for i, row in df.iterrows():
        extracted=extract_fields(row.title,row.description)
        for key,value in extracted.items(): df.at[i,key]=value
    target.parent.mkdir(exist_ok=True)
    df.to_csv(target,index=False)
    print(f'Converted {len(df)} source listings; unknown fields remain empty.')

if __name__ == '__main__': prepare(force='--force' in sys.argv)
