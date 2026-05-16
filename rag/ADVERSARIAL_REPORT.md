# Adversarial Hardening Report

Status: implemented; live execution pending Qdrant data, Redis BM25 indexes, OpenAI credentials, and calibrated Gate 2.

## Suite Coverage

- Personal info: 5 queries
- Wrong company: 3 queries
- Off-topic: 4 queries
- Non-existent: 4 queries
- Prompt injection: 3 queries
- Speculative/future: 3 queries
- Arithmetic traps: 3 queries

Total: 25 adversarial queries.

## Expected Pattern

Gate 1 should catch clearly off-document, wrong-company, and low-similarity requests. Gate 2 should catch plausible but unsupported requests such as speculative forecasts, prompt injection, and fabricated arithmetic.

## Live Run Command

```powershell
python backend\tests\test_adversarial.py
```

## Results

| Metric | Result |
| --- | --- |
| Adversarial pass rate | pending |
| Gate 1 catch rate | pending |
| Gate 2 catch rate | pending |
| False positives on good queries | pending |

Update this table after Gate 2 calibration and live ingestion.
