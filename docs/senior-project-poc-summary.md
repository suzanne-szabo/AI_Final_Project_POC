# Mental-Model Inference Engine: Proof-of-Concept Summary for the Senior Project

Suzanne Szabo · status as of 2026-11-16 · repository `suzanne-szabo/AI_Final_Project_POC`

> **Context for the reader.** This proof of concept was built as the CS 4300 (AI) final project
> (Nov 3 to Dec 3, 2026). It is **one component** of the senior project, the *diagnostic front end* of
> an adaptive programming-lesson system, not the system itself. This document separates what the class
> project built and showed from what it means for the senior project.

---

## 1. Where this fits in the senior project

**The senior project** is an AI-assisted learning environment that adapts foundational CS lessons
(functions in Python, then the call stack in RISC-V assembly, for example factorial) to what each student
actually believes about how code runs. The research question is whether a system can tell if a
student holds a *viable mental model of a lesson's notional machine*, and adjust the lesson accordingly.

**This proof of concept covers the first step only:** *before* a lesson, infer the student's current
mental model and hand a structured diagnosis to the lesson engine.

```
[Inference engine: THIS POC]  ->  diagnosis (which misconceptions, how certain)  ->  [Lesson engine: future]
         ^ probes, answers, explanations                                             | adapted lesson
         |___________________________________ student ______________________________|
```

**Not in this PoC (senior-project work):**
- the lesson engine and lesson content;
- a student-facing interface;
- real students;
- RISC-V;
- re-diagnosis during and after a lesson.

---

## 2. Scope chosen for the PoC (deliberately narrow)

- **One notional machine:** Python function calls, with assignment as a prerequisite tier, since
  parameter passing in Python *is* assignment. Loops were considered and rejected: their errors are
  often slips rather than coherent models, and they do not lead to the call stack.
- **Five rules of the machine:**
  1. assignment binds a name to an object (never copies, never links names);
  2. `def` binds a function without running it;
  3. a call creates a frame with parameters bound to the argument objects;
  4. local variables vanish when the call ends;
  5. `return` ends the call and hands back a value without displaying it.
- **Eight documented misconceptions**, each a wrong version of one rule. Three are about assignment:
  A1 linked names, A2 reversed direction, A3 copy-on-assign. Five are about functions: F1 return equals
  print, F2 parameter linked to the caller's variable, F3 `def` runs the body, F4 local variables
  outlive the call, F5 code runs after `return`. Their research sources are recorded per entry.
- **15 probe programs.** For each, the student predicts the output and rates their confidence from 1 to 5.

---

## 3. What was built

### 3.1 The representation (the core design decision)

A student's mental model is **the correct notional machine with some rules swapped for buggy
versions**, that is, a subset of the eight-entry catalog. This follows Brown and Burton's BUGGY (1978),
applied to a notional machine.

| Requirement | How the representation meets it |
|---|---|
| Measurable | It can be scored against a known (planted) profile |
| Predictive | A profile predicts the student's exact answer to any probe, which is what makes inference possible |
| Actionable | Each misconception maps to a teaching move for the lesson engine |
| Interpretable | Readable by a teacher or student |
| Buildable without data | No student data is needed |

The alternatives compared were an LLM-written narrative, mastery scores, a concept map and a learned
vector. Only the catalog meets all five requirements.

### 3.2 The inference engine (a hybrid agent)

- **The application owns the belief.** It keeps an exact Bayesian posterior over all 2^8 = 256
  profiles. Every answer and explanation updates it with Bayes' rule.
- **The student's confidence rating sets how much to trust each answer.** A confident wrong answer is
  strong evidence of a misconception; a guess may be a slip.
- **Probe choice by expected information gain.** The next probe is the one expected to reduce the
  uncertainty most.
- **The LLM has two constrained roles** (course models through a gateway):
  - **Interviewer:** a ReAct loop in LangGraph that chooses actions through four typed tools: rank the
    probes, ask a probe (with a required stated reason), ask for an explanation, submit the diagnosis.
    A controller validates every call; the LLM never touches the belief.
  - **Interpreter:** reads a student's free-text explanation and labels which misconceptions it shows,
    or marks it not informative.
- **Output:** a probability for each misconception, plus the most likely profile. The session ends
  `DIAGNOSED` when the agent is certain about every misconception (each probability ≤ 0.15 or ≥ 0.85).
  Otherwise it ends `BUDGET` after 10 probes, or `ERROR` with an explicit reason.
- **Inspectability:** a JSONL trace per session records every action, observation, belief update,
  stated reason and model cost. LangSmith tracing is optional.
- **Engineering practice:**
  - spec-first, with about 190 offline tests that use a scripted fake model;
  - a manifest per run (commit, command, configuration);
  - prompt-cache discipline: a constant system prompt and tools, variable content last, append-only
    history. 70–93% of prompt tokens came from the cache.

### 3.3 Simulated students (needed because no real-student data exists)

- **Bank students:** they follow the answer keys, with a 15% careless-slip rate, confidence ratings,
  15% vague answers, and explanations from a labeled bank of 94 written explanations.
- **LLM students:** an LLM (Gemma) role-plays a planted profile. Persona wording comes from about 30
  real beginner questions on Stack Overflow and Python forums, and each student is given a style (clear,
  terse or hedging). A **fidelity check** measures whether a simulated student actually answers the way
  its planted beliefs predict.

---

## 4. What was tested and found (the class project)

All numbers are on **simulated** students. Bank students follow the agent's own answer keys, so those
results are an upper bound.

