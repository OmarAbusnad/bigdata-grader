# Big Data Grader V4 — Self Test Results

Date: 2026-10-03

## Automated tests

```text
16 passed, 3 subtests passed
```

Validated components:

- heuristic repository discovery,
- LLM plan normalization,
- rejection of unsafe shell chaining,
- relevant-file selection for AI analysis,
- sandbox command rendering,
- Docker sandbox security defaults,
- previous V3 runtime/oracle logic regression tests,
- static-check evidence regression tests,
- Spark probe logic regression tests.

## Dry-run evaluation

Fixture `aiman` was evaluated without AI and correctly produced:

```text
plan_confidence = 0.55
manual_review = true
```

This verifies that V4 no longer pretends heuristic discovery is sufficient for automatic execution when the configured confidence threshold is 0.80.

## Environment check in build environment

```text
Python: OK
Git: OK
Hidden tests: OK
Docker: unavailable in this build environment
OPENAI_API_KEY: not configured in this build environment
```

Therefore the Docker + real-LLM end-to-end execution cannot be honestly claimed as executed here. The code path is implemented and guarded so that lack of Docker returns `INFRA_ERROR` rather than a student failure.
