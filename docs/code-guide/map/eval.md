# `eval`

## `backend/eval/rag_eval.py` (77 lines)

Measures the guideline search on eval/rag_cases.json.

    cd backend && uv run python eval/rag_eval.py [k]

For each case: whether an expected passage is in the top k (hit@k), its
rank (for mean reciprocal rank), the share of top-k passages from Indian
sources (tier 1), and the time taken. Uses MEDORA_KNOWLEDGE_DATABASE_URL and
the same source switches as reports (MEDORA_KNOWLEDGE_TESTING_SOURCES ...).
Targets from the plan: hit@8 >= 85%, search time a few seconds.

As in a report: a diagnosis question also reads the pages of the conditions
the symptom-understanding step (Gemini) names to look up, and a treatment
question ("X treatment and dose for ...") the pages of X. `--plain` searches
the question alone.

Functions and classes:
- **L34–39** `def _look_up`  
  What the understanding step names for this presentation.
- **L42–71** `def main`

## `backend/eval/report_eval.py` (132 lines)

Measures the whole report (CrewAI panel, writer, pharmacist review, code
rules, guideline RAG) on eval/report_cases.json, live on Gemini.

    cd backend && uv run python eval/report_eval.py            # every case
    cd backend && uv run python eval/report_eval.py uti-woman  # some cases

Per case: is the most likely condition right, is a must-rule-out listed, no
wrong condition or sensitive word, urgency and department acceptable, the
expected medicine present and a wrong one absent (or no medicine at all when
none may be shown), and how long it took. Writes eval/report_results.json.
Nothing is saved to the database. The expected answers are DRAFT (see the
cases file) until a doctor confirms them.

Settings and constants:
- **L30** `HERE`
- **L31** `CONCURRENT`

Functions and classes:
- **L34–43** `def _session`
- **L46–48** `def _has`
- **L51–79** `def score`
- **L82–127** `async def main`
