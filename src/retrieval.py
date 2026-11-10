import json
import re
from html import unescape
import pandas as pd
from rank_bm25 import BM25Okapi
from src.schemas import Search

class Inventory:
    def __init__(self, path):
        self.frame = pd.read_csv(path).fillna(value=float('nan'))
        for key in Search.model_fields:
            if key in ('body_type', 'color', 'transmission', 'fuel_type', 'warranty', 'dubizzle_managed', 'price', 'mileage_km') and key not in self.frame:
                self.frame[key] = None
        self.tokens = [self.normalized_description(f'{r.get("description", "")} {r.get("trim", "")}').split()
                       or ['_'] for r in self.frame.to_dict('records')]
        self.bm25 = BM25Okapi(self.tokens)

    def search(self, filters: Search):
        df = self.frame.copy()
        sortable_total=None
        requested={
            'price': filters.price_min is not None or filters.price_max is not None,
            'mileage_km': filters.max_mileage_km is not None,
            'body_type': filters.body_type is not None,
            'color': filters.color is not None,
            'transmission': filters.transmission is not None,
            'fuel_type': filters.fuel_type is not None,
            'warranty': filters.warranty is not None,
            'dubizzle_managed': filters.dubizzle_managed is not None,
        }
        for key in ['make', 'model']:
            value = getattr(filters, key)
            if value is not None:
                normalize = lambda text: re.sub(r'[\W_]+', '', text.casefold())
                df = df[df[key].astype(str).map(normalize) == normalize(value)]
        for value, lower in [(filters.year_min, True), (filters.year_max, False)]:
            if value is not None:
                df = df[df.year >= value] if lower else df[df.year <= value]
        if filters.require_description_match:
            phrase = self.normalized_description(filters.query)
            descriptions = df['description'].fillna('').map(self.normalized_description)
            df = df[(' ' + descriptions + ' ').str.contains(f' {phrase} ', regex=False)] if phrase else df.iloc[:0]
        if phrase := self.normalized_description(filters.exclude_description_query):
            descriptions = df['description'].fillna('').map(self.normalized_description)
            df = df[~(' ' + descriptions + ' ').str.contains(f' {phrase} ', regex=False)]
        query_tokens = self.normalized_description(filters.query).split()
        if query_tokens and not filters.require_description_match:
            terms = set(query_tokens)
            df = df.loc[[index for index in df.index if terms.intersection(self.tokens[index])]]
        if filters.sort_by in requested:
            requested[filters.sort_by] = True
        constraints = {}
        for key in ['body_type', 'color', 'transmission', 'fuel_type']:
            value = getattr(filters, key)
            if value is not None:
                constraints[key] = df[key].astype(str).str.casefold() == value.casefold()
        for key in ['warranty', 'dubizzle_managed']:
            value = getattr(filters, key)
            if value is not None:
                constraints[key] = df[key].astype(str).str.lower() == str(value).lower()
        for arg, col, lower in [('price_min','price',True),('price_max','price',False),('max_mileage_km','mileage_km',False)]:
            value = getattr(filters,arg)
            if value is not None:
                values = pd.to_numeric(df[col], errors='coerce') if col in df else pd.Series(float('nan'), index=df.index)
                exclusive = ((arg == 'price_max' and filters.price_max_exclusive)
                             or (arg == 'max_mileage_km' and filters.max_mileage_exclusive))
                mask = values >= value if lower else (values < value if exclusive else values <= value)
                constraints[col] = constraints[col] & mask if col in constraints else mask
        unknown_counts = {}
        for key, active in requested.items():
            if not active:
                continue
            missing = df[key].isna()
            for other, mask in constraints.items():
                if other != key:
                    missing = missing & mask
            unknown_counts[key] = int(missing.sum())
        for mask in constraints.values():
            df = df.loc[mask.reindex(df.index)]
        if filters.sort_by and filters.sort_by != 'relevance':
            values = pd.to_numeric(df[filters.sort_by], errors='coerce')
            sortable_total=int(values.notna().sum())
            df = df.assign(_sort=values).dropna(subset=['_sort']).sort_values(
                '_sort', ascending=filters.sort_order == 'asc',
                na_position='last', kind='stable').drop(columns='_sort')
        elif query_tokens:
            scores = self.bm25.get_scores(query_tokens)
            df = df.assign(_score=[scores[i] for i in df.index]).sort_values('_score', ascending=False, kind='stable').drop(columns='_score')
        return {'total':len(df),'items':json.loads(df.iloc[filters.offset:filters.offset+filters.limit].to_json(orient='records')),'unknown_counts':unknown_counts,'sortable_total':sortable_total}

    @staticmethod
    def normalized_description(text):
        plain = re.sub(r'<[^>]+>', ' ', unescape(str(text)))
        return ' '.join(re.findall(r'\w+', plain.casefold()))

    def get(self, car_id):
        rows = self.frame[self.frame.car_id == car_id]
        return json.loads(rows.to_json(orient='records'))[0] if len(rows) else None
