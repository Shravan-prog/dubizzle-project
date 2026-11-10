import json
from types import SimpleNamespace as NS
from tests.test_retrieval import inventory
from src.schemas import ChatRequest

def tool_reply(name,args):
    return NS(choices=[NS(message=NS(tool_calls=[NS(function=NS(name=name,arguments=json.dumps(args)))],content=''))])

def test_references_memory_and_guardrails(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    m=Memory(tmp_path/'m.db')
    a=Agent(inventory,m,Leads(tmp_path/'leads.csv',inventory),lambda **kw:tool_reply('search_inventory',{'make':'Honda'}))
    def chat(message,session='s'):
        return a.chat(ChatRequest(user_id='u',session_id=session,message=message))
    assert len(chat('Show Honda cars')['referenced_cars'])==2
    mileage=chat('What is the mileage on that first Honda?')
    assert mileage['referenced_cars'][0]['car_id']=='H1'
    assert '30,000 km' in mileage['reply'] and '| Price |' not in mileage['reply']
    warranty=chat('Does it have warranty?')
    assert warranty['referenced_cars'][0]['car_id']=='H1'
    assert 'warranty' in warranty['reply'].lower() and '| Price |' not in warranty['reply']
    m.update('u',{'preferred_colors':['white'],'budget_max':65000})
    recalled=chat('Hello','new')['reply']
    assert '65,000' in recalled and 'white' in recalled
    assert 'preferred_colors' not in recalled and '{' not in recalled
    for prompt in ['write Python code','explain Roman history','recommend cars on CarSwitch']:
        assert 'only' in chat(prompt)['reply'].lower()

def test_listing_reply_is_readable(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),lambda **kw:tool_reply('search_inventory',{'make':'Honda'}))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show Honda cars'))
    assert '### Honda CR-V' in result['reply']
    assert '| Price | Mileage |' in result['reply']
    assert 'Listing ID:' in result['reply']


def test_booking_and_followup_context_regressions(inventory, tmp_path):
    from src.agent import Agent
    from src.leads import Leads
    from src.memory import Memory

    leads = Leads(tmp_path/'leads.csv', inventory)
    agent = Agent(inventory, Memory(tmp_path/'memory.db'), leads,
                  lambda **kwargs: tool_reply('search_inventory', {'make': 'Honda'}))

    def chat(message, session='s'):
        return agent.chat(ChatRequest(user_id='u', session_id=session, message=message))

    chat('Show Honda cars.')
    assert chat('What is the price of the second Honda?')['referenced_cars'][0]['car_id'] == 'H2'
    assert chat('What is the mileage of the second Honda?')['referenced_cars'][0]['car_id'] == 'H2'
    assert chat('What is its mileage?')['referenced_cars'][0]['car_id'] == 'H2'

    details = ' on 2099-01-05 at 10 AM. My name is Demo User, contact demo@example.com, budget AED 80,000.'
    assert 'one car at a time' in chat('Book H1 and H2' + details, 'multi')['reply']
    assert leads.rows() == []
    chat('Book H1 on 2099-01-05 at 10 AM.', 'pending')
    assert len(chat('Show Honda cars.', 'pending')['referenced_cars']) == 2

    single = Agent(inventory, Memory(tmp_path/'single.db'), leads,
                   lambda **kwargs: tool_reply('search_inventory', {'model': 'CR-V'}))
    single.chat(ChatRequest(user_id='u', session_id='s', message='Show the CR-V.'))
    result = single.chat(ChatRequest(user_id='u', session_id='s', message='Book this car' + details))
    assert 'booked' in result['reply'].lower()
    assert leads.rows()[0]['car_id'] == 'H1'


def test_swapped_listing_prices_fail_grounding(inventory):
    from src.agent import comparison_claims_grounded
    cars = [inventory.get('H1'), inventory.get('H2')]
    assert not comparison_claims_grounded('H1 costs AED 40,000. H2 costs AED 60,000.', cars)
    assert comparison_claims_grounded('H1 costs AED 60,000. H2 costs AED 40,000.', cars)
    assert not comparison_claims_grounded('H2 costs AED 20,000 more than H1.', cars)
    assert comparison_claims_grounded('H1 costs AED 20,000 more than H2.', cars)
    assert comparison_claims_grounded('H1 is AED 20,000 higher than H2.', cars)
    assert not comparison_claims_grounded('H2 is AED 20,000 higher than H1.', cars)
    assert not comparison_claims_grounded('H2 has a confirmed warranty.', cars)
    assert not comparison_claims_grounded('**H2**\n**Warranty:** Yes', cars)


