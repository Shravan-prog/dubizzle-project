# Expanded Dubizzle RAG evaluation

The suite contains 37 questions across the [original evaluation](../data/rag_eval_questions.json), [Gemini-specific evaluation](../data/gemini_rag_questions.json), and [14 added scenarios](../data/rag_eval_extended.json). It uses the supplied 100-car inventory through the FastAPI chat endpoint, with temporary memory and lead storage. Cases specify expected listing IDs, selected facts or wording, and model traces where Gemini is required.

| Verification | Result |
| --- | --- |
| [First full live run](rag_eval_expanded_initial.json) | 35/37 automatic checks |
| [Second full live run](rag_eval_expanded_final.json) | 35/37 automatic checks |
| [Targeted live retest](rag_eval_targeted_retest.json) | 4/4, including both cases flagged in the second full run |
| [Scripted baseline](rag_eval_scripted_retest.json) | 17/17 |
| Automated tests | 36 passed |

All 37 cases passed across the second full run and the targeted retest. Each run log records the question, answer, listing IDs, and tool trace. This is evidence for these scenarios. Gemini wording and provider availability can vary.

The first run exposed a returning-user greeting that sometimes answered the new question before inventory retrieval, contradicting the actual answer. Returning-user greetings now use saved profile data. The second run also exposed a budget narration fallback. Gemini now sees the verified filters applied by the search. The evaluator accepts equivalent zero-result wording such as “0 BMW M4 listings,” while still requiring zero returned IDs. Explicit description queries require a phrase match, and the comparison model receives backend-calculated differences.

To run the complete suite again:

```bash
uv run python scripts/evaluate_rag.py --live \
  --dataset data/rag_eval_questions.json \
  --dataset data/gemini_rag_questions.json \
  --dataset data/rag_eval_extended.json \
  --delay 6 --output /tmp/dubizzle-rag-results.json
```

The supplied inventory has no confirmed Dubizzle-managed listings. The live suite checks rejected and incomplete requests and lead recording. The separate [booking demo](demo_transcripts.md) verifies a successful reservation using a labeled synthetic listing.
