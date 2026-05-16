# Nikhil (RAG Lead) Demo Script

## 30-Second Pitch

My component is the retrieval backbone of FinSight AI. Every user question passes through hybrid retrieval, neural reranking, and two document-grounding gates before any LLM sees context. BM25 catches exact financial terms, dense search catches semantic matches, RRF combines both, and the CrossEncoder reranker chooses the strongest evidence. If the document does not support the question, Gate 1 or Gate 2 returns `Not found in the document.` before generation can hallucinate.

## Wow 1: Hybrid Retrieval Proof

Query:

```text
What is consolidated total income H1-26?
```

Command:

```powershell
curl "http://localhost:8000/api/retrieval/debug?project_id=adani-q2-fy26&query=What%20is%20consolidated%20total%20income%20H1-26%3F"
```

Show:

- `bm25_hits` has exact term evidence.
- `dense_hits` has semantic evidence.
- `rrf_merged` combines them.
- `reranked` places the strongest chunk at the top.

Talking point:

BM25 catches exact financial language, dense search catches meaning, and RRF lets both vote.

## Wow 2: Instant Refusal

Query:

```text
What is the CEO's email address?
```

Command:

```powershell
curl "http://localhost:8000/api/retrieval/debug?project_id=adani-q2-fy26&query=What%20is%20the%20CEO%27s%20email%20address%3F"
```

Show:

- `refusal.level` is `1` or `2`.
- Message is `Not found in the document.`
- No generation call is needed.

Talking point:

The guardrail fires before answer generation, which keeps negative controls from turning into fabricated answers.

## Wow 3: Numeric Routing Readiness

Query:

```text
What percent did consolidated income grow H1-26?
```

Command:

```powershell
curl "http://localhost:8000/api/retrieval/debug?project_id=adani-q2-fy26&query=What%20percent%20did%20consolidated%20income%20grow%20H1-26%3F"
```

Show:

- Top chunks include `is_table=true` or income-related sections.
- M4 can route table-backed numeric questions to PAL instead of free-form arithmetic.

Talking point:

Retrieval gives M4 the structured signal it needs to calculate instead of guessing.

## Final Validation Commands

```powershell
python backend\eval\calibrate_gate2.py --project-id adani-q2-fy26
python backend\eval\run_eval.py --assert-ndcg=0.75
python backend\tests\acceptance\test_t1_t5.py
python backend\tests\test_concurrency.py
```
