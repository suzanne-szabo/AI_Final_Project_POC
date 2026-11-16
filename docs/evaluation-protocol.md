# Evaluation Protocol (HW-12)

Status: fixed on 2026-11-15, **before** the evaluation results were inspected (lecture 230: specify the
cases, comparisons, measurements and interpretation rules before outcomes). Owner: Suzanne Szabo.
Drafted by Claude. Any later change to this protocol is recorded in §9 with its reason and date.

Related: `scripts/overnight_eval.sh`, `scripts/check_students.py`, `docs/decisions.md` (D34, D35),
`docs/notional-machine.md`, `docs/student-simulator-plan.md`.

---

## 1. Goal and success

**Goal.** Before a lesson, infer which of the eight catalog misconceptions a student holds about the
Python function-call notional machine, using at most 10 probes and 5 explanations.

**Terms.** Two kinds of confidence are kept apart in every report:
- **student confidence rating**: the student's own 1–5 rating of an answer, an input to the agent;
- **agent certainty**: the agent's probability that the student holds each misconception, its output.

**Success criterion (per session).** A session succeeds when:
1. it ends `DIAGNOSED` or `BUDGET`, not `ERROR` or `STEP_LIMIT`; and
2. its reported profile (every misconception with probability > 0.5) **equals the planted profile
   exactly**.

**Mandatory requirement.** The worst outcome for a lesson is the agent being certain and wrong: a session
that ends `DIAGNOSED` with a wrong profile. It is counted and reported separately, beside every success
rate, and a higher success rate does not cancel it out.

**Efficiency requirement.** Within the budget (10 probes, 5 explanations, 30 steps). Cost is reported, but
no cost limit decides success.

**For an unsupported input** (for example, an unknown model name), success means the run ends with an
explicit `ERROR` terminal reason and a retained trace, not a crash.

---

## 2. Task suite and environment

- **Students:** simulated students with planted profiles. Each misconception is planted independently
  with probability 0.2, using seed 7, so student `sim-NNN` is the same student in every configuration.
  - **Bank students:** answers follow the answer keys, with a 0.15 slip rate, informative confidence
    ratings, 15% vague or hedged answers, and explanations from the labeled bank.
  - **LLM students:** Gemma-4-26B-A4B playing a planted profile (D35).
- **Sample sizes:**
  - 500 students for the offline comparisons;
  - 100 for the live interpreter and interviewer comparisons;
  - 20 for LLM students;
  - 12 for the LLM-student fidelity check.
- **Out of scope:** real students, misconceptions outside the catalog, other notional machines.

---

## 3. Configurations and matched comparisons

In every comparison the students, seed, budget, stopping rule and scoring code are matched. The only
intended difference is the one named in the row.

| Id | Question | Compared configurations | Run folders (`runs/`) |
|---|---|---|---|
| C1 | E1: adaptive vs. fixed quiz | fixed, shuffled, eig, eig_explain; oracle interpreter; 500 students | `eval-offline-500` |
| C2 | E2: do student confidence ratings help? | eig, eig_explain with vs. without ratings; 500 students | `eval-offline-500`, `eval-offline-500-noconf` |
| C3 | **Refinement (D34)** in isolation | eig_explain with the live Qwen interpreter: **baseline** code `3a00ed7` vs. **revised** code; 100 students | `eval-baseline-eigexplain-llm-100`, `eval-revised-eigexplain-llm-100` |
| C4 | Refinement in the full agent | Qwen interviewer: baseline vs. revised; 100 students | `eval-baseline-qwen-100`, `eval-revised-qwen-100` |
| C5 | E3: interviewer model | Qwen vs. Gemma interviewer, revised code; 100 students (decision on the first 50 as planned, all 100 reported) | `eval-revised-qwen-100`, `eval-revised-gemma-100` |
| C6 | Robustness: vague and hedged answers | eig_explain, oracle; vague-answer rate 0.15 vs. 0; 500 students | `eval-offline-500`, `eval-offline-500-novague` |
| C7 | E4: does the agent's accuracy hold when students answer in their own words? | Qwen interviewer + Qwen interpreter facing Gemma LLM students (`--student-style mixed`) vs. bank students with the same planted profiles (the same ids in `eval-revised-qwen-100`). **Only the 12 of the first 20 students without A2 or F5 planted** (`--skip-planted A2_REVERSED F5_RUNS_AFTER_RETURN`; D37) | `eval-llmstudents-faithful` |
| C8 | Agent reproducibility | Qwen interviewer, HW-11 run vs. tonight's baseline run, on the same 20 students | `baseline-qwen-d32`, `eval-baseline-qwen-100` (sim-000 to sim-019) |

C3 is the primary test of the refinement. Its decider is deterministic code, so the only live
component that differs is the interpreter prompt. C4 checks the same change inside the full agent,
where the interviewer adds run-to-run variation.

---

## 4. Measures (each with its direction)

