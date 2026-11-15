# Beginner Sources: How Real Novices Talk About the Notional Machine

Status: first reading pass, 2026-11-15 (D33). Owner: Suzanne Szabo. Collected by Claude from public
Q&A pages. Related: `docs/student-simulator-plan.md` §3.5, `docs/catalog-sources.md`,
`docs/notional-machine.md`.

**Purpose.** Give the LLM-student personas real beginner wording, attitudes and confusions, instead of
wording invented by the catalog's author (the circularity noted in D7). It also adds practitioner-level
evidence for catalog entries and suggests new probes.

**Rules followed (D33):**
- Every entry gives a link and a paraphrase. Short quoted phrases are rare and attributed by link.
- No usernames are recorded.
- Pages were read one at a time, through a search engine and fetches of single pages. Reddit pages
  could not be opened directly (the mirror sites returned a bot check), so Reddit entries rely on the
  search-result text only. Nothing was scraped.

**Interpretation.** These are illustrations, not frequencies. People who post questions are a
self-selected group, many posts come from people with C, C++ or Java habits, and several sources are
answers by experienced helpers rather than beginners. A source that is a teacher's or helper's note is
marked *(helper)*.

Access date for every link: 2026-11-15.

---

## 1. Evidence per misconception

### A1_LINKED: after `b = a`, the names stay tied

