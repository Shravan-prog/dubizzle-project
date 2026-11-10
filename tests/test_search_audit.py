from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from src.agent import Agent
from src.leads import Leads
from src.memory import Memory
from src.retrieval import Inventory
from src.schemas import ChatRequest
from tests.test_agent import tool_reply
from tests.test_retrieval import inventory


@pytest.fixture
def actual_inventory():
    return Inventory(Path(__file__).resolve().parents[1] / 'data' / 'cars.csv')


def chat_with(inventory, tmp_path, plan, narrator=None):
    completion = plan if callable(plan) else lambda **kw: tool_reply('search_inventory', plan)
    agent = Agent(inventory, Memory(tmp_path / 'memory.db'),
                  Leads(tmp_path / 'leads.csv', inventory), completion, narrator)
    return lambda message: agent.chat(ChatRequest(user_id='u', session_id='s', message=message))


def test_manual_gearbox_uses_structured_transmission(actual_inventory, tmp_path):
    chat = chat_with(actual_inventory, tmp_path, {'transmission': 'manual'})
    result = chat('Show me cars with a manual gearbox.')
    assert 'CAR-066' in [car['car_id'] for car in result['referenced_cars']]


def test_description_exclusion_stops_at_budget_clause(inventory, tmp_path):
    chat = chat_with(inventory, tmp_path, {'make': 'Honda', 'query': 'panoramic roof', 'price_max': 70000})
    result = chat('Find Hondas without a panoramic roof under AED 70,000.')
    assert [car['car_id'] for car in result['referenced_cars']] == ['H2']


def test_provider_outage_preserves_explicit_color(inventory, tmp_path, monkeypatch):
    monkeypatch.setattr('src.agent.time.sleep', lambda _: None)

    def unavailable(**kwargs):
        raise RuntimeError('503 unavailable')

    chat = chat_with(inventory, tmp_path, unavailable)
    assert chat('Show me red Honda cars.')['referenced_cars'] == []


def test_search_does_not_reinterpret_usd_as_aed(inventory, tmp_path):
    chat = chat_with(inventory, tmp_path, {'make': 'Honda', 'price_max': 70000})
    result = chat('Show Honda cars under USD 70,000.')
    assert result['referenced_cars'] == []
    assert 'AED' in result['reply']


def test_ambiguous_pronoun_asks_which_listing(inventory, tmp_path):
    chat = chat_with(inventory, tmp_path, {'make': 'Honda'})
    assert len(chat('Show me Honda cars.')['referenced_cars']) == 2
    result = chat('Does it have a warranty?')
    assert result['referenced_cars'] == []
    assert 'which' in result['reply'].lower()


def test_direct_details_answer_all_requested_fields(actual_inventory, tmp_path):
    chat = chat_with(actual_inventory, tmp_path, {'make': 'Honda'})
    result = chat('What are the mileage and warranty of CAR-087?')
    assert '79,000 km' in result['reply']
    assert 'warranty' in result['reply'].lower()
    assert 'not listed' in result['reply'].lower()


def test_explicit_comparison_includes_both_listings(actual_inventory, tmp_path):
    chat = chat_with(actual_inventory, tmp_path, {'make': 'BMW', 'model': 'M4'})
    result = chat('Compare the price and warranty of CAR-023 and CAR-026.')
    assert {car['car_id'] for car in result['referenced_cars']} == {'CAR-023', 'CAR-026'}
    assert 'warranty' in result['reply'].lower()


def test_transmission_followup_answers_from_focused_listing(actual_inventory, tmp_path):
    chat = chat_with(actual_inventory, tmp_path, {'make': 'Toyota'})
    chat('What is the mileage of CAR-066?')
    result = chat('Does it have automatic transmission?')
    assert [car['car_id'] for car in result['referenced_cars']] == ['CAR-066']
    assert 'manual' in result['reply'].lower()
    assert '| Price |' not in result['reply']


def test_inventory_narrator_cannot_invent_listing_features(actual_inventory, tmp_path):
    def narrator(**kwargs):
        return NS(choices=[NS(message=NS(
            content='This Honda CR-V is black, has a panoramic sunroof, and is ready for a test drive.'
        ))])

    chat = chat_with(actual_inventory, tmp_path, {'make': 'Honda'}, narrator)
    result = chat('Show me Honda cars.')
    assert [car['car_id'] for car in result['referenced_cars']] == ['CAR-087']
    assert 'sunroof' not in result['reply'].lower()
    assert 'ready for a test drive' not in result['reply'].lower()


@pytest.mark.parametrize('question', [
    'Can you show me cars on Yalla Motor?',
    'What is the capital of France?',
])
def test_out_of_scope_requests_cannot_reach_inventory(inventory, tmp_path, question):
    chat = chat_with(inventory, tmp_path, {'make': 'Honda'})
    result = chat(question)
    assert result['referenced_cars'] == []
    assert not result['tool_calls']
    assert 'dubizzle' in result['reply'].lower()


def test_recall_does_not_echo_blocked_competitor(inventory, tmp_path):
    chat = chat_with(inventory, tmp_path, {'make': 'Honda'})
    chat('Can you recommend Carswitch?')
    result = chat('What did I ask earlier?')
    assert 'carswitch' not in result['reply'].lower()


def test_provider_attempts_stay_within_client_timeout(inventory, tmp_path, monkeypatch):
    timeouts = []
    delays = []
    monkeypatch.setattr('src.agent.time.sleep', delays.append)

    def planner(**kwargs):
        timeouts.append(kwargs['timeout'])
        assert kwargs['num_retries'] == 0
        if len(timeouts) < 3:
            raise RuntimeError('503 unavailable')
        response = tool_reply('search_inventory', {'make': 'Honda'})
        response.choices[0].message.tool_calls *= 2
        return response

    def narrator(**kwargs):
        timeouts.append(kwargs['timeout'])
        assert kwargs['num_retries'] == 0
        return NS(choices=[NS(message=NS(content='Here are the Honda listings.'))])

    chat = chat_with(inventory, tmp_path, planner, narrator)
    assert chat('Show Honda cars.')['referenced_cars']
    assert len(timeouts) == 4
    assert sum(timeouts) + sum(delays) + 5 < 45


def test_narrator_can_describe_a_verified_result_set_ceiling(inventory, tmp_path):
    def narrator(**kwargs):
        return NS(choices=[NS(message=NS(content='I found two Honda listings under AED 70,000.'))])

    chat = chat_with(inventory, tmp_path, {'make': 'Honda', 'price_max': 70000}, narrator)
    result = chat('Show me Honda cars under AED 70,000.')
    assert result['reply'].startswith('I found two Honda listings under AED 70,000.')
    assert result['tool_calls'][-1]['source'] == 'model'