**Quality:**
- **Exact match rate** = successful sessions / evaluated sessions [higher is better].
- **Certain-but-wrong rate** = sessions ending `DIAGNOSED` with a wrong profile / evaluated sessions
  [lower is better].
- **Brier score** = mean over sessions and misconceptions of (probability − planted 0/1)² [lower is
  better].
- **Per-misconception precision and recall** [higher is better].
- **Calibration of agent certainty:**
  - pool every (session, misconception) probability;
  - put them in the bins [0, .1), [.1, .3), [.3, .5), [.5, .7), [.7, .9), [.9, 1];
  - for each bin report the count, the mean probability, and the observed share planted;
  - calibration error = the count-weighted mean of |mean probability − observed share| [lower is better];
  - a mean probability above the observed share means overconfidence.
- **Subgroups:** exact match rate by the number of planted misconceptions (0, 1, 2, 3+).

**Paired outcomes** (C3, C4, C5, C6, C7), one count per student:
- both succeed;
- only the revised (or variant) configuration succeeds;
- only the baseline (or original) succeeds;
- neither succeeds.

C6 also reports the pass-to-fail rate: original passes, variant fails, divided by original passes.

**Efficiency.** Every measure includes failed sessions:
- probes and explanations per session [lower is better];
- model calls per session [lower is better];
- model seconds per session, as the median and the 95th percentile [lower is better];
- cached share of prompt tokens [higher is better];
- model calls per successful session = total calls / successful sessions [lower is better].

**Reliability:**
- ERROR, STEP_LIMIT and rejection counts [lower is better];
- C8 agreement = the share of the 20 students with the same success status in both runs, and the share
  with the identical reported profile.

**Mechanism check for D34:** the share of bank slip explanations the live interpreter marks informative
[higher is better]. It is computed from the explanation records in the C3 and C4 traces.

**LLM-student fidelity:** belief fidelity [higher], leak rate [lower] and neutral accuracy [higher], from
`check_students.py`.

---

## 5. Decision rules (fixed in advance)

- **Accept D34** if, in C3:
  1. the certain-but-wrong count does not rise;
  2. exact match does not fall by more than 2 students; and
  3. the mechanism check rises.

  If (1) and (2) hold but (3) does not, the change is kept but recorded as unconfirmed. If (2) fails,
  the change is reverted and the paired failures are analyzed. C4 is reported as supporting evidence
  only: interviewer variation makes it noisier.
- **Interviewer model (C5).** Choose the model with the higher exact match on the first 50 students. If
  the two are within 3 students, choose the one with fewer certain-but-wrong sessions. If they are still
  tied, choose the one with the lower median model seconds per session. Results on all 100 students are
  reported either way.
- **Using LLM students for evaluation (C7).** LLM-student results are treated as evidence about the agent
  only if the 12-student fidelity check reaches belief fidelity ≥ 70% and leak ≤ 25%. Otherwise they are
  reported as a finding about the simulator, and C7 is descriptive only.
- **C7 scope, fixed after the fidelity rerun and before any C7 data (D37).** Gemma does not express A2 or F5
  (0/3 and 0/4 leaked), while the other six misconceptions were 22/22. C7 evaluates the inference tool, not the
  simulator, so it runs only on students whose planted profile the simulator can play: the 12 of the first 20
  without A2 or F5. Detection of A2 and F5 is evaluated on bank students only (C1 to C5).
- **Circularity (C7).** If exact match on LLM students is more than 15 percentage points below that of
  the paired bank students, the bank results are reported as an upper bound that does not transfer.

---

## 6. Retained cases (selection rule fixed in advance)

At least six cases, chosen by these rules from the named runs, not by hand after looking at the results.
Each is reported with its outcome, success status and an excerpt of its trace.

| # | Kind | Rule |
|---|---|---|
| R1 | Ordinary, successful | `eval-revised-qwen-100`: the lowest-numbered student with ≥ 2 planted misconceptions whose session succeeds |
| R2 | Ordinary, successful, no misconceptions | `eval-revised-qwen-100`: the lowest-numbered student with an empty profile whose session succeeds |
| R3 | Changed by the refinement | C3: the lowest-numbered student that succeeds only in the revised configuration; if there is none, the one that fails only in the revised configuration |
| R4 | Unsuccessful: certain but wrong | `eval-revised-qwen-100`: the lowest-numbered certain-but-wrong session; if there is none, the lowest-numbered failed session |
| R5 | Boundary: budget reached | `eval-revised-qwen-100`: the lowest-numbered session ending `BUDGET` |
| R6 | Unsupported input | an interviewer run with an unknown model name (rerun of the HW-11 B1 command on the revised code) |
| R7 | LLM student | C7 (`eval-llmstudents-faithful`): the lowest-numbered success and the lowest-numbered failure, if both exist |

---

## 7. Interpretation limits

