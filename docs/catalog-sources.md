# Catalog Sources: Evidence for Each Misconception and Its Probes

Status: first sourcing pass, 2026-11-10. Owner: Suzanne Szabo.
Related: `mm_agent/catalog.py`, `mm_agent/probes.py`, `docs/mental-model-representation.md`, decision D26.

## Summary

- **Five of the eight misconceptions are supported by published research or a curated research
  inventory:** the three assignment misconceptions, parameter linking (F2), and execution continuing past
  `return` (F5).
- **Two are documented in teaching materials but not yet traced to research:** return vs. print (F1) and
  the body running at `def` (F3). Both are well-known novice errors, but a textbook or teacher note is not
  a research citation.
- **One is weakly supported:** local variables outliving the call (F4). Related scope misconceptions are
  documented; this exact belief has not been found in a source yet.
- **No source reports the exact wrong outputs for our 15 programs.** The answer keys follow from the
  misconception definitions, and the probe format matches published instruments (short programs, answer
  options mapped to models, written explanations), but the keys are not yet validated against real
  students. That validation belongs in the senior project's supervised pilot.

## Evidence levels used

| Level | Meaning |
|---|---|
| Strong | Reported in peer-reviewed studies of students, ideally with frequencies |
| Moderate | In a curated research inventory or a peer-reviewed study, but in a different form or language |
| Practitioner | Described by teaching materials or instructors, not (yet) by a study we have located |
| Weak | Only related misconceptions found |

## Per misconception

| Id | Level | Verified sources | How our probes compare |
|---|---|---|---|
| `A1_LINKED` | Moderate | Kohn (2017) found that some high-school students apply a model of mathematical substitution, believing a statement like `y = 2*x` establishes a link between the two variables. The progmiscon.org inventory lists `VariablesHoldExpressions` for Python (= stores a reference to the expression). Tunnell Wilson et al. (2017) report a "bidirectional assignment" model. | P01 and P04 test a link after `b = a`. Kohn's form uses an expression, so a confirmation probe such as `x = 2; y = 2 * x; x = 5; print(y)` (linked model predicts 10) would match the documented form more closely. |
| `A2_REVERSED` | Strong | Ma et al. (2007) extended Dehnadi and Bornat's questionnaire: students predicted results of small program fragments from answer options that each mapped to a mental model of assignment. About one third of students held non-viable models of value assignment at the end of their first year. | P02 is this item type. Note: cite Ma et al., not Dehnadi and Bornat's aptitude claims, which Bornat later retracted ("Camels and humps: a retraction"). |
| `A3_COPY_ON_ASSIGN` | Strong | progmiscon.org lists `AssignmentCopiesObject` for Python. Ma et al. (2007): only 17% of students held a viable model of reference assignment. Tunnell Wilson et al. (2017) identify "assignment by copy" as an incorrect model. | P03 (aliasing through assignment) and P14 (through a parameter) match. |
| `F1_RETURN_IS_PRINT` | Practitioner | The *Foundations of Python Programming* textbook (Runestone) notes that many beginning programmers find the print/return distinction very confusing; a UC Berkeley Python instructor reported return vs. print as a recurring beginner problem (Yee, 2003, edu-sig). | Our entry merges two directions: "returning displays the value" (P06) and "a function that prints gives that value back" (P05). These may be separate beliefs; check with data and consider splitting. |
| `F2_PARAM_LINKED` | Strong | Tunnell Wilson et al. (2017): in a question where a method reassigns its parameter, 9 of the 10 students who answered wrongly chose the answer in which the caller's variable changes (Java quizzes in an upper-level course, about 30% wrong per question). Fleury (1991) and Madison (1995) studied the rules students construct for parameter passing; Madison found students' understanding of parameters fragile at the end of the introductory course. | P07 and P15 have the same structure as Tunnell Wilson's question 1. Their instrument (short program, distractors from known misconceptions, written explanation) is the same format as ours. |
| `F3_DEF_RUNS_BODY` | Practitioner | The Runestone *CS Principles* teacher notes describe this misconception and the exact detection method: show a function definition containing prints but no call, and ask for the output. | P08 is that detection item; P09 is a variant. |
| `F4_LOCALS_OUTLIVE_CALL` | Weak | James, Becker and Minier (2019) report four scope-related misconceptions involving parameters, variable declarations and loop variables; related, but not this exact belief. | P10 and P11 rest on my own reasoning about the belief. Least supported entry. |
| `F5_RUNS_AFTER_RETURN` | Moderate | progmiscon.org lists `DeferredReturn` for Python: "A return statement in the middle of a function doesn't return immediately." The Runestone teacher notes describe students who believe the entire body executes regardless of where `return` appears. | P12 matches directly. P13's key (a later `return` overrides the first) is my extrapolation of the same belief. |

