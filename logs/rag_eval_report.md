# Inventory evaluation

The 17 labeled cases exercise the supplied 100-row inventory through FastAPI with isolated SQLite and CSV state. Checks include returned IDs, wording, preference recall, guardrails and lead recording. Live runs can use deterministic replies for direct facts or when model narration is rejected.

| Recorded run | Original result |
| --- | --- |
| [Initial scripted run](rag_eval_scripted.json) | 16/17 |
| [Initial live Gemini run](rag_eval_live.json) | 16/17 |
| [Scripted retest](rag_eval_scripted_retest.json) | 17/17 |
| [Six-case live Gemini run](gemini_rag_results.json) | 4/6 |

The latest scripted rerun passed **17/17**, including **S03**. The scripted planner omitted sorting for “lowest listed price.” The backend applied ascending price order and returned CAR-060 at AED 35,000, the lowest indexed asking price. The table preserves the historical scores. The [expanded report](rag_eval_expanded_report.md) lists the separate expanded runs.

The current inventory contains 10 listings with explicit Dubizzle management evidence. The [live README demo](../README.md#live-conversation-on-the-supplied-inventory) shows the explanation for an unconfirmed Honda and a satellite-dish query returning no listing cards.

```bash
uv run python scripts/evaluate_rag.py
uv run python scripts/evaluate_rag.py --live
```