- All students are simulated. Bank students follow the agent's own answer keys, so bank results are an
  upper bound (D7). LLM students reduce this circularity but do not remove it: their personas are built
  from the same catalog.
- Live model replies can differ between runs (C8 measures how much). One run per configuration; no
  conclusion is drawn from differences smaller than the C8 disagreement rate.
- Conclusions are limited to the eight-misconception catalog, these 15 probes, these budgets, and the two
  course models.

---

## 8. Provisional recommendation criteria (for the HW-12 assessment)

These criteria are fixed in advance. The evidence is reported against each one, and the final call is
made in HW-13.

- **Use within a defined scope** (a research tool, or a supervised pilot before a lesson): exact match ≥
  0.85 and certain-but-wrong ≤ 5% on bank students; no ERROR on supported inputs; and the C7 gap within
  15 points.
- **Revise before use:** the bank criteria are met but the C7 gap exceeds 15 points or the
  certain-but-wrong rate exceeds 5%; or the LLM-student fidelity gate (§5) fails, so the agent is
  untested beyond bank students.
- **Do not use for the intended purpose:** on LLM students the agent does no better than the fixed quiz
  (C1's fixed decider) on exact match.

None of these establishes readiness for real students. That needs the supervised pilot planned for the
senior project.

---

## 9. Changes to this protocol

| Date | Change | Reason |
|---|---|---|
| 2026-11-15 | One persona revision round before C7 (`PERSONA_BELIEFS` for A1, A2, F5 gain a worked example written with non-probe programs); the fidelity check is rerun and the §5 gate is applied to the rerun. No further revision before C7. | First full check (`runs/students-check-2026-11-15_1508/`): belief fidelity 69%, leak 24% (gate: ≥ 70%, ≤ 25%). Misses were concentrated: A2 0/3 (model states the correct rule), F5 0/4 (one student leaked; one held the belief but in a different answer form), A1 2/4; the other five misconceptions 18/18. The revision was planned in `docs/student-simulator-plan.md` §3.1. Made before any C7 data. |
| 2026-11-15 | Fidelity rerun (`runs/students-check-2026-11-15_1524/`): 76% fidelity, 24% leak, so the §5 gate **passes** and C7 counts as evidence. A1 is now 4/4, but A2 (0/3) and F5 (0/4) still leak completely, so C7 is reported split three ways (§5). | Without the split, simulator leaks on A2 and F5 would be scored as agent errors. The split was fixed before any C7 data. |
| 2026-11-15 | C7 runs only on the students without A2 or F5 (12 of the first 20), replacing the three-way split. | Suzanne: the evaluation is about the inference tool, not the simulator; students whose beliefs the simulator cannot express would measure the simulator. Decided before any C7 data. |
| 2026-11-16 | Night-1 interviewer runs (C4, C5) are invalid and rerun on 50 students each through `scripts/paced_run.py` (night 2, `scripts/evening_eval.sh`): `eval-baseline-qwen-50`, `eval-d38-qwen-50`, `eval-d38-gemma-50`. LangSmith off for all night-2 runs. C8 uses `baseline-qwen-d32` vs. `eval-baseline-qwen-50` (sim-000 to sim-019), plus the 33 valid night-1 baseline sessions. | The course key has a $2/hour spending cap. The night-1 baseline Qwen run hit it after 33 students; both revised interviewer runs failed on every session (`ExceededBudget`, recorded as MODEL_ERROR). No other night-1 run was affected (checked: no budget errors in their traces). The paced harness discards a session that hits the cap, waits, and reruns it from a fresh copy of the student; agent code is unchanged in both trees. 50 students is what the hourly budget allows, and the protocol's C5 decision was already on the first 50. LangSmith's free tier is used up; tracing never changes prompts or results. |
| 2026-11-16 | **D38 added after the C3 results** (a second refinement, decided after seeing data): after an unexpected answer, an explanation with no labels does not update the belief. C3 becomes three-way on the same 100 students: baseline (`3a00ed7`), D34 (`eval-revised-eigexplain-llm-100`), D34+D38 (`eval-d38-eigexplain-llm-100`); the §5 D34 acceptance rule is applied to D34+D38 vs. baseline. C4 compares `3a00ed7` with the D34+D38 code. The eig_explain rows of C2 and C6 are rerun offline with D38 (`eval-offline-500-d38`, `-noconf-d38`, `-novague-d38`). | C3 failed acceptance rule (1): certain-but-wrong rose 5 → 11, although exact match held (85 vs 85) and the mechanism check rose (4/76 → 65/66). Failure analysis (lecture 230 workflow): 6 of the 7 new cases were students who slipped away from a misconception they hold, gave an unexpected answer, and admitted a slip, which D27's scope counted against every misconception the probe tests. Offline test before any live rerun: 0.75 → 0.80 exact, certain-but-wrong 96 → 65 on 500 students. Reported as a post-hoc change. |
