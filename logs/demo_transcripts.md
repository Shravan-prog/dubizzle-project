# Deterministic demonstration transcripts

Synthetic inventory and scripted LLM responses. Real FastAPI HTTP contracts, retrieval, SQLite and CSV are exercised. This is not a live Gemini evaluation.

## Conversation 1: exploration and booking

**User:** Show Honda cars

**Assistant:** I found a Honda that matches your search. Here are the verified listing details.

### Honda CR-V — 2022
**Trim:** Sport  ·  **Listing ID:** `DEMO-H1`

| Price | Mileage | Body type | Color | Warranty |
|---|---|---|---|---|
| 60000 AED | 30000 km | SUV | white | True |

**User:** What is the mileage on that first Honda?

**Assistant:** The listed mileage for the 2022 Honda CR-V is 30,000 km.

**User:** Does it have warranty?

**Assistant:** The 2022 Honda CR-V has a listed warranty.

**User:** Remember I like DEMO-H1 and white SUVs under AED 65000. My name is Demo User.

**Assistant:** I’ll remember that you prefer white SUVs under AED 65000 and liked this Honda.

**User:** Book DEMO-H1 on 2099-01-05 at 10:00. Name Demo User, contact demo@example.com, budget AED 65000.

**Assistant:** Your viewing is booked for 2099-01-05 at 10:00 Dubai time.

## Conversation 2: returning user in a fresh session

**User:** Hello

**Assistant:** Welcome back, Demo User. I remember you prefer white SUVs under AED 65000 and liked DEMO-H1.