def test_audit_booking_intent_and_search_recall(inventory, tmp_path):
    from src.agent import Agent
    from src.leads import Leads
    from src.memory import Memory

    leads = Leads(tmp_path/'leads.csv', inventory)
    agent = Agent(inventory, Memory(tmp_path/'memory.db'), leads,
                  lambda **kwargs: tool_reply('search_inventory', {'make': 'Honda', 'price_max': 60000}))

    def chat(message, session='s'):
        return agent.chat(ChatRequest(user_id='u', session_id=session, message=message))

    details = ' on 2099-01-05 at 10 AM. My name is Demo User, contact demo@example.com, budget AED 80,000.'
    assert 'booked' not in chat('Do not book H1' + details)['reply'].lower()
    assert not leads.rows()
    assert '08:00' in chat('What viewing slots are available?')['reply']
    chat('Book H2 on 2099-01-05 at 11 AM. My name is Demo User, budget AED 80,000.', 'switch')
    switched = chat('Book H1 instead. Contact demo@example.com.', 'switch')['reply']
    assert 'date' in switched and 'time' in switched
    assert not leads.rows()
    assert 'one car at a time' in chat('Book the first and second car' + details)['reply']
    assert not leads.rows()
    assert chat('Show Hondas strictly under AED 60,000.')['referenced_cars'][0]['car_id'] == 'H2'
    assert 'Honda' in chat('What cars was I looking for last time?', 'fresh')['reply']
    assert 'only help' not in chat('What is the service history of H1?')['reply']


def test_mandatory_feature_is_not_only_a_ranking_hint(inventory):
    from src.agent import enforce_search_semantics
    from src.schemas import Search
    request = enforce_search_semantics(Search(make='Honda', query='satellite dish'),
                                       'Find a Honda with a roof-mounted satellite dish.')
    assert inventory.search(request)['items'] == []


