from types import SimpleNamespace

import pytest

from src.agent import Agent
from src.leads import Leads
from src.memory import Memory
from src.schemas import ChatRequest
from tests.test_agent import tool_reply
from tests.test_retrieval import inventory


@pytest.fixture
def make_chat(inventory, tmp_path):
    def setup(filters=None, narration=None):
        def planner(**kwargs):
            return tool_reply('search_inventory', filters or {'make': 'Honda'})

        def narrator(**kwargs):
            return SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(content=narration))
            ])

        leads = Leads(tmp_path / 'leads.csv', inventory)
        agent = Agent(inventory, Memory(tmp_path / 'memory.db'), leads, planner,
                      narrator if narration else None)

        def chat(message):
            return agent.chat(ChatRequest(user_id='u', session_id='s', message=message))

        return chat, leads

    return setup


@pytest.mark.parametrize('request_text, budget', [
    ("I wouldn’t want to book H1 on 2099-01-05 at 10 AM", "AED 80,000"),
    ("Book H1 on 2099-01-05 at 8 AM or 10 AM", "AED 80,000"),
    ("Book H1 on 2099-01-05 at 8 or 10 AM", "AED 80,000"),
    ("Book H1 on 2099-01-05 at 09:00–10:00", "AED 80,000"),
    ("Book H1 on 2099-01-05 or 2099-01-06 at 10 AM", "AED 80,000"),
    ("Book H1 on 2099-01-05 at 10 AM", "80,000 USD"),
])
def test_declined_ambiguous_and_foreign_currency_requests_do_not_book(make_chat, request_text, budget):
    chat, leads = make_chat()
    chat(f'{request_text}. My name is Demo User, contact demo@example.com, budget {budget}.')
    assert all(not row['requested_day'] for row in leads.rows())


def test_invalid_replacement_time_cannot_book_the_stale_slot(make_chat):
    chat, leads = make_chat()
    first = chat('Book H1 on 2099-01-05 at 9 AM. My name is Demo User, budget AED 80,000.')
    assert 'contact' in first['reply'].lower()
    chat('My contact is demo@example.com. 10:60 AM please.')
    assert all(not row['requested_day'] for row in leads.rows())
    chat('My contact is demo@example.com.')
    assert all(not row['requested_day'] for row in leads.rows())
    chat('10:00 AM please.')
    row, = leads.rows()
    assert row['requested_hour_24'] == '10'


def test_unmanaged_car_rejection_cannot_be_narrated_as_confirmation(make_chat):
    chat, leads = make_chat(narration='Your viewing is confirmed. See you at the dealership!')
    result = chat('Book H2 on 2099-01-05 at 10 AM. My name is Demo User, '
                  'contact demo@example.com, budget AED 80,000.')
    assert all(not row['requested_day'] for row in leads.rows())
    assert 'Your viewing is confirmed' not in result['reply']
    assert 'managed' in result['reply'].lower()


def test_empty_search_cannot_be_narrated_as_a_match(make_chat):
    chat, _ = make_chat(filters={'make': 'BMW'}, narration='I found a BMW for you. It can be booked right now.')
    result = chat('Show BMW listings.')
    assert result['referenced_cars'] == []
    assert 'I found a BMW' not in result['reply']


def test_split_lead_retains_budget_and_needs_after_contact_and_budget_update(make_chat):
    chat, leads = make_chat()
    chat('My budget is AED 90,000 and I need wheelchair space.')
    assert leads.rows() == []
    chat('My name is Demo User, and my email is demo@example.com.')
    row, = leads.rows()
    assert float(row['budget_max']) == 90000
    assert 'wheelchair space' in row['notes']
    assert not row['requested_day']

    chat('My budget is AED 80,000. My email is demo@example.com.')
    updated, = leads.rows()
    assert float(updated['budget_max']) == 80000
    assert 'wheelchair space' in updated['notes']


def test_contact_opt_out_does_not_create_a_lead(make_chat):
    chat, leads = make_chat()
    chat('My name is Demo User. Do not contact me at demo@example.com. My budget is AED 60,000.')
    assert leads.rows() == []


def test_valid_booking_with_a_preference_still_books(make_chat):
    chat, leads = make_chat()
    chat('Book H1 on 2099-01-05 at 10 AM. My name is Demo User, '
         'contact demo@example.com, budget AED 80,000. I prefer a red car.')
    row, = leads.rows()
    assert row['requested_day'] == '2099-01-05'
    assert 'red car' in row['notes']
