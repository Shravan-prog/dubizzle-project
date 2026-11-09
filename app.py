"""HTTP-only client. Run: uv run streamlit run app.py."""
import os
from uuid import uuid4
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title='Dubizzle Cars Assistant', page_icon='🚗', layout='wide')
BASE=os.getenv('BACKEND_URL','http://127.0.0.1:8000').rstrip('/')
APP_VERSION='direct-field-followups-v1'

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
if st.session_state.get('app_version') != APP_VERSION:
    st.session_state.app_version=APP_VERSION
    st.session_state.session_id=str(uuid4())
    st.session_state.messages=[]
elif 'session_id' not in st.session_state:
    st.session_state.session_id=str(uuid4())
    st.session_state.messages=[]
with st.sidebar:
    st.header('Your session')
    user=st.text_input('User ID',value='demo-user')
    name=st.text_input('Name',value='')
    if st.session_state.get('active_user')!=user:
        st.session_state.active_user=user
        st.session_state.session_id=str(uuid4())
        st.session_state.messages=[]
    if st.button('Start New Session (Test Long-Term Memory)'):
        result=api('POST','/sessions/reset',json={'user_id':user})
        if result:
            st.session_state.session_id=result['session_id']
            st.session_state.messages=[]
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
