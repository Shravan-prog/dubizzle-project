from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from main import create_app
from src.memory import Memory
from tests.test_agent import tool_reply
from tests.test_retrieval import inventory


@pytest.fixture
def backend(inventory, tmp_path):
    return TestClient(
        create_app(tmp_path, lambda **kw: tool_reply('search_inventory', {'make': 'Honda'})),
        raise_server_exceptions=False,
    )


def chat(backend, message, session='original'):
    response = backend.post('/chat', json={'user_id': 'audit-user', 'session_id': session, 'message': message})
    assert response.status_code == 200, response.text
    return response.json()


def test_search_sentence_does_not_become_user_name(backend):
    result = chat(backend, 'I am looking for a Honda.')

    assert result['active_preferences']['name'] is None
    assert 'looking for a Honda' not in chat(backend, 'Hello', session='returning')['reply']


def test_multiple_liked_cars_persist_across_sessions(backend):
    chat(backend, 'I like H1.')
    result = chat(backend, 'I like H2.', session='returning')

    assert set(result['active_preferences']['liked_car_ids']) == {'H1', 'H2'}


def test_liked_car_recall_answers_direct_question_in_fresh_session(backend):
    chat(backend, 'I like H1.')
    chat(backend, 'Hello', session='returning')

    reply = chat(backend, 'Which car did I like?', session='returning')['reply']

    assert 'H1' in reply or 'CR-V' in reply
    assert 'Civic' not in reply


def test_saved_budget_includes_both_ends_of_explicit_range(backend):
    result = chat(backend, 'Remember my budget is AED 60,000 to AED 80,000.')

    assert result['active_preferences']['budget_min'] == 60_000
    assert result['active_preferences']['budget_max'] == 80_000


def test_conflicting_budget_change_does_not_corrupt_profile(backend, tmp_path):
    Memory(tmp_path / 'memory.db').update('audit-user', {'budget_min': 70_000})

    result = chat(backend, 'Remember that my budget is AED 50,000.')

    profile = result['active_preferences']
    minimum, maximum = profile['budget_min'], profile['budget_max']
    assert minimum is None or maximum is None or minimum <= maximum
    assert backend.get('/users/audit-user/memory').status_code == 200


def test_new_session_greeting_does_not_drop_sidebar_name(backend, monkeypatch):
    app_file = Path(__file__).resolve().parents[1] / 'app.py'

    def request(method, url, **kwargs):
        kwargs.pop('timeout', None)
        return backend.request(method, urlsplit(url).path, **kwargs)

    monkeypatch.setattr('httpx.request', request)
    app = AppTest.from_file(str(app_file)).run()
    app.text_input[1].set_value('Sam').run()
    app.button[0].click().run()
    app.chat_input[0].set_value('Show me Honda cars.').run()

    assert not app.exception
    assert backend.get('/users/demo-user/memory').json()['name'] == 'Sam'
