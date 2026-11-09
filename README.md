# Dubizzle Cars AI Assistant

Local take-home implementation: FastAPI backend, HTTP-only Streamlit client, hybrid retrieval, SQLite memory and CSV viewing leads.

## Quick start

Requires Python 3.11–3.13 and uv; tested on macOS. CSV locking uses POSIX fcntl (macOS/Linux).

```bash
# After extracting the submission ZIP:
cd dubizzle-cars-assistant
uv sync --locked
cp .env.example .env
# Set GEMINI_API_KEY in .env; never commit it.
uv run python scripts/prepare_data.py
uv run uvicorn main:app --host 127.0.0.1 --port 8000
# In a second terminal, from the same directory:
uv run streamlit run app.py
```

Open http://localhost:8501. API documentation: http://127.0.0.1:8000/docs.
Default model: `gemini/gemini-3.5-flash-lite`; change LLM_MODEL for another tool-capable model.
For OpenAI use an `openai/...` model and OPENAI_API_KEY. Provider availability and free-tier quotas vary; no live paid calls were made during verification.
Configuration follows [LiteLLM Gemini documentation](https://docs.litellm.ai/docs/providers/gemini) and [native function calling](https://docs.litellm.ai/docs/completion/function_call).

## Architecture

Streamlit provides chat and inspectors without reading backend files: every operation uses HTTP through httpx. FastAPI owns inventory, profiles and lead writes. LiteLLM provides native tool calling without a separate orchestration framework. Structured pandas filters enforce explicit constraints and sorting, while BM25 ranks descriptions and trims. SQLite stores session histories and user profiles; CSV makes booked leads easy to inspect. Pydantic validates requests and tool arguments. The model first selects a tool; after the backend executes it, a second grounded model call receives only the verified result and phrases a natural response. Structured listing cards appear for search results, while mileage, warranty, price and colour follow-ups receive direct answers. A post-check rejects new numeric facts or unknown listing IDs, and any model failure falls back to a human-readable deterministic response rather than exposing internal JSON or repeating the full card. Temporary planning failures are retried; common inventory searches have a deterministic fallback after retries are exhausted.

## Design and future work

The supplied workbook contains 100 rows with seven populated source columns. Conversion preserves these and adds stable IDs and nullable fields. Only facts stated in the listing text are extracted, including mileage, price, body type, color, transmission, fuel and warranty. Unknown prices fail price filters; unknown management status cannot authorize a viewing. Seller descriptions remain untrusted. Booking slots use Dubai time, Monday–Saturday inclusive, 08:00–20:00 inclusive; Sunday, past, out-of-hours and occupied slots are rejected. A process lock serializes chats; a file lock protects booking validation and CSV writes.

This is a local demonstration, not a public deployment. Before production, add authentication/authorization (user IDs currently identify, not authenticate), separate private lead data from debugging output, distributed session locking, booking confirmation/idempotency, stronger semantic guardrails, broader adversarial/model evaluations and monitoring. The current single-pass tool planner uses generic clarification when no tool is selected; multi-step tool-result reasoning and better dialogue phrasing are future improvements. Keyword guards are not a complete security boundary. Do not expose the local API publicly.

## API

- POST /chat: user_id, session_id, message → reply, referenced_cars, active_preferences, tool_calls.
- GET /inventory: structured Search filters, query, offset, limit.
- GET /users/{user_id}/memory: recalled profile.
- POST /sessions/reset: user_id and optional session_id. Omit session_id for a fresh session preserving long-term memory.
- GET /leads?user_id=...: user-filtered lead inspector with offset/limit.
- GET /health: health and inventory count.

POST requests are not generally safe to retry automatically. Duplicate booking slots are rejected, not replayed.
SQLite and leads are created in DATA_DIR (default data). Source data is not modified by chats.
Qualified inquiries are saved when name, valid contact and budget are available, even without a successful booking. In leads.csv, empty slot fields mean an inquiry, not a reservation; successful booking fills the slot fields. Notes preserve the user's stated needs. Slots begin on exact hours: a request for 10:30 prompts clarification rather than silently changing it to 10:00. Budget shorthand such as AED 80k is supported; negative preference statements prompt clarification before changing memory.
Name is included in the first submitted chat message. Changing User ID starts a separate local chat.

## Verification

```bash
uv run pytest -q
uv run python scripts/demo_logs.py
```

Verified: 31 tests passed and two deterministic HTTP conversations completed after the parsing, lead-recording and grounded-response changes. Live API checks confirmed that mileage, warranty, price and colour questions return direct field answers without another model call or a repeated listing card. Comparison requests enforce the requested result count, collapse duplicate vehicle options, explain verified tradeoffs and end with a grounded recommendation. A semantic comparison guard rejects unsupported adjectives and relative price, mileage or year claims that contradict the structured rows. A field question without prior car context asks the user to search or provide a listing ID, and provider outages display a friendly UI error rather than backend JSON. Gemini inventory and booking replies expose `compose_grounded_response` as a model-backed stage in the tool trace. Regression coverage also includes natural responses grounded in tool results, budget shorthand, negative preferences, contact validation, hourly slots and inquiries for unmanaged cars. Common inventory searches use a deterministic fallback if transient provider failures remain after retries.
The deterministic demo replaces only the LLM boundary and uses synthetic inventory in a temporary directory; it does not alter supplied inventory or personal leads. Full transcripts: [logs/demo_transcripts.md](logs/demo_transcripts.md). The supplied listings contain no explicit dubizzle-managed flag, so live bookings are correctly rejected; successful booking persistence is demonstrated with a clearly labelled synthetic managed-car fixture.

## Embedded demonstration excerpts

```text
Conversation 1 — synthetic fixture, real HTTP tools and persistence
User: Show Honda cars
Assistant: Found 1 matching listings (prices in AED).
[DEMO-H1] Honda CR-V Sport, 2022; price: 60000; mileage_km: 30000;
body_type: SUV; color: white; warranty: True; dubizzle_managed: True
User: What is the mileage on that first Honda?
Assistant: [DEMO-H1] ... mileage_km: 30000 ...
User: Does it have warranty?
Assistant: [DEMO-H1] ... warranty: True ...
User: Remember I like DEMO-H1 and white SUVs under AED 65000.
Assistant: Saved your preferences ...
User: Book DEMO-H1 on 2099-01-05 at 10:00.
      Name Demo User, contact demo@example.com, budget AED 65000.
Assistant: Viewing booked: {"ok": true, ...}

Conversation 2 — same user, fresh session
User: Hello
Assistant: Welcome back! Your saved preferences:
name: Demo User; budget_max: 65000; preferred_body_types: ["SUV"];
preferred_colors: ["white"]; liked_car_ids: ["DEMO-H1"].
```

Excerpts are shortened for readability; complete generated output is in the linked transcript.

