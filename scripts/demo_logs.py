"""Deterministic integration demo: fake LLM boundary, real HTTP app/tools/storage."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from fastapi.testclient import TestClient
from main import create_app

def fake_completion(**kwargs):
    text=kwargs['messages'][-1]['content']
    if 'Remember' in text:
        name='update_user_preferences'; args={'name':'Demo User','budget_max':65000,'preferred_colors':['white'],'preferred_body_types':['SUV'],'liked_car_ids':['DEMO-H1']}
    elif 'Book' in text:
        name='book_viewing_and_qualify_lead'; args=dict(user_id='demo',user_name='Demo User',contact='demo@example.com',car_id='DEMO-H1',requested_day='2099-01-05',requested_hour_24=10,budget_max=65000,notes='Synthetic demonstration')
    else:
        name='search_inventory'; args={'make':'Honda'}
    return NS(choices=[NS(message=NS(tool_calls=[NS(function=NS(name=name,arguments=json.dumps(args)))],content=''))])

def fake_narrator(**kwargs):
    event=json.loads(kwargs['messages'][-1]['content'])['event']
    replies={
        'inventory_search':'I found a Honda that matches your search. Here are the verified listing details.',
        'car_details':'The first Honda has 30000 km on the odometer.',
        'preference_saved':'I’ll remember that you prefer white SUVs under AED 65000 and liked this Honda.',
        'booking':'Your viewing is booked for 2099-01-05 at 10:00 Dubai time.',
        'returning_greeting':'Welcome back, Demo User. I remember you prefer white SUVs under AED 65000 and liked DEMO-H1.',
    }
    return NS(choices=[NS(message=NS(content=replies.get(event,'How can I help with your car search?')))])

def run():
    lines=['# Deterministic demonstration transcripts','','Synthetic inventory and scripted LLM responses. Real FastAPI HTTP contracts, retrieval, SQLite and CSV are exercised. This is not a live Gemini evaluation.','','## Conversation 1: exploration and booking','']
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        pd.DataFrame([dict(car_id='DEMO-H1',make='Honda',model='CR-V',trim='Sport',year=2022,price=60000,mileage_km=30000,body_type='SUV',color='white',transmission='automatic',fuel_type='petrol',warranty=True,dubizzle_managed=True,description='Synthetic family SUV')]).to_csv(root/'cars.csv',index=False)
        client=TestClient(create_app(root,fake_completion,fake_narrator))
        def turn(text,session):
            response=client.post('/chat',json={'user_id':'demo','session_id':session,'message':text})
            response.raise_for_status()
            lines.extend(['**User:** '+text,'','**Assistant:** '+response.json()['reply'],''])
            return response.json()
        turn('Show Honda cars','one')
        turn('What is the mileage on that first Honda?','one')
        turn('Does it have warranty?','one')
        turn('Remember I like DEMO-H1 and white SUVs under AED 65000. My name is Demo User.','one')
        turn('Book DEMO-H1 on 2099-01-05 at 10:00. Name Demo User, contact demo@example.com, budget AED 65000.','one')
        assert client.get('/leads',params={'user_id':'demo'}).json()['total']==1
        lines.extend(['## Conversation 2: returning user in a fresh session',''])
        client.post('/sessions/reset',json={'user_id':'demo','session_id':'two'}).raise_for_status()
        result=turn('Hello','two')
        assert result['active_preferences']['liked_car_ids']==['DEMO-H1']
    output=Path(__file__).resolve().parents[1]/'logs/demo_transcripts.md'
    output.parent.mkdir(exist_ok=True)
    output.write_text('\n'.join(lines))
    print('PASS: two HTTP conversations, persisted booking and cross-session recall; '+str(output))

if __name__=='__main__': run()
