import pytest

def test_contract_rejects_blank_and_unknown_fields():
    from src.schemas import ChatRequest, Search
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(user_id='u', session_id='s', message=' ')
    with pytest.raises(ValidationError):
        Search(price_min=100, price_max=10)
    with pytest.raises(ValidationError):
        Search(invented=True)
