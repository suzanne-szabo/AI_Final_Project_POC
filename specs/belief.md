# Functional Specification: Belief Evidence (`mm_agent/belief.py`)

Status: Draft v1 (2026-11-09). Extends the week-1 `Belief` class; everything not named here is unchanged.

## 1. Existing behavior that must not change

- `Belief(prior, slip)` holds weights over `PROFILES` (all 256 subsets of the catalog).
- `update(probe, option)` with no confidence argument behaves exactly as in week 1, so
  `python -m mm_agent.poc --students 100 --seed 7 --student-slip 0.15` still writes byte-identical traces
  to `runs/poc-2026-11-04/`. A regression test checks this.
- All sums use `math.fsum` (D11).

## 2. Answer evidence with a confidence rating (D19)

```python
def update(self, probe, option, confidence: int | None = None,
           slip_by_confidence: dict[int, float] | None = None) -> None
```

- When `confidence` is `None` or `slip_by_confidence` is `None`, the slip is `self.slip` (week-1 behavior).
- Otherwise the slip is `slip_by_confidence[confidence]`. A rating outside 1–5 raises `ValueError`.
- The likelihood is unchanged in form: `1 - slip` for the answer the profile predicts, otherwise
  `slip / (len(probe.options()) - 1)`.
- `predictive(probe)` and expected information gain keep using `self.slip` (the agent does not know the
  rating before asking).

**Why:** a confident wrong answer is stronger evidence of a belief than a hesitant one. On a probe with
three possible answers (such as `P07`), the default table makes a matching answer 48 times more likely
under the matching profile than as a slip at rating 5, but only about 3.7 times more likely at rating 1.
The week-1 fixed slip of 0.10 gives 18.

## 3. Explanation evidence (D13, D21)

```python
def update_explanation(self, probe, labels: Iterable[str], sensitivity: float, false_alarm: float) -> None
```

For each misconception `m` in the probe's relevant set (the ids in `probe.keys`), and each profile `p`:

| `m` in `labels` | `m` in `p` | Likelihood factor |
|---|---|---|
| yes | yes | `sensitivity` |
| yes | no | `false_alarm` |
| no | yes | `1 - sensitivity` |
| no | no | `1 - false_alarm` |

The profile's likelihood is the product of these factors over the relevant set; the weights are then
multiplied and renormalized (with `math.fsum`).

- Labels that are not in the probe's relevant set are **ignored** (D21). The caller records them.
- An empty `labels` list is still evidence: it lowers the probability of each relevant misconception.
- Unknown ids raise `ValueError`.
- `0 < false_alarm < sensitivity < 1` is required; otherwise `ValueError`.

**Worked example (must hold to 2 decimals, used by a test):** prior 0.2, slip 0.1, probe `P07`
(relevant: `F2_PARAM_LINKED`). After `update(P07, "6")`, P(F2) = 0.82. Then
`update_explanation(P07, ["F2_PARAM_LINKED"], 0.85, 0.05)` gives 0.99; starting again from 0.82,
`update_explanation(P07, [], 0.85, 0.05)` gives 0.42.

## 4. Helpers

```python
def is_confident(self, low: float, high: float) -> bool   # every marginal <= low or >= high
def estimate(self) -> dict                                  # {"marginals": {...}, "most_likely": [ids], "entropy": float}
```

`most_likely` is the set of ids with marginal > 0.5, in catalog order. Values rounded to 4 decimals.
