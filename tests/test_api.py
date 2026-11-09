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
