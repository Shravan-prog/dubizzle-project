"""HTTP-only client. Run: uv run streamlit run app.py."""
import os
import re
from uuid import uuid4
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title='Dubizzle Cars Assistant', page_icon='🚗', layout='wide')
BASE=os.getenv('BACKEND_URL','http://127.0.0.1:8000').rstrip('/')

def api(method,path,**kwargs):
    try:
        response=httpx.request(method,BASE+path,timeout=45,**kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 503:
            st.error('The AI service is temporarily unavailable. Please try again in a moment.')
        else:
            st.error(f'Backend returned {exc.response.status_code}: {exc.response.text}')
    except httpx.RequestError:
        st.error('Backend unavailable. Start FastAPI and check BACKEND_URL.')
    return None

st.title('Find your next car')
st.caption('Explore dubizzle inventory, compare listings and arrange eligible viewings. Prices are in AED.')
def valid_id(value):
    return bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value))


def set_session(user, session_id):
    st.session_state.active_user = user
    st.session_state.session_id = session_id
    st.session_state.messages = []
    st.query_params['user'] = user
    st.query_params['session'] = session_id


with st.sidebar:
    st.header('Your session')
    url_user = st.query_params.get('user', '')
    url_session = st.query_params.get('session', '')
    user=st.text_input('User ID',value=url_user if valid_id(url_user) else 'demo-user')
    name=st.text_input('Name',value='')
    if not valid_id(user):
        st.error('Use 1–100 letters, numbers, underscores or hyphens for the user ID.')
        st.stop()
    if 'session_id' not in st.session_state or 'active_user' not in st.session_state:
        resume = user == url_user and valid_id(url_session)
        set_session(user, url_session if resume else str(uuid4()))
        st.session_state.restore_history = resume
    elif st.session_state.active_user != user:
        set_session(user, str(uuid4()))
        st.session_state.restore_history = False
    elif (url_user, url_session) != (user, st.session_state.session_id):
        st.query_params['user'] = user
        st.query_params['session'] = st.session_state.session_id
    if st.session_state.get('restore_history'):
        history = api('GET', f'/sessions/{st.session_state.session_id}/history', params={'user_id': user})
        if history is not None:
            st.session_state.messages = history['messages']
            st.session_state.restore_history = False
    if st.button('Start New Session (Test Long-Term Memory)'):
        result=api('POST','/sessions/reset',json={'user_id':user})
        if result:
            set_session(user, result['session_id'])
            st.session_state.restore_history = False
            greeting=api('POST','/chat',json={'user_id':user,'session_id':result['session_id'],'message':'Hello'})
            if greeting: st.session_state.messages.append({'role':'assistant',**greeting})
    st.caption('Session: '+st.session_state.session_id)

for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message.get('reply',message.get('content','')))
        if message.get('tool_calls'):
            with st.expander('Tool trace'): st.json(message['tool_calls'])

if prompt:=st.chat_input('Ask about a make, budget, mileage or viewing'):
    sent=(f'My name is {name}. ' if name and not st.session_state.messages else '')+prompt
    st.session_state.messages.append({'role':'user','content':prompt})
    with st.chat_message('user'): st.markdown(prompt)
    with st.spinner('Checking inventory…'):
        result=api('POST','/chat',json={'user_id':user,'session_id':st.session_state.session_id,'message':sent})
    if result:
        st.session_state.messages.append({'role':'assistant',**result})
        st.rerun()

with st.sidebar:
    if st.button('Refresh inspectors'): st.rerun()
    with st.expander('Long-term memory',expanded=True):
        profile=api('GET',f'/users/{user}/memory')
        if profile is not None: st.json(profile)
    with st.expander('Recorded leads'):
        leads=api('GET','/leads',params={'user_id':user})
        if leads is not None: st.dataframe(leads['items'])
    with st.expander('Inventory inspection'):
        inventory=api('GET','/inventory',params={'limit':10})
        if inventory is not None: st.dataframe(inventory['items'])
