import pytest
from tests.test_retrieval import inventory
from src.agent import Agent, parse_preferences, collect_booking, fallback_search
from src.memory import Memory
from src.leads import Leads
from src.schemas import ChatRequest, Booking

@pytest.mark.parametrize('amount,expected',[('80k',80000),('80,000',80000),('1.2 million',1200000)])
def test_budget_shorthand(inventory,amount,expected):
    assert parse_preferences('Remember white SUVs under AED '+amount,inventory)['budget_max']==expected
    assert fallback_search('Show Honda under AED '+amount,inventory).price_max==expected

def test_negation_leaves_memory_unchanged(inventory,tmp_path):
    memory=Memory(tmp_path/'m.db')
    memory.update('u',{'preferred_colors':['blue']})
    a=Agent(inventory,memory,Leads(tmp_path/'leads.csv',inventory),lambda **kw:pytest.fail('Must clarify before model'))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Remember I do not like white cars'))
    assert result['active_preferences']['preferred_colors']==['blue']
    assert 'not changed' in result['reply']

def test_booking_requires_real_contact_and_exact_hour(inventory):
    base='Book H1 on 2099-01-05 at {}. My name is User, budget AED 80k. '
    booking,guidance=collect_booking(base.format('10 AM'),[],{},['H1'],inventory,'u')
    assert booking is None and 'contact' in guidance
    booking,guidance=collect_booking(base.format('10:30 AM')+'contact user@example.com',[],{},['H1'],inventory,'u')
    assert booking is None and 'on the hour' in guidance
    booking,guidance=collect_booking(base.format('10 AM')+'contact user@example.com',[],{},['H1'],inventory,'u')
    assert booking.budget_max==80000 and booking.requested_hour_24==10
    with pytest.raises(ValueError):
        Booking(**(booking.model_dump()|{'contact':'2099-01-05'}))

def test_unmanaged_inquiry_is_saved_without_booking(inventory,tmp_path):
    leads=Leads(tmp_path/'leads.csv',inventory)
    a=Agent(inventory,Memory(tmp_path/'m.db'),leads,lambda **kw:pytest.fail('Unexpected model'))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Book H2 on 2099-01-05 at 10 AM. My name is User, contact user@example.com, budget AED 80k. I need space for a family of five.'))
    assert 'could not book' in result['reply'].lower()
    rows=leads.rows()
    assert len(rows)==1 and rows[0]['requested_day']==''
    assert 'family of five' in rows[0]['notes'] and float(rows[0]['budget_max'])==80000