| Question | Result |
|---|---|
| Does adaptive probing beat a fixed quiz? (500 students, same 10-probe budget) | **Yes.** Exact profile match: fixed order 0.57, shuffled 0.63, information gain 0.76, information gain + explanations 0.80 (after the D38 fix) |
| Do student confidence ratings help? | **Yes.** Without them, exact match drops from 0.76 to 0.70 and certain diagnoses become much rarer (74% → 48%) |
| Do vague answers hurt? | **Modestly.** About 5 points |
| Can an LLM run the interview? | **Yes.** Qwen interviewer with the live interpreter: 0.90 exact on 20 students (HW-11); about 17 model calls and about 47 s of model time per student |
| Does it hold when students answer in their own words? (LLM students, 12 whose beliefs the simulator could play) | **12/12 exact**, including hedging and terse styles. Caveat: these students never made careless errors |
| Can an LLM convincingly play a confused student? | **Partly.** 76% of answers stayed in character. Six misconceptions were played perfectly; **A2 (reversed assignment) and F5 (code runs after `return`) were never played**, even with worked examples |

**Refinements driven by evidence:**
- **A prompt rule for when to ask for explanations** (D30): exact match went from 0.75 to 0.90 with the
  Gemma interviewer.
- **A required stated reason for every probe** (D32): reasons went from 0 of 22 probes to 162 of 162.
- **Counting admitted careless errors as evidence** (D34): the interpreter's handling of
  careless-error explanations went from 4 of 76 to 65 of 66.
- **D34 had a side effect,** found by failure analysis. Errors where the agent was certain but wrong rose,
  because a slip *away* from a held misconception was counted as evidence against it. The next fix
  (D38) addresses this. Offline it raised exact match from 0.75 to 0.80 and cut certain-but-wrong
  diagnoses by a third. **The live confirmation runs tonight (Nov 16).**

**Still pending:** the final interviewer comparisons on 50 students and the HW-12 report (due Nov 19).
The course key's $2-per-hour cost cap shapes how large live runs can be.

---

## 5. What was learned that matters for the senior project

1. **The representation works as a diagnostic contract.** A probability per known misconception is
   accurate enough to act on, inspectable, and directly usable by a lesson engine. **Keep it.**
2. **The application must own the reasoning; the LLM should be a constrained tool user.** Every serious
   failure was diagnosable from the traces because the belief and the rules lived in code, not in the
   model. This architecture should carry into the senior project.
3. **The interpreter, which reads student explanations, is the most sensitive component.** Small
   interpretation rules (what counts as a careless error, which misconceptions an explanation counts
   for) changed accuracy more than the choice of model did.
4. **Being certain but wrong is the metric that matters most for teaching.** A wrong but confident
   diagnosis would send a student to the wrong lesson. Explanations help, but only with careful scoring.
5. **LLM-simulated students are useful but can't replace real ones.** They test whether the agent
   handles students' own wording, but they can't act out some well-documented misconceptions (A2, F5).
   This is direct evidence that the senior project needs **real-student data**.
6. **Answer keys need more than one form of each wrong answer.** Students who hold a misconception
   sometimes express it in another valid form.
7. **Cost and logistics are real constraints.** About 17 model calls per student, and a $2-per-hour key
   cap means about 50 students per hour. Prompt-cache discipline matters.
8. **Evaluation method:** a protocol fixed before results, matched paired comparisons, and logged
   post-hoc changes caught a refinement that improved one measure while worsening another.

---

## 6. What carries forward and what changes (senior-project roadmap)

**Carry forward as is:**
- the misconception-catalog representation and the Bayesian belief;
- the information-gain probe selection;
- the constrained ReAct interviewer and the controller;
- the trace format, the evaluation protocol method and the prompt-cache rules.

**Change or extend:**
- **Catalog organized by rule:** one value per rule, which removes contradictory profiles and gives 96
  profiles instead of 256, plus a "no consistent model" state per rule.
- **Buggy interpreters** that generate answer keys by running the replaced rule, instead of
  hand-writing them. They would also allow several answer forms per misconception.
- **New probes from the beginner research:**
  - an integer probe for A1;
  - a probe that separates rebinding from mutation for list parameters;
  - a possible new misconception: *assigning inside a function changes the global variable with the
    same name*.
- **A careless-error flag in the interpreter**, so a slip is told apart from correct reasoning.
- **RISC-V:** extend the same structure to the call-stack notional machine (frames, return address,
  saved registers) with its own catalog and probes.
- **Real students:**
  - a GUI that captures the predicted output, the confidence rating and the explanation, and gives no
    correct/incorrect feedback during diagnosis;
  - a pause-and-resume loop (a LangGraph interrupt with a checkpointer);
  - an independent check of the diagnosis (think-aloud interviews or a longer test);
  - IRB review, consent, anonymous IDs, and no third-party tracing without consent.
- **Hand-off to the lesson engine:** define the interface (the probability per misconception, the
  certainty, and which probes produced the evidence) and re-diagnose after the lesson.

---

## 7. Honest limits of what the PoC shows

- **No real students.** All accuracy figures are on simulated students. The bank students are an upper
  bound.
- **Narrow scope:** only the eight catalog misconceptions, 15 probes, two course models and one notional
  machine.
- **Small live samples** (12 to 100 students), and live model replies vary from run to run.
- **The agent can only diagnose misconceptions in its catalog.** A student with a different wrong model
  shows up as uncertainty, not as a new diagnosis.

**Key project documents:**
- `docs/mental-model-representation.md` (the representation and its alternatives)
- `docs/notional-machine.md` (the exact machine, the misconceptions and the inference math, with diagrams)
- `docs/catalog-sources.md` (research evidence for each misconception)
- `docs/beginner-sources.md` (real beginner questions)
- `docs/decisions.md` (decisions D1–D38)
- `docs/evaluation-protocol.md`
- `docs/student-simulator-plan.md`