## Further findings relevant to the design

- **Python alone may hide the notional machine.** Johnson, McQuistin and O'Donnell (2020) found many
  introductory Python students form inadequate and brittle mental models, and recommend teaching Python
  alongside a low-level language that makes the notional machine explicit. This supports the senior
  project's pairing of Python and RISC-V.
- **Students' explanations are hard to code.** Tunnell Wilson et al. (2017) found students used terms
  like "reference" in many senses, which made their written explanations hard to code reliably, and that
  students often attributed answers to parameter passing while ignoring scope. This supports the
  vague-explanation work (D22–D23): the interpreter must handle imprecise wording and report when an
  explanation is not informative.
- **Probe format.** Concept-inventory items with answer options mapped to models (Ma et al., 2007;
  Tunnell Wilson et al., 2017) are the established instrument for this kind of diagnosis, which supports
  predict-the-output probes with keyed wrong answers.

## Actions

1. Library check (needs full text): Sorva's 2012 dissertation, Appendix A ("A Misconception Catalogue"),
   and Kallia and Sentance (2019), which reports seven misconceptions about functions. Look for F1, F3, F4.
2. If F4 finds no source, consider broadening it to a documented scope misconception, or keep it and
   state it as a hypothesis.
3. Add an expression-based confirmation probe for A1 (Kohn's form) when confirmation probes are added.
4. Track F1's two directions separately in results; split if they behave differently.
5. Validate the answer keys against real students in the senior project's supervised pilot (consent
   and IRB first).

## References

- Fleury, A. E. (1991). Parameter passing: The rules the students construct. *ACM SIGCSE Bulletin, 23*(1), 283–286. https://doi.org/10.1145/107005.107066
- Chiodini, L., Moreno Santos, I., Gallidabino, A., Tafliovich, A., Santos, A. L., & Hauswirth, M. (2021). A curated inventory of programming language misconceptions. *ITiCSE 2021*. https://doi.org/10.1145/3430665.3456343 (inventory at progmiscon.org)
- James, K., Becker, W., & Minier, M. (2019). Four scope-related misconceptions held by computer science students. *SIGCSE 2019*. https://doi.org/10.1145/3287324.3293860
- Johnson, F., McQuistin, S., & O'Donnell, J. (2020). Analysis of student misconceptions using Python as an introductory programming language. *CEP 2020*. https://doi.org/10.1145/3372356.3372360
- Kallia, M., & Sentance, S. (2019). Learning to use functions: The relationship between misconceptions and self-efficacy. *SIGCSE 2019*, 752–758. https://doi.org/10.1145/3287324.3287377
- Kohn, T. (2017). *Teaching Python programming to novices: Addressing misconceptions and creating a development environment* (Doctoral thesis, ETH Zurich).
- Ma, L., Ferguson, J., Roper, M., & Wood, M. (2007). Investigating the viability of mental models held by novice programmers. *SIGCSE 2007*, 499–503. https://doi.org/10.1145/1227310.1227481
- Madison, S. K. (1995). *A study of college students' construct of parameter passing: Implications for instruction* (Doctoral dissertation, University of Wisconsin). ERIC ED390378.
- Sorva, J. (2012). *Visual program simulation in introductory programming education* (Doctoral dissertation, Aalto University).
- Tunnell Wilson, P., Krishnamurthi, S., & Fisler, K. (2017). Student understanding of aliasing and procedure calls. *SPLASH-E 2017*.
- Teaching materials: Runestone Academy, *Foundations of Python Programming* (Print vs. return) and *CS Principles* teacher notes (procedures not executed at definition; statements after return).
