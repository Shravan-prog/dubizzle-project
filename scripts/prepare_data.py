"""Preserve supplied source columns; unknown structured facts remain null."""
from pathlib import Path
from html import unescape
import re
import sys
import pandas as pd

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

def extract_fields(title, description):
    text = unescape(re.sub(r'<[^>]+>', '\n', f'{title}\n{description}'))
    result={key:None for key in ['price','mileage_km','body_type','color','transmission','fuel_type','warranty','dubizzle_managed']}
    mileage=re.search(r'\bMileage\s*:?\s*([\d,]+)\s*(?:km|kms)\b|\bOnly\s+([\d,]+)\s*(?:km|kms)\b',text,re.I)
    if mileage:
        result['mileage_km']=int(next(group for group in mileage.groups() if group).replace(',',''))
    amounts=[]
    for before,after in re.findall(r'\bAED\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*AED\b',text,re.I):
        value=float((before or after).replace(',',''))
        if 10_000 <= value <= 10_000_000: amounts.append(value)
    if amounts: result['price']=int(max(amounts))
    for body_type,pattern in BODY_TYPES:
        if re.search(pattern,text,re.I): result['body_type']=body_type; break
    color=re.search(r'\b(?:exterior\s+)?colou?r\s*:?\s*(white|black|blue|red|silver|grey|gray|green|gold|brown|beige|orange|yellow)\b',text,re.I)
    if color: result['color']=color[1].lower().replace('gray','grey')
    transmission=re.search(r'\b(?:transmission|gearbox)\s*:?\s*(automatic|manual|cvt)\b|\b(automatic|manual|cvt)\s+(?:transmission|gearbox)\b',text,re.I)
    if transmission: result['transmission']=next(group for group in transmission.groups() if group).lower()
    fuel=re.search(r'\b(?:fuel(?: type)?|powertrain)\s*:?\s*(petrol|gasoline|diesel|electric|hybrid)\b',text,re.I)
    if fuel: result['fuel_type']=fuel[1].lower().replace('gasoline','petrol')
    if re.search(r'\b(no|without)\s+(?:remaining\s+)?warranty\b',text,re.I): result['warranty']=False
    elif re.search(r'\b(?:under warranty|warranty (?:included|valid|until|covers)|comes with (?:a )?warranty)\b',text,re.I): result['warranty']=True
    if re.search(r'\b(?:managed by dubizzle|dubizzle[ -]managed)\b',text,re.I): result['dubizzle_managed']=True
    return result

def prepare(force=False):
    root = Path(__file__).resolve().parents[1]
    target = root / 'data/cars.csv'
    if target.exists() and not force:
        print('Existing cars.csv preserved')
        return
    df = pd.read_excel(root / 'Copy_of_sample_cars_dataset.xlsx')
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
