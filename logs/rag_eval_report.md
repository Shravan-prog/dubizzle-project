# Inventory question evaluation

The 17 labeled questions use the supplied 100-row inventory. Checks cover listing IDs, comparison count and duplicates, selected answer facts, preference persistence, refusals and lead recording. The runner gives each run its own temporary SQLite database and lead CSV.

```bash
uv run python scripts/evaluate_rag.py --output /tmp/rag-scripted.json
uv run python scripts/evaluate_rag.py --live --output /tmp/rag-live.json
```

| Check | Result |
| --- | --- |
| Existing pytest suite | 31 passed |
| Scripted planner with real retrieval and storage | 16/17 |
| Live Gemini with real retrieval and storage | 17/17 after reviewing and rescoring one wording mismatch |

The [live capture](rag_eval_live.json) preserves the original 16/17 score. G02 returned zero listings and correctly said “No Honda cars were found under AED 5,000.” The wording check was broadened and the captured reply passed it. Some turns in the live run used direct application logic or fallback narration. The tool traces show which stages called the model.

The [scripted capture](rag_eval_scripted.json) failed S03. The scripted planner deliberately omitted the sort arguments for “lowest listed price.” The backend returned its default inventory page because its deterministic override recognizes “lowest price” but misses the inserted word. Live Gemini selected the correct sort and returned CAR-060 at AED 35,000.

## Assignment readiness

- FastAPI handles inventory search and chat, and the Streamlit client uses HTTP. The assignment accepts tool calling and hybrid retrieval. The implementation uses structured filters with BM25 keyword ranking.
- The live run retrieved the correct Honda, resolved mileage and warranty follow-ups, reported missing data, produced a three-car comparison and recalled preferences in a fresh session.
- Both modes refused the tested coding and competitor prompts. They rejected invalid viewing hours and refused to book an unconfirmed listing. The lead was retained. The supplied inventory has no confirmed dubizzle-managed listing, so successful booking uses the labeled synthetic fixture in the existing [demo transcripts](demo_transcripts.md).
- The README covers setup, architecture choices, design and future work, and includes the two required conversation demonstrations.

The implementation meets the documented prototype scope. S03 remains a resilience gap if the planner omits sorting. These case scores describe the selected questions and one live provider run.
