import pandas as pd
import pytest

@pytest.fixture
def inventory(tmp_path):
    from src.retrieval import Inventory
    rows = [dict(car_id='H1', make='Honda', model='CR-V', year=2022, price=60000, mileage_km=30000, body_type='SUV', color='white', warranty=True, dubizzle_managed=True, trim='Sport', description='Family panoramic roof'), dict(car_id='H2', make='Honda', model='Civic', year=2020, price=40000, mileage_km=70000, body_type='sedan', color='blue', warranty=False, dubizzle_managed=False, trim='LX', description='Efficient commuter'), dict(car_id='T1', make='Toyota', model='RAV4', year=2023, price=None, mileage_km=None, body_type='SUV', color='white', warranty=None, dubizzle_managed=None, trim='', description='Family car')]
    path = tmp_path / 'cars.csv'
    pd.DataFrame(rows).to_csv(path, index=False)
    return Inventory(path)

def test_structured_filter_and_unknowns(inventory):
    from src.schemas import Search
    r = inventory.search(Search(make='honda', body_type='SUV', warranty=True, price_max=65000))
    assert [c['car_id'] for c in r['items']] == ['H1']
    assert inventory.search(Search(price_max=100000))['total'] == 2
    assert inventory.search(Search(warranty=False))['total'] == 1

def test_lexical_ranking_and_pagination(inventory):
    from src.schemas import Search
    assert inventory.search(Search(query='panoramic roof'))['items'][0]['car_id'] == 'H1'
    assert inventory.search(Search(limit=1, offset=1))['items'][0]['car_id'] == 'H2'
    assert inventory.get('missing') is None

def test_required_description_phrase_filters_before_sorting(inventory):
    from src.schemas import Search
    result = inventory.search(Search(make='Honda', query='panoramic roof',
                                     require_description_match=True, sort_by='price'))
    assert [car['car_id'] for car in result['items']] == ['H1']
    result = inventory.search(Search(make='Honda', query='satellite dish',
                                     require_description_match=True))
    assert result['total'] == 0

def test_sorting_places_unknown_values_last(inventory):
    from src.schemas import Search
    result = inventory.search(Search(sort_by='mileage_km', sort_order='asc'))
    assert [car['car_id'] for car in result['items']] == ['H1', 'H2']
    newest = inventory.search(Search(sort_by='year', sort_order='desc', limit=1))
    assert newest['items'][0]['car_id'] == 'T1'

def test_price_coverage_is_scoped_and_unpriced_listings_do_not_rank(inventory):
    from src.schemas import Search
    assert inventory.search(Search(make='Honda', price_max=5000))['unknown_counts'] == {'price': 0}
    ranked = inventory.search(Search(make='Toyota', sort_by='price', limit=1))
    assert ranked['items'] == [] and ranked['sortable_total'] == 0


def test_missing_prices_exclude_listings_with_a_different_body_type(inventory):
    from src.schemas import Search

    inventory.frame.loc[inventory.frame.car_id == 'H2', 'price'] = None
    result = inventory.search(Search(body_type='SUV', price_max=100_000))

    assert [car['car_id'] for car in result['items']] == ['H1']
    assert result['unknown_counts']['price'] == 1
