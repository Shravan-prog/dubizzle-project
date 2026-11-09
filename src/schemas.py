from typing import Annotated, Any, Literal
import re
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Identifier = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,100}$')]

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ChatRequest(Contract):
    user_id: Identifier
    session_id: Identifier
    message: Text

class ChatResponse(Contract):
    reply: str
    referenced_cars: list[dict[str, Any]]
    active_preferences: dict[str, Any]
    tool_calls: list[dict[str, Any]]

class ResetRequest(Contract):
    user_id: Identifier
    session_id: Identifier | None = None

class Search(Contract):
    query: str = ''
    make: str | None = None
    model: str | None = None
    year_min: int | None = Field(None, ge=1900, le=2100)
    year_max: int | None = Field(None, ge=1900, le=2100)
    price_min: float | None = Field(None, ge=0)
    price_max: float | None = Field(None, ge=0)
    max_mileage_km: float | None = Field(None, ge=0)
    body_type: str | None = None
    color: str | None = None
    warranty: bool | None = None
    dubizzle_managed: bool | None = None
    sort_by: Literal['relevance', 'price', 'mileage_km', 'year'] | None = None
    sort_order: Literal['asc', 'desc'] = 'asc'
    offset: int = Field(0, ge=0)
    limit: int = Field(10, ge=1, le=100)

    @model_validator(mode='after')
    def ranges(self):
        for low, high in [('year_min', 'year_max'), ('price_min', 'price_max')]:
            if getattr(self, low) is not None and getattr(self, high) is not None:
                if getattr(self, low) > getattr(self, high):
                    raise ValueError(f'{low} must not exceed {high}')
        return self

class CarDetails(Contract):
    car_id: str | None = None
    position: int | None = Field(None, ge=1)
    make: str | None = None

class Preferences(Contract):
    name: str | None = Field(None, max_length=100)
    budget_min: float | None = Field(None, ge=0)
    budget_max: float | None = Field(None, ge=0)
    preferred_makes: list[str] | None = None
    preferred_body_types: list[str] | None = None
    preferred_colors: list[str] | None = None
    liked_car_ids: list[str] | None = None
    past_inquiries_summary: str | None = Field(None, max_length=1000)

class Booking(Contract):
    user_id: Identifier
    user_name: Text
    contact: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
    car_id: str
    requested_day: str = Field(description='ISO date YYYY-MM-DD, or English weekday for next occurrence in Dubai')
    requested_hour_24: int = Field(ge=0, le=23)
    budget_max: float = Field(gt=0)
    notes: str = Field('', max_length=2000)

    @model_validator(mode='after')
    def check_contact(self):
        if not valid_contact(self.contact):
            raise ValueError('Provide a valid email address or phone number, not a date')
        return self

def valid_contact(value):
    if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): return True
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): return False
    return bool(re.fullmatch(r'\+?[\d ()-]+',value)) and 7 <= len(re.sub(r'\D','',value)) <= 15