def test_comparison_narration_accepts_verified_price_gap(inventory, tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads

    def narrator(**kwargs):
        payload = json.loads(kwargs['messages'][-1]['content'])
        assert payload['verified_data']['differences']['price'] == {
            'difference': '20000', 'higher_listing_id': 'H1', 'lower_listing_id': 'H2',
        }
        return NS(choices=[NS(message=NS(content='H1 costs AED 60,000.00. I recommend H1 for its listed warranty. It costs AED 20,000 more than H2.'))])

    agent = Agent(inventory, Memory(tmp_path/'memory.db'), Leads(tmp_path/'leads.csv', inventory),
                  lambda **kwargs: tool_reply('search_inventory', {'make': 'Honda'}), narrator)
    result = agent.chat(ChatRequest(user_id='u', session_id='s', message='Compare the Hondas and recommend one with a warranty.'))
    assert 'It costs AED 20,000 more than H2.' in result['reply']
    assert result['tool_calls'][-1]['source'] == 'model'


def test_returning_greeting_recalls_profile_without_answering_search(inventory, tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads

    memory = Memory(tmp_path/'memory.db')
    memory.update('u', {'name': 'Demo', 'budget_max': 65000})
    narrated = []

    def narrator(**kwargs):
        event = json.loads(kwargs['messages'][-1]['content'])['event']
        narrated.append(event)
        content = 'I cannot access inventory.' if event == 'returning_greeting' else 'Here are the Honda listings.'
        return NS(choices=[NS(message=NS(content=content))])

    agent = Agent(inventory, memory, Leads(tmp_path/'leads.csv', inventory),
                  lambda **kwargs: tool_reply('search_inventory', {'make': 'Honda'}), narrator)
    result = agent.chat(ChatRequest(user_id='u', session_id='fresh', message='Show me Hondas.'))
    assert 'Welcome back, Demo' in result['reply']
    assert '65,000' in result['reply']
    assert 'Here are the Honda listings' in result['reply']
    assert 'cannot access inventory' not in result['reply']
    assert narrated == ['inventory_search']


def test_recall_uses_saved_turns_without_replaying_inventory(inventory, tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads

    memory = Memory(tmp_path / 'memory.db')
    calls = []

    def planner(**kwargs):
        calls.append(kwargs['messages'][-1]['content'])
        return tool_reply('search_inventory', {'make': 'Honda'})

    agent = Agent(inventory, memory, Leads(tmp_path / 'leads.csv', inventory), planner)

    def chat(message, session='original'):
        return agent.chat(ChatRequest(user_id='u', session_id=session, message=message))

    chat('Show Honda cars')
    for message, expected in [
        ('What did I ask earlier?', 'Show Honda cars'),
        ('Which cars did you show me earlier?', 'Honda CR-V (H1)'),
        ('What did I ask before?', 'Show Honda cars'),
        ('What did you say earlier?', 'Found 2 matching listings'),
        ('What was the mileage again?', '30,000 km'),
    ]:
        result = chat(message)
        assert expected in result['reply']
        assert '| Price |' not in result['reply']
        if 'again' not in message:
            assert not result['tool_calls']
    assert 'yet' in chat('What did I ask earlier?', 'fresh')['reply']
    assert calls == ['Show Honda cars']

def test_empty_search_explains_next_step(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),lambda **kw:tool_reply('search_inventory',{'make':'Honda','year_min':2025}))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show Honda cars from 2022 or newer'))
    assert 'No confirmed matching cars' in result['reply']
    assert 'Try removing one filter' in result['reply']

def test_booking_requests_missing_fields_and_rejects_invalid_slot(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    m=Memory(tmp_path/'m.db')
    m.record('u','s','Show cars','Here they are',['H1'])
    def unexpected(**kwargs):
        raise AssertionError('Incomplete booking must not call the model')
    a=Agent(inventory,m,Leads(tmp_path/'leads.csv',inventory),unexpected)
    reply=a.chat(ChatRequest(user_id='u',session_id='s',message='I want to book a viewing for the first car.'))['reply']
    assert 'name' in reply.lower() and 'contact' in reply.lower() and 'date' in reply.lower()
    invalid=a.chat(ChatRequest(user_id='u',session_id='other',message='Book a viewing on Sunday at 9 PM.'))['reply']
    assert 'Sunday' in invalid and '08:00–20:00' in invalid

def test_search_does_not_silently_save_preferences(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    m=Memory(tmp_path/'m.db')
    a=Agent(inventory,m,Leads(tmp_path/'leads.csv',inventory),lambda **kw:tool_reply('update_user_preferences',{'preferred_makes':['Honda']}))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show Honda cars'))
    assert m.profile('u')['preferred_makes'] is None
    assert 'only save preferences' in result['reply'].lower()

def test_transient_model_failures_are_retried(inventory,tmp_path,monkeypatch):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    attempts={'count':0}
    def flaky(**kwargs):
        attempts['count']+=1
        if attempts['count']<3: raise RuntimeError('503 UNAVAILABLE')
        return tool_reply('search_inventory',{'make':'Honda'})
    monkeypatch.setattr('src.agent.time.sleep',lambda seconds: None)
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),flaky)
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show Honda cars'))
    assert attempts['count']==3 and len(result['referenced_cars'])==2

def test_exhausted_retries_fall_back_for_inventory_queries(inventory,tmp_path,monkeypatch):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    monkeypatch.setattr('src.agent.time.sleep',lambda seconds: None)
    def unavailable(**kwargs): raise RuntimeError('503 UNAVAILABLE')
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),unavailable)
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show Honda cars'))
    assert [car['car_id'] for car in result['referenced_cars']]==['H1','H2']
    assert result['tool_calls'][0]['source']=='deterministic_fallback'

def test_lowest_mileage_forces_one_sorted_result(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),lambda **kw:tool_reply('search_inventory',{'limit':5}))
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Which car has the lowest mileage?'))
    assert [car['car_id'] for car in result['referenced_cars']]==['H1']

