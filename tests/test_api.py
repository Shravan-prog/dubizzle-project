from fastapi.testclient import TestClient
from tests.test_retrieval import inventory
from tests.test_agent import tool_reply

def test_http_flow(inventory,tmp_path):
    from main import create_app
    client=TestClient(create_app(tmp_path,lambda **kw:tool_reply('search_inventory',{'make':'Honda'})))
    assert client.get('/health').json()['inventory_count']==3
    assert client.get('/inventory',params={'make':'Honda'}).json()['total']==2
    assert client.get('/inventory',params={'price_min':100,'price_max':10}).status_code==422
    session=client.post('/sessions/reset',json={'user_id':'u'}).json()['session_id']
    response=client.post('/chat',json={'user_id':'u','session_id':session,'message':'Show Honda cars'})
    assert response.status_code==200
    assert len(response.json()['referenced_cars'])==2
    assert client.get('/leads',params={'user_id':'u'}).json()['items']==[]
    assert client.post('/chat',json={'user_id':'other','session_id':session,'message':'Hello'}).status_code==403


def test_refresh_restores_transcript_and_car_context(inventory, tmp_path):
    from pathlib import Path
    from unittest.mock import patch
    from urllib.parse import urlsplit
    from streamlit.testing.v1 import AppTest
    from main import create_app

    backend = TestClient(create_app(tmp_path, lambda **kw: tool_reply('search_inventory', {'make': 'Honda'})))
    app_file = Path(__file__).resolve().parents[1] / 'app.py'

    def request(method, url, **kwargs):
        kwargs.pop('timeout', None)
        return backend.request(method, urlsplit(url).path, **kwargs)

    with patch('httpx.request', side_effect=request):
        first = AppTest.from_file(str(app_file)).run()
        first.text_input[0].set_value('refresh-user').run()
        first.chat_input[0].set_value('Show Honda cars').run()
        session = first.query_params['session']

        refreshed = AppTest.from_file(str(app_file))
        refreshed.query_params.update(first.query_params)
        refreshed.run()
        assert not refreshed.exception
        assert refreshed.text_input[0].value == 'refresh-user'
        assert any(item.value == 'Show Honda cars' for item in refreshed.markdown)
        refreshed.chat_input[0].set_value('What is the mileage on that first Honda?').run()
        assert any('30,000 km' in item.value for item in refreshed.markdown)

        refreshed.button[0].click().run()
        assert refreshed.query_params['session'] != session
        assert not any(item.value == 'Show Honda cars' for item in refreshed.markdown)

    assert backend.get(f'/sessions/{session}/history', params={'user_id': 'another-user'}).status_code == 403
