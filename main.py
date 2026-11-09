"""Run with uv run uvicorn main:app --reload."""
import os
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from src.schemas import ChatRequest, ChatResponse, ResetRequest, Search

# This local assessment uses .env as its explicit runtime configuration.
load_dotenv(override=True)

def create_app(data_dir=None, completion=None, narrator=None):
    from src.retrieval import Inventory
    from src.memory import Memory
    from src.leads import Leads
    from src.agent import Agent
    root = Path(data_dir or os.getenv('DATA_DIR', 'data'))
    root.mkdir(parents=True, exist_ok=True)
    inventory = Inventory(root / 'cars.csv')
    memory = Memory(root / 'memory.db')
    leads = Leads(root / 'leads.csv', inventory)
    agent = Agent(inventory, memory, leads, completion=completion, narrator=narrator)
    api = FastAPI(title='Dubizzle Cars Assistant', version='1.0.0')

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={'error': {'code': 'validation_error', 'message': 'Invalid request', 'details': [{'location': list(e['loc']), 'message': e['msg']} for e in exc.errors()]}})

    @api.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'error': {'code': str(exc.status_code), 'message': str(exc.detail)}})

    @api.get('/health')
    def health():
        return {'status': 'ok', 'inventory_count': len(inventory.frame)}

    @api.post('/chat', response_model=ChatResponse)
    def chat(body: ChatRequest):
        try:
            return agent.chat(body)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @api.get('/inventory')
    def get_inventory(filters: Search = Query()):
        return inventory.search(filters)

    @api.get('/users/{user_id}/memory')
    def get_memory(user_id: str):
        return memory.profile(user_id)

    @api.get('/leads')
    def get_leads(user_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        rows = [r for r in leads.rows() if r['user_id'] == user_id]
        return {'items': rows[offset:offset+limit], 'total': len(rows)}

    @api.post('/sessions/reset')
    def reset(body: ResetRequest):
        session_id = body.session_id or str(uuid4())
        try:
            memory.reset(body.user_id, session_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        return {'session_id': session_id, 'user_id': body.user_id, 'active_preferences': memory.profile(body.user_id)}

    return api

# A factory supports isolated tests and demonstration databases.
if Path(os.getenv('DATA_DIR', 'data'), 'cars.csv').exists():
    app = create_app()