- **Linked integers, a chained assignment.** A beginner wrote `a = b = 0`, then `b = 1`, and expected
  `a` to follow `b`. Their reasoning was that `a` "refers to" `b`, so changing `b` should carry `a` with
  it. They were then puzzled that a list behaved differently.
  [SO 66212267](https://stackoverflow.com/questions/66212267/why-is-the-value-in-a-not-affected-by-the-change-in-b)
  — the clearest A1 example found, and the basis for probe idea N1 (Section 3).
- **A self-refuting conjecture.** A forum poster guessed that two names are the same object. Changing
  one and checking the other seemed to refute the guess, and they ended the post saying they were now
  confused. [python-forum post 90029](https://python-forum.io/post-90029.html)
- **The int and list contrast.** A post asks why `b` changed after `.append` but `d` did not change after
  `c = 8`. [SO 59532255](https://stackoverflow.com/questions/59532255/why-did-one-value-change-but-the-second-value-did-not)
  The same contrast appears in a Treehouse question.
  [Treehouse](https://teamtreehouse.com/community/equality-question-with-using-splices-and-lists-vs-variables-numbers)

**Implication.** A1 is real, but beginners usually reach it *by generalizing from lists*: they saw
aliasing once and now expect every `b = a` to tie the names. A1 personas should sound like someone who
has half-learned "Python uses references".

### A2_REVERSED: `x = y` moves the value left to right

- No beginner post was found stating the reversed direction outright. The evidence is indirect:
  - teaching texts warn that beginners read `=` as mathematical equality and suggest reading it as a
    left-pointing arrow or as "gets"
    ([UVM CS1210](https://uvm.edu/~cbcafier/cs1210/book/04_variables,_statements,_and_expressions/variables.html),
    [Waterloo CS114](https://student.cs.uwaterloo.ca/~cs114/book/ch-reassignment.html) *(helper)*);
  - a beginner said assignment and equality seem exactly the same to them
    ([programming.dev thread](https://deddit.petersanchez.com/g/python@programming.dev/p/B4bTLndFk438cmVb44-Confused-about-logical-operators-ie-comparison-o)).

**Implication.** The A2 source stays the research literature (D26, strong). A2 personas should treat
`=` as symmetric ("they're equal now") and pick a direction inconsistently, rather than state a rule.

### A3_COPY_ON_ASSIGN: `b = a` copies a list

This is the most common confusion found, by far. Typical posts:

- `b = a`, then `b.insert(...)`: why did `a` change?
  [SO 75064277](https://stackoverflow.com/questions/75064277)
- A learner thought appending to `b` would work on a copy, and remembered the topic from a course long
  ago. [CodeAbbey forum](https://codeabbey.com/index/forum_topic/99a82fbcb49375334d71e2b864f8525c)
- "Make b equal to a, then change b without touching a."
  [SO 62512776](https://stackoverflow.com/questions/62512776/python-3-comparing-list-variables)
- `list_b = list_a`, then `pop()` on `list_b`: why did `list_a` lose an element?
  [python-forum 31031](https://python-forum.io/thread-31031.html)
- Copying through a parameter: a beginner was surprised that a list changed after a function call. They
  argued that the parameter is a local variable, so changes should stay in the function.
  [SO 49455331](https://stackoverflow.com/questions/49455331/python-global-variable-contradiction);
  also [SO 54645701](https://stackoverflow.com/questions/54645701/local-and-global-lists-in-python).
- A teacher's report that students with a C background expect `y = x` to copy, and are surprised when
  `x.append` shows up in `y`. [Lerner](https://lerner.co.il/2019/06/18/understanding-python-assignment/) *(helper)*

**Implication.** A3 personas are often *confident*: the copy model feels natural and comes from math or
C. Their explanations use words like "copy", "its own list", "separate", and "the parameter is local so
it's safe". The parameter version is the same belief as the assignment version (it supports A3 covering
P14).

### F1_RETURN_IS_PRINT: `return` and `print` are the same

- Many posts say both "give the answer" or "return values":
  - [python-forum 5320](https://python-forum.io/archive/index.php/thread-5320.html)
  - [SO 66930179](https://stackoverflow.com/questions/66930179/what-should-i-use-print-or-return-in-python)
  - [python-forum 27444](https://python-forum.io/thread-27444.html)
  - [discuss.python.org 48498](https://discuss.python.org/t/asking-for-help-understanding-the-difference-between-return-and-print-in-function/48498)
  - an r/learnpython post comparing a function that prints with one that returns (search-result text
    only: [r/learnpython hvqo6w](https://www.reddit.com/r/learnpython/comments/hvqo6w/return_vs_call_function/)).
- **Why it persists, a key insight for personas.** In the interactive shell, a returned value is echoed,
  so `return` *looks* like printing. A teacher on the Python mailing list noted that first-time students
  see no visual difference.
  [python-list 2022-05](https://www.python.org/pipermail/python-list/2022-May/906462.html) *(helper)*
  The same explanation is in [python-forum 5320](https://python-forum.io/archive/index.php/thread-5320.html).
- **The reverse direction.** A beginner called a returning function with no `print` and asked why the
  code "won't work", most likely expecting output. (Search-result text only:
  [r/learnpython 1kycsnp](https://www.reddit.com/r/learnpython/comments/1kycsnp/i_wonder_why_this_wont_work/).)
- An introductory e-book states plainly that beginners find the distinction confusing.
  [Learning Python, print vs. return](https://learningpython-today.github.io/pip2/Functions/Printvs.return.html) *(helper)*

**Implication.** This is strong practitioner evidence for F1 (D26 rated it practitioner). Personas
should cite the shell ("when I ran it, it showed the number"), and should be unsure *where* the value
goes rather than hold a precise rule.

### F2_PARAM_LINKED: reassigning a parameter changes the caller's variable

- A beginner reassigned a parameter inside a function and expected the caller's variable to change. They
  then asked how to make such changes "permanent".
  [SO 53249829](https://stackoverflow.com/questions/53249829/python-keep-changes-on-a-variable-made-within-a-function)
- A new learner asked why a list parameter "worked" but a string parameter did not. They felt both
  functions did the same thing.
  [python-forum 40495](https://python-forum.io/printthread.php?tid=40495)
- A Stack Overflow title calls Python "unfair" for treating a list and a plain variable differently.
  [SO 9323739](https://stackoverflow.com/questions/9323739/python-is-unfair-its-treating-list-and-a-non-list-variable-with-partiality)
- Several forum threads about changing a variable "outside the function" end with helpers suggesting
  `global`. [python-forum 21115](https://python-forum.io/thread-21115.html),
  [python-forum 1455](https://python-forum.io/archive/index.php/thread-1455.html)

**Implication.** F2 holders often *also* know that lists change through a function. They overgeneralize
from that, which is the mirror image of A3. Their wording: "I passed x in, so changing n changes x",
"it should save the change". The "Python is unfair" frustration is a good emotional note for a persona.

### F3_DEF_RUNS_BODY: the body runs at `def`

- Several beginners report that "nothing happens" or "nothing prints" when they run a file that only
  defines functions. They expected defining to run the body.
  - [JetBrains community](https://intellij-support.jetbrains.com/hc/en-us/community/posts/207376025/comments/207214395)
  - [python-forum post 128981](https://python-forum.io/post-128981.html)
  - [python-forum post 8213](https://python-forum.io/post-8213.html), from a C++ background
  - [SO 15446560](https://stackoverflow.com/questions/15446560/main-function-doesnt-run-when-running-script)
- Teaching texts make the point explicitly: a definition only files the body away, and each call runs it
  again. [AlgoMaster](https://algomaster.io/learn/python/functions-basics) *(helper)*

**Implication.** This is new practitioner-to-forum evidence for F3 (D26: practitioner). In the posts,
the belief shows up as an expectation of output from the definition. That matches P08 (`hi | start`).
Personas should say the function "should print hi because it's in the code above".

### F4_LOCALS_OUTLIVE_CALL: local names survive the call

- A beginner set a variable inside a function and expected to use it afterwards. Outside, it "reverted"
  to the earlier value, or raised "not defined" when no earlier value existed.
  [python-forum 21115](https://python-forum.io/thread-21115.html)
- A forum post describes print as if "locked" to the function, because the value made inside was not
  available outside. [python-forum 42723](https://python-forum.io/thread-42723.html)
- A beginner believed local variables are "set to None" by `return`, rather than disappearing with the
  call. [python-forum 44454](https://python-forum.io/thread-44454-newpost.html)
- Teaching notes describe the NameError as surprising to novices.
  [Runestone](https://runestone.academy/ns/books/published/foppff/functions_variables-and-parameters-are-local.html),
  [blogbyaiden](https://blogbyaiden.netlify.app/programming/python-writing-functions-scope-of-variable) *(helper)*

**Implication.** This is the first direct beginner evidence for F4 (D26: weak). It also shows a
*variant* the catalog does not model: assigning inside a function is believed to update the global with
the same name (`value = 5` inside `f` changes the global `value`). See N3 in Section 3.

### F5_RUNS_AFTER_RETURN: execution continues past `return`

- A beginner asked why a print placed after `return` did not run.
  [python-forum 23749](https://python-forum.io/thread-23749-post-102419.html)
- A learner reported that code below `return` still executed, against what their lesson said, and asked
  for confirmation.
  [Sololearn 1259112](https://www.sololearn.com/en/Discuss/1259112/after-using-return-statement-it-wont-execute-any-of-the-below-statement-right)
- A learner was puzzled that a function stopped at a `return` inside a loop, when more `if` statements
  came after it. [python-forum 44454](https://python-forum.io/thread-44454-newpost.html)
- A teacher's note names this exact misconception: students miss that `return` is also the exit point.
  [Runestone Teacher Note](https://runestone.academy/ns/books/published/TeacherCSP/CSPNameNames/noteAfterReturn.html) *(helper)*

**Implication.** This is good practitioner support for F5, especially for the *early return* form (P13).
Personas: "it returns pos but then keeps checking the rest".

---

## 2. Personality and style traits seen across posts

These traits feed the `style` option and the persona prompts.

| Trait | What it looks like in the posts | Use in personas |
|---|---|---|
| Apologetic, low confidence | "probably a stupid question", "sorry for the noob question", "I just started" | `hedging` style; confidence 1–2 even when the belief is firm |
| Frustrated or blaming the language | Python is "broken" or "unfair"; "variable changes for no reason" | Confident wrong belief; confidence 4–5; explanation blames the language |
| Transfer from another language | C, C++ or Java habits: `=` copies, a function runs when written | Confident A3/F3; explanation mentions "in C this would copy" |
| Shell-based reasoning | "when I ran it, it showed the number" | F1 explanations cite what they saw in the shell |
| Conjecture, then confusion | proposes a rule, tests it, ends "now I am confused" | Mixed or partly wrong explanations; inconsistent answers across probes |
| Terse | code plus "why doesn't this work?" with no reasoning | `terse` style; short, low-information explanations |
| Half-learned jargon | "points to", "reference", "local so it's safe", "permanent" | Vocabulary that sounds right but supports a wrong rule (hard cases for the interpreter) |

---

## 3. Probe and catalog ideas from the reading

These are candidates, not adopted. Adding probes changes the bank and the information-gain ranking, so
they are for the final week or the senior project.

| Id | Idea | Correct | Key | Why |
|---|---|---|---|---|
| N1 | `a = b = 0` / `b = 1` / `print(a, b)` | `0 1` | A1: `1 1` | The integer A1 probe that D26 asked for; taken directly from SO 66212267 |
| N2 | `def f(items):` / `items = [9]` / `data = [1]` / `f(data)` / `print(data)` | `[1]` | F2: `[9]` | Separates F2 (rebinding links) from "lists always change"; the list/string confusion in python-forum 40495 |
| N3 | `value = 1` / `def f():` / `value = 5` / `f()` / `print(value)` | `1` | new: `5` | A possible new misconception: *local assignment writes the global* (python-forum 21115). It is related to F4 but not the same |
| N4 | Shell vs. script `return`: show a REPL transcript | — | — | F1 personas reason from the shell; a probe could ask what a script prints vs. what the shell shows |

---

## 4. What changes in the plan

1. **Persona prompts** (`LLMStudent`): each misconception's description gains the beginner phrasing
   from Section 1, and the instruction to reason the way such a student would. Example: an A3 student
   says the parameter is "local so it's safe".
2. **`style`** (`clear`, `terse`, `hedging`), with attitudes from Section 2, chosen per student.
3. **Interpreter test cases**: the half-learned-jargon trait gives realistic hard cases ("it points to
   the same thing so it should change too" from an A1 holder on an integer probe).
4. **Catalog evidence** (`docs/catalog-sources.md`): F1, F3, F4 and F5 gain forum-level support.
   F4 moves from weak to practitioner if Suzanne agrees.
