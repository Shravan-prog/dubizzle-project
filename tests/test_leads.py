from tests.test_retrieval import inventory
from src.schemas import Booking

def test_booking_rules(inventory, tmp_path):
    from src.leads import Leads
    service = Leads(tmp_path/'leads.csv',inventory)
    args = dict(user_id='u',user_name='User',contact='user@example.com',car_id='H1',requested_day='2099-01-05',requested_hour_24=10,budget_max=65000)
    for day,hour in [('2099-01-04',10),('2099-01-05',21)]:
        assert not service.book(Booking(**(args | dict(requested_day=day,requested_hour_24=hour))))['ok']
    assert service.book(Booking(**args))['ok']
    assert not service.book(Booking(**args))['ok']
    assert not service.book(Booking(**(args|{'car_id':'H2'})))['ok']
    assert len(service.rows()) == 1
