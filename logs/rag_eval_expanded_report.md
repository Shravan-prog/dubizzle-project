# Expanded Dubizzle RAG evaluation

The expanded suite combines the [original evaluation](../data/rag_eval_questions.json), [Gemini-specific questions](../data/gemini_rag_questions.json), and [14 additional scenarios](../data/rag_eval_extended.json). Each run uses the supplied inventory and isolated memory and leads.

| Recorded run | Original result |
| --- | --- |
| [First full live run](rag_eval_expanded_initial.json) | 35/37 |
| [Second full live run](rag_eval_expanded_final.json) | 35/37 |
| [Targeted live retest](rag_eval_targeted_retest.json) | 4/4 |
| [Scripted baseline](rag_eval_scripted_retest.json) | 17/17 |

The logs preserve each run's results and trace. The [live README demo](../README.md#live-conversation-on-the-supplied-inventory) shows behavior on the current inventory, including the booking eligibility explanation.

```bash
uv run python scripts/evaluate_rag.py --live \
  --dataset data/rag_eval_questions.json \
  --dataset data/gemini_rag_questions.json \
  --dataset data/rag_eval_extended.json
```
