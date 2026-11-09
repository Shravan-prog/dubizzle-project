from scripts.prepare_data import extract_fields

def test_extracts_only_explicit_structured_facts():
    fields=extract_fields(
        'White SUV',
        'Mileage: 35,711 km. Selling price: AED 115,750. '
        'Automatic transmission. Fuel: petrol. Warranty included.')
    assert fields | {} == fields
    assert fields['mileage_km']==35711
    assert fields['price']==115750
    assert fields['body_type']=='SUV'
    assert fields['transmission']=='automatic'
    assert fields['fuel_type']=='petrol'
    assert fields['warranty'] is True

def test_does_not_infer_missing_facts_from_model_name():
    fields=extract_fields('Honda CR-V', 'Well maintained family vehicle.')
    assert fields['body_type'] is None
    assert fields['price'] is None
    assert fields['warranty'] is None