def test_explicit_preferences_are_saved_without_model_planning(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    m=Memory(tmp_path/'m.db')
    def unexpected(**kwargs): raise AssertionError('Explicit preferences must not depend on the model')
    a=Agent(inventory,m,Leads(tmp_path/'leads.csv',inventory),unexpected)
    result=a.chat(ChatRequest(user_id='u',session_id='one',message='Remember that I prefer white SUVs under AED 80000.'))
    assert result['active_preferences']['preferred_colors']==['white']
    assert result['active_preferences']['preferred_body_types']==['SUV']
    assert result['active_preferences']['budget_max']==80000
    recalled=a.chat(ChatRequest(user_id='u',session_id='two',message='Hello'))
    assert 'white' in recalled['reply'] and '80,000' in recalled['reply']

def test_booking_details_can_be_collected_across_turns(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    m=Memory(tmp_path/'m.db'); leads=Leads(tmp_path/'leads.csv',inventory)
    def unexpected(**kwargs): raise AssertionError('Booking collection must not depend on the model')
    a=Agent(inventory,m,leads,unexpected)
    m.record('u','s','Show cars','Here they are',['H1'])
    first=a.chat(ChatRequest(user_id='u',session_id='s',message='I want to book a viewing for the first car.'))
    assert 'contact' in first['reply'].lower()
    second=a.chat(ChatRequest(user_id='u',session_id='s',message='My name is User, contact user@example.com, 2099-01-05 at 10 AM, budget AED 65000.'))
    assert 'booked' in second['reply'].lower()
    assert len(leads.rows())==1

def test_grounded_narrator_turns_tool_results_into_natural_replies(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    narration_inputs=[]
    def narrator(**kwargs):
        narration_inputs.append(kwargs['messages'][-1]['content'])
        return NS(choices=[NS(message=NS(content='I found two Hondas that match. The first is a 2022 CR-V with 30,000 km.'))])
    a=Agent(
        inventory,
        Memory(tmp_path/'m.db'),
        Leads(tmp_path/'leads.csv',inventory),
        completion=lambda **kw:tool_reply('search_inventory',{'make':'Honda'}),
        narrator=narrator,
    )
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Show me Honda cars'))
    assert result['reply'].startswith('I found two Hondas that match.')
    assert '### Honda CR-V' in result['reply']
    assert 'H1' in narration_inputs[0] and 'H2' in narration_inputs[0]

def test_grounded_narrator_makes_booking_failure_readable(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    def narrator(**kwargs):
        prompt=kwargs['messages'][-1]['content']
        assert 'confirmed dubizzle-managed listing' in prompt
        return NS(choices=[NS(message=NS(content="I couldn't book that viewing because the listing is not confirmed as dubizzle-managed. I saved your inquiry and budget."))])
    a=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),completion=lambda **kw:pytest.fail('Planner should not run'),narrator=narrator)
    result=a.chat(ChatRequest(user_id='u',session_id='s',message='Book H2 on 2099-01-05 at 10 AM. My name is User, contact user@example.com, budget AED 80k.'))
    assert result['reply'].startswith("I couldn't book")
    assert '{"ok"' not in result['reply']

def test_specific_car_followups_answer_directly_without_narrator(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    memory=Memory(tmp_path/'m.db')
    memory.record('u','s','Show Honda cars','Here are the cars',['H1'])
    def unexpected(**kwargs):
        raise AssertionError('A known field follow-up must not need another model call')
    agent=Agent(inventory,memory,Leads(tmp_path/'leads.csv',inventory),completion=unexpected,narrator=unexpected)
    mileage=agent.chat(ChatRequest(user_id='u',session_id='s',message='What is its mileage?'))['reply']
    warranty=agent.chat(ChatRequest(user_id='u',session_id='s',message='Does it have a warranty?'))['reply']
    colour=agent.chat(ChatRequest(user_id='u',session_id='s',message='What colour is it?'))['reply']
    assert mileage=='The listed mileage for the 2022 Honda CR-V is 30,000 km.'
    assert warranty=='The 2022 Honda CR-V has a listed warranty.'
    assert colour=='The listed colour of the 2022 Honda CR-V is white.'
    assert '| Price |' not in mileage+warranty+colour

def test_contextless_pronoun_asks_which_car_without_model(inventory,tmp_path):
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    def unexpected(**kwargs):
        raise AssertionError('Missing car context must be clarified without a model call')
    agent=Agent(inventory,Memory(tmp_path/'m.db'),Leads(tmp_path/'leads.csv',inventory),completion=unexpected,narrator=unexpected)
    result=agent.chat(ChatRequest(user_id='u',session_id='new',message='What is its mileage?'))
    assert result['reply']=='Which car do you mean? Search the inventory first or provide a listing ID.'
    assert result['tool_calls']==[]

def test_comparison_request_recommends_and_removes_duplicate_options(tmp_path):
    import pandas as pd
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    from src.retrieval import Inventory

    rows=[
        dict(car_id='A1',make='Haval',model='H9',trim='4WD',year=2026,price=115750,mileage_km=18,body_type='SUV',color=None,warranty=True,dubizzle_managed=None,description='Family SUV'),
        dict(car_id='A2',make='Haval',model='H9',trim='4WD',year=2026,price=115750,mileage_km=18,body_type='SUV',color=None,warranty=True,dubizzle_managed=None,description='Family SUV duplicate listing'),
        dict(car_id='B1',make='Toyota',model='RAV4',trim='GX',year=2025,price=105000,mileage_km=12000,body_type='SUV',color='white',warranty=True,dubizzle_managed=None,description='Family SUV'),
        dict(car_id='C1',make='Honda',model='CR-V',trim='EX',year=2024,price=95000,mileage_km=20000,body_type='SUV',color='silver',warranty=False,dubizzle_managed=None,description='Family SUV'),
        dict(car_id='D1',make='Nissan',model='X-Trail',trim='S',year=2023,price=90000,mileage_km=25000,body_type='SUV',color='black',warranty=False,dubizzle_managed=None,description='Family SUV'),
    ]
    path=tmp_path/'cars.csv'; pd.DataFrame(rows).to_csv(path,index=False)
    inventory=Inventory(path)

    def narrator(**kwargs):
        payload=json.loads(kwargs['messages'][-1]['content'])
        assert 'recommend' in payload['instruction'].lower()
        assert [car['car_id'] for car in payload['verified_data']['items']]==['A1','B1','C1']
        return NS(choices=[NS(message=NS(content='I recommend the 2025 Toyota RAV4 because it has a listed warranty and offers the best balance of price and mileage among these three options.'))])

    agent=Agent(
        inventory,
        Memory(tmp_path/'m.db'),
        Leads(tmp_path/'leads.csv',inventory),
        completion=lambda **kw:tool_reply('search_inventory',{'body_type':'SUV','sort_by':'year','sort_order':'desc','limit':10}),
        narrator=narrator,
    )
    result=agent.chat(ChatRequest(user_id='u',session_id='s',message='Compare the best three family SUVs and recommend one.'))
    assert 'I recommend the 2025 Toyota RAV4' in result['reply']
    assert [car['car_id'] for car in result['referenced_cars']]==['A1','B1','C1']
    assert result['reply'].count('### Haval H9')==1

def test_comparison_guard_rejects_contradictory_or_unsupported_claims(tmp_path):
    import pandas as pd
    from src.agent import Agent
    from src.memory import Memory
    from src.leads import Leads
    from src.retrieval import Inventory

    rows=[
        dict(car_id='H1',make='Haval',model='H9',trim='4WD',year=2026,price=115750,mileage_km=18,body_type='SUV',color=None,warranty=True,dubizzle_managed=None,description='Family SUV'),
        dict(car_id='A1',make='Audi',model='Q8',trim='S Line',year=2023,price=204999,mileage_km=89000,body_type='SUV',color=None,warranty=True,dubizzle_managed=None,description='Family SUV'),
        dict(car_id='T1',make='Toyota',model='RAV4',trim='GX',year=2025,price=150000,mileage_km=30000,body_type='SUV',color=None,warranty=True,dubizzle_managed=None,description='Family SUV'),
    ]
    path=tmp_path/'cars.csv'; pd.DataFrame(rows).to_csv(path,index=False)
    inventory=Inventory(path)

    def misleading_narrator(**kwargs):
        return NS(choices=[NS(message=NS(content='The Audi Q8 offers a powerful S Line trim with verified low pricing data. Recommendation: choose the Audi Q8.'))])

    agent=Agent(
        inventory,
        Memory(tmp_path/'m.db'),
        Leads(tmp_path/'leads.csv',inventory),
        completion=lambda **kw:tool_reply('search_inventory',{'body_type':'SUV','limit':3}),
        narrator=misleading_narrator,
    )
    result=agent.chat(ChatRequest(user_id='u',session_id='s',message='Compare these three family SUVs and recommend one.'))
    assert 'powerful' not in result['reply'].lower()
    assert 'low pricing data' not in result['reply'].lower()
    assert '**Recommendation:**' in result['reply']
    assert result['tool_calls'][-1]['source']=='deterministic_guardrail'
