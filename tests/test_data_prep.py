import pytest

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


def test_management_requires_listing_specific_evidence():
    description = ('Buy this car with confidence from dubizzle cars!<br>'
                   'We manage the interaction between the buyer and seller, from beginning to end.')
    assert extract_fields('Ford Edge', description)['dubizzle_managed'] is True
    assert extract_fields('Dealer listing', 'Seller of the month by Dubizzle')['dubizzle_managed'] is None
    assert extract_fields('Private sale', 'This car is not managed by Dubizzle')['dubizzle_managed'] is False


def test_extracts_listing_facts_without_confusing_historical_or_interior_values():
    facts = extract_fields('5 Years Warranty', 'GCC Specs<br>101982 kms<br>2.0L 4-Cylinder Petrol. '
                           'Interior color: Black. Exterior: White. Asking price AED 35,000. Originally AED 60,000.')
    assert (facts['mileage_km'], facts['price'], facts['warranty'], facts['color'], facts['fuel_type']) == (
        101982, 35000, True, 'white', 'petrol')
    assert extract_fields('0KM', 'Warranty until 100,000 km')['mileage_km'] == 0
    assert extract_fields('', 'Warranty until 100,000 km')['mileage_km'] is None
    assert extract_fields('', 'Buy now for AED 35,000. AED 60,000 original price.')['price'] == 35000
    assert extract_fields('', 'Interior color: Black.')['color'] is None


def test_audit_wording_variants():
    assert extract_fields('', 'Transmission: 8-speed Automatic')['transmission'] == 'automatic'
    assert extract_fields('', 'All-electric SUV')['fuel_type'] == 'electric'
    assert extract_fields('', 'Engine Specs: Electric Motor — 286 HP')['fuel_type'] == 'electric'
    assert extract_fields('GLA 35 AMG | AGENCY WARRANTY/SERVICE!', '')['warranty'] is True
    assert extract_fields('', 'This car is no longer managed by Dubizzle.')['dubizzle_managed'] is False
    assert extract_fields('', 'Asking price AED 9,000.')['price'] == 9000


@pytest.mark.parametrize(('description', 'field', 'expected'), [
    ('2.7L V4 Petrol | Automatic', 'fuel_type', 'petrol'),
    ('160000KM Driven, Diesel ,Caravan, Manual Transmission', 'fuel_type', 'diesel'),
    ('Interior And Exterior Is Clean<br>•Fully Automatic<br>•Audio Control On The Steering Wheel',
     'transmission', 'automatic'),
    ('Supplied with 02 Original Keys<br>Fully Automatic for Effortless Driving<br>Stylish Ride',
     'transmission', 'automatic'),
    ('Ford Warranty Till February 2029 or 100,000 km', 'warranty', True),
])
def test_extracts_explicit_listing_variants(description, field, expected):
    assert extract_fields('', description)[field] == expected


def test_automatic_equipment_does_not_describe_transmission():
    assert extract_fields('', 'Fully Automatic Climate Control')['transmission'] is None
