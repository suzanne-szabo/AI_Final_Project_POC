# Week 2 Live Runs (on the course gateway)

These runs need Tailscale and `LLM_API_KEY` in `.env`. Run them from the project folder, in this order.
Each writes its results under `runs/`; send the `summary.md` files back for review.

## 1. Interpreter comparison on clean and vague explanations (D25)

```bash
uv sync
uv run python scripts/compare_models.py --repeat 2
```

- Runs the 24 clean and 34 vague explanations through Qwen3.8-Flash-Next and Gemma-4-26B-A4B, twice.
- About 230 calls per model; roughly 5–10 minutes in total.
- Look at: exact match on the vague set, agreement on "informative", and false alarms on
  non-informative explanations (labels for "idk"-type answers). D12's choice of Qwen is confirmed or
  revised on these numbers.

## 2. Interviewer model check (D16)

```bash
uv run python scripts/check_interviewer.py --repeat 2
```

- Eight fixed situations (S1–S8), one model call each, for both models: 32 calls; about 2 minutes.
- Look at: valid single tool call rate, accepted rate, and expected-action rate (did it ask for an
  explanation after a misconception answer, submit when confident, avoid submitting too early, recover
  after a rejection), plus latency and cached share.

## 3. Interviewer smoke test (after choosing the interviewer model)

```bash
uv run python -m mm_agent.run --deciders eig eig_explain interviewer \
    --interviewer-model <chosen model> --interpreter llm --students 20 --seed 7 \
    --out runs/smoke-2026-11-12
```

- 20 simulated students, each facing the information-gain baselines and the LLM interviewer, with the
  live Qwen interpreter labeling explanations.
- Roughly 20 × (10–25 interviewer calls + up to 5 interpreter calls); about 15–25 minutes.
- Look at: exact match and Brier score per decider, errors by kind, rejections per session, model calls
  per session, latency, cached share.

## Optional: LangSmith tracing (D14)

When you have the API key, add to `.env`:

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<key>
LANGSMITH_PROJECT=mental-model-agent
```

Then rerun the smoke test (or a 3-student version of it) and open the project in LangSmith. The JSONL
traces remain the evidence record. Simulated students only: no real student data goes to LangSmith
until the privacy review in the senior project.
