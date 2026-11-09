import json
import re
import pandas as pd
from rank_bm25 import BM25Okapi
from src.schemas import Search

class Inventory:
    def __init__(self, path):
        self.frame = pd.read_csv(path).fillna(value=float('nan'))
        for key in Search.model_fields:
            if key in ('body_type', 'color', 'warranty', 'dubizzle_managed', 'price', 'mileage_km') and key not in self.frame:
                self.frame[key] = None
        self.tokens = [re.findall(r'\w+', f'{r.get("description", "")} {r.get("trim", "")}'.lower()) or ['_'] for r in self.frame.to_dict('records')]
        self.bm25 = BM25Okapi(self.tokens)

    def search(self, filters: Search):
        df = self.frame.copy()
        sortable_total=None
        requested={
            'price': filters.price_min is not None or filters.price_max is not None,
            'mileage_km': filters.max_mileage_km is not None,
            'body_type': filters.body_type is not None,
            'color': filters.color is not None,
            'warranty': filters.warranty is not None,
            'dubizzle_managed': filters.dubizzle_managed is not None,
        }
        unknown_counts={key:int(self.frame[key].isna().sum()) for key,active in requested.items() if active}
        for key in ['make', 'model', 'body_type', 'color']:
            value = getattr(filters, key)
            if value is not None:
                df = df[df[key].astype(str).str.casefold() == value.casefold()]
        for key in ['warranty', 'dubizzle_managed']:
            value = getattr(filters, key)
            if value is not None:
                df = df[df[key].astype(str).str.lower() == str(value).lower()]
        for arg, col, lower in [('year_min','year',True),('year_max','year',False),('price_min','price',True),('price_max','price',False),('max_mileage_km','mileage_km',False)]:
            value = getattr(filters,arg)
            if value is not None:
                values = pd.to_numeric(df[col], errors='coerce') if col in df else pd.Series(float('nan'), index=df.index)
                df = df[values >= value] if lower else df[values <= value]
        if filters.sort_by and filters.sort_by != 'relevance':
            values = pd.to_numeric(df[filters.sort_by], errors='coerce')
            sortable_total=int(values.notna().sum())
            df = df.assign(_sort=values).sort_values(
                '_sort', ascending=filters.sort_order == 'asc',
                na_position='last', kind='stable').drop(columns='_sort')
        elif filters.query:
            scores = self.bm25.get_scores(re.findall(r'\w+',filters.query.lower()))
            df = df.assign(_score=[scores[i] for i in df.index]).sort_values('_score', ascending=False, kind='stable').drop(columns='_score')
        return {'total':len(df),'items':json.loads(df.iloc[filters.offset:filters.offset+filters.limit].to_json(orient='records')),'unknown_counts':unknown_counts,'sortable_total':sortable_total}

    def get(self, car_id):
        rows = self.frame[self.frame.car_id == car_id]
        return json.loads(rows.to_json(orient='records'))[0] if len(rows) else None
