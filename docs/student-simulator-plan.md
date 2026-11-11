# Student Simulator: Plan, Scaffolding and Intended Use

Status: plan for the evaluation week (ending Nov 19), 2026-11-11. Owner: Suzanne Szabo.
Related: `specs/students.md`, decisions D7, D17, D18, D22.

## 1. Why a simulator, and why more than one

The agent's accuracy can only be measured against a known answer, and no real student data exists yet
(collecting it is senior-project work, after consent and IRB). Simulated students supply the ground
truth: each one is given a planted set of misconceptions, and the agent's estimate is scored against it.

The risk is circularity. A simulator built from the same answer keys the agent assumes will make the
agent look better than it is (D7). So the plan uses simulators of increasing independence from the
agent's own model:

| Simulator | How it answers | How independent of the agent's model | Status |
|---|---|---|---|
| `BankStudent` | Answer keys + slips, confidence, hedges; explanations drawn from the labeled bank | Low: same keys and the same kind of slips the belief assumes | Built; used in every run so far |
| `LLMStudent` (course model) | An LLM role-plays a student with the planted beliefs, written as plain sentences; it predicts outputs and explains in its own words | Medium: it never sees the answer keys, so its answers and explanations are its own | Built and tested offline; **not yet run live** |
| `LLMStudent` (a different model family, e.g. Claude through the API) | Same as above | Higher: no shared habits with the interviewer or interpreter model | Possible with one adapter; optional (section 5) |
| Real students | — | Full | Senior project pilot only |

## 2. What exists now (scaffolding)

- **One `Student` interface** (`answer(probe) -> Response`, `explain(probe) -> str`). Every decider can face
  every student (D18).
- **`LLMStudent`** (`mm_agent/students.py`): a constant system prompt shared by all LLM students, then one
  message stating the student's beliefs (the misconception for each one held, the correct rule for each one
  not held), then an append-only conversation. Two forced tools: `respond(answer, confidence)` and
  `explain(text)`. Invalid replies get one retry, then a fallback answer, and the failure is counted.
- **The run command** already supports it:
  `python -m mm_agent.run --deciders ... --student llm --student-model <model> --interpreter llm`.
  (The oracle interpreter cannot be used with LLM students, since their explanations are not in the bank.)
- **Traces** record the student model in the header; with LangSmith on, every student call is visible.

## 3. What is still needed before LLM students can be trusted

1. **A fidelity check (new script, `scripts/check_students.py`).** Before LLM students are used to grade the
   agent, check that they actually behave like their planted profile. Give each of, say, 16 LLM students
   (two per misconception, plus some with none) all 15 probes, without any interviewer, and compare each
   answer with the answer the planted profile predicts (`probe.intended(profile)`). Report, per
   misconception and per model:
   - **fidelity**: share of answers that match the planted profile;
   - **leak rate**: share of answers that are correct where the profile predicts a wrong answer (the model
     "knows Python" and ignores the persona; the most likely failure);
   - **unexpected rate**: answers that match neither;
   - **confidence and explanation sanity**: are wrong-by-belief answers given with high confidence, and do
     the explanations show the belief?
   About 16 × 15 = 240 calls per model. If fidelity is low for a misconception, the persona wording for it
   is revised (for example, a worked example of the belief) before any evaluation run.
2. **Persona style (small addition).** An optional `style` for LLM students: `clear`, `terse`, or `hedging`,
   so explanations vary in clarity the way real ones do, without anyone writing them. Default `clear`.
3. **Model pairing rule.** The student model should differ from the interviewer model, so the two do not
   share blind spots: Gemma interviewer with Qwen students and the reverse.
4. **Interpreter accuracy on LLM explanations.** There is no ground-truth label for an LLM student's free
   text, only the planted profile. Two measures: (a) the share of explanations whose labels match the
   misconception that produced the answer, as a proxy; (b) a hand-labeled sample of about 30 explanations
   (by Suzanne) to check the proxy.

## 4. How we will use it (evaluation week)

Questions, each answered with the measures already in the report (exact match, per-misconception precision
and recall, Brier score, confident-but-wrong rate, probes and explanations used, model calls, latency,
cached share):

| # | Question | Design |
|---|---|---|
| E1 | Does adaptive probing beat non-adaptive quizzes? | fixed, shuffled, eig on 200 bank students at slips 0.05 / 0.15 / 0.25 (offline, free, minutes) |
| E2 | Do explanations and confidence ratings help? | eig vs. eig_explain; confidence on / off / uninformative (offline) |
| E3 | Does the LLM interviewer match or beat the code deciders? | eig, eig_explain, interviewer-Gemma, interviewer-Qwen on 100 bank students with the live interpreter |
| E4 | Do the results hold with students who are not built from the answer keys? | the four deciders of E3 on 30–40 LLM students (crossed models), after the fidelity check |
| E5 | How does the interpreter handle real-sounding explanations? | the proxy and the hand-labeled sample from E4 |

**Run cost and time (course gateway).** An LLM-student session has about 10 student answers, about 3
explanations, 17–20 interviewer calls and about 3 interpreter calls: roughly 35 calls, about 40–80 seconds.
E4 with 40 students and 4 deciders is about 160 sessions, so 2–3 hours of batch time, run overnight or in
parts. E1 and E2 are offline and take minutes.

**What would change the conclusions.** If the agent's accuracy on LLM students (E4) is much lower than on
bank students (E3), the bank results were inflated by circularity, and the report says so. If it is
similar, the bank results gain credibility. Either way it is a finding.

## 5. Could Claude play the student?

Two very different meanings:

- **Claude (this assistant) answering live during a run.** Not practical. The workspace Claude works from
  cannot reach the course gateway, cannot hold an interactive process open between steps, and would need a
  file hand-off for every answer, so each probe would take a full conversation turn. It would use
  Suzanne's chat usage, could not be repeated exactly, and would not scale past a demo. What Claude *can*
  do during a run is watch it: read the trace files in the run folder as each session finishes and report
  on them.
- **A Claude model as the `LLMStudent`'s model, through the Claude API.** Technically simple: `LLMStudent`
  takes any LangChain chat model, so it needs the `langchain-anthropic` package, an `ANTHROPIC_API_KEY`, and
  a small branch in `llm.make_model`. It gives the most independent simulated student, since Claude is a
  different model family from the interviewer and interpreter. But it is billed: Claude API usage is
  separate from a Claude chat subscription and is paid through the Claude Console (Max, Ultra and Team plans
  include monthly API credits; Pro does not). Recommended only as an optional extra for E4, after the free
  course models have been tried.
