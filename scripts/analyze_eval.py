"""HW-12 analysis: every measure and comparison in docs/evaluation-protocol.md, from the retained runs.

Offline (reads runs/ only):

    uv run python scripts/analyze_eval.py

Writes docs/evaluation-results.md (tables for the report) and runs/eval-analysis.json (all numbers).
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RUNS = ROOT / "runs"

from mm_agent.catalog import IDS  # noqa: E402

BINS = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0001)]


# --- loading -------------------------------------------------------------------------------------------

def load(run: str, decider: str) -> dict[str, list[dict]]:
    out = {}
    for f in sorted((RUNS / run).glob(f"{decider}_sim-*.jsonl")):
        recs = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        out[recs[0]["student_id"]] = recs
    if not out:
        raise SystemExit(f"no {decider} traces in runs/{run}")
    return out


def result(recs):
    return recs[-1]


def success(recs) -> bool:
    r = result(recs)
    return r["terminal"] in ("DIAGNOSED", "BUDGET") and bool(r["exact_match"])


def certain_wrong(recs) -> bool:
    r = result(recs)
    return r["terminal"] == "DIAGNOSED" and not r["exact_match"]


def pct(x, d=0):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def quantile(values, q):
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


# --- measures ------------------------------------------------------------------------------------------

def measures(sessions: dict) -> dict:
    rs = [result(s) for s in sessions.values()]
    n = len(rs)
    succ = sum(success(s) for s in sessions.values())
    secs = [r.get("model_seconds") or 0.0 for r in rs]
    calls = [r.get("model_calls") or 0 for r in rs]
    brier = statistics.mean((r["estimate"]["marginals"][m] - (m in r["planted"])) ** 2
                            for r in rs if r.get("estimate") for m in IDS) if any(r.get("estimate") for r in rs) else None
    return {
        "n": n,
        "success": succ,
        "exact_rate": succ / n,
        "certain_wrong": sum(certain_wrong(s) for s in sessions.values()),
        "brier": brier,
        "diagnosed": sum(r["terminal"] == "DIAGNOSED" for r in rs),
        "budget": sum(r["terminal"] == "BUDGET" for r in rs),
        "errors": sum(r["terminal"] in ("ERROR", "STEP_LIMIT") for r in rs),
        "mean_probes": statistics.mean(r["probes_used"] for r in rs),
        "mean_explanations": statistics.mean(r["explanations_used"] for r in rs),
        "mean_calls": statistics.mean(calls),
        "median_seconds": quantile(secs, 0.5),
        "p95_seconds": quantile(secs, 0.95),
        "calls_per_success": (sum(calls) / succ) if succ else None,
        "rejections": sum(r.get("rejections_total") or 0 for r in rs),
    }


def paired(a: dict, b: dict, ids=None) -> dict:
    ids = sorted(set(a) & set(b) if ids is None else ids)
    c = Counter()
    for s in ids:
        x, y = success(a[s]), success(b[s])
        c["both" if x and y else "b only" if y else "a only" if x else "neither"] += 1
    return {"pairs": len(ids), **{k: c[k] for k in ("both", "b only", "a only", "neither")}}


def calibration(sessions: dict) -> dict:
    rows, total, err = [], 0, 0.0
    points = [(r["estimate"]["marginals"][m], m in r["planted"])
              for r in (result(s) for s in sessions.values()) if r.get("estimate") for m in IDS]
    for lo, hi in BINS:
        pts = [(p, y) for p, y in points if lo <= p < hi]
        if not pts:
            rows.append({"bin": f"[{lo:.1f}, {min(hi, 1):.1f}]", "n": 0})
            continue
        mp, obs = statistics.mean(p for p, _ in pts), sum(y for _, y in pts) / len(pts)
        rows.append({"bin": f"[{lo:.1f}, {min(hi, 1):.1f}]", "n": len(pts), "mean_prob": mp, "observed": obs})
        total += len(pts)
        err += len(pts) * abs(mp - obs)
    return {"bins": rows, "calibration_error": err / total if total else None}


def subgroups(sessions: dict) -> dict:
    g = {}
    for s in sessions.values():
        k = min(len(result(s)["planted"]), 3)
        key = {0: "0", 1: "1", 2: "2", 3: "3+"}[k]
        n, ok = g.get(key, (0, 0))
        g[key] = (n + 1, ok + success(s))
    return {k: {"n": n, "success": ok, "rate": ok / n} for k, (n, ok) in sorted(g.items())}


def slip_mechanism(sessions: dict, bank: dict) -> dict:
    """Interpreter judgments on bank explanations, by bank kind: judged right = informative flag and labels."""
    c = Counter()
    for recs in sessions.values():
        for x in recs:
            if x.get("kind") == "call" and x.get("tool") == "ask_explanation" and x.get("accepted"):
                e = bank.get(x["data"].get("explanation"))
                if e is None:
                    continue
                ok = (x["data"]["informative"] == e["informative"]
                      and sorted(x["data"].get("labels") or []) == sorted(e["evident"]))
                c[(e["kind"], ok)] += 1
    kinds = sorted({k for k, _ in c})
    return {k: {"right": c[(k, True)], "total": c[(k, True)] + c[(k, False)]} for k in kinds}


# --- report --------------------------------------------------------------------------------------------

def main() -> int:
    bank = {json.loads(l)["text"]: json.loads(l) for l in (ROOT / "data" / "explanation_bank.jsonl").read_text().splitlines()}
    R = {}

    # C1, C2, C6 (offline, 500 students)
    off = {d: load("eval-offline-500", d) for d in ("fixed", "shuffled", "eig", "eig_explain")}
    off_d38 = load("eval-offline-500-d38", "eig_explain")
    noconf = {"eig": load("eval-offline-500-noconf", "eig"), "eig_explain": load("eval-offline-500-noconf-d38", "eig_explain")}
    novague = {"eig": load("eval-offline-500-novague", "eig"), "eig_explain": load("eval-offline-500-novague-d38", "eig_explain")}
    R["C1"] = {"fixed": measures(off["fixed"]), "shuffled": measures(off["shuffled"]), "eig": measures(off["eig"]),
               "eig_explain_d34": measures(off["eig_explain"]), "eig_explain_d38": measures(off_d38)}
    R["C1_paired_eig_vs_fixed"] = paired(off["fixed"], off["eig"])
    R["C2"] = {"eig": {"with": measures(off["eig"]), "without": measures(noconf["eig"]),
                       "paired": paired(noconf["eig"], off["eig"])},
               "eig_explain": {"with": measures(off_d38), "without": measures(noconf["eig_explain"]),
                               "paired": paired(noconf["eig_explain"], off_d38)}}
    R["C6"] = {}
    for d, orig in (("eig", novague["eig"]), ("eig_explain", novague["eig_explain"])):
        variant = off["eig"] if d == "eig" else off_d38
        p = paired(orig, variant)
        passes = p["both"] + p["a only"]
        R["C6"][d] = {"original_no_vague": measures(orig), "variant_15pct_vague": measures(variant), "paired": p,
                      "pass_to_fail_rate": p["a only"] / passes if passes else None}
    R["calibration_offline_eig_explain_d38"] = calibration(off_d38)
    R["subgroups_offline_eig_explain_d38"] = subgroups(off_d38)

    # C3 (live interpreter, 100 students, three-way)
    c3 = {"baseline": load("eval-baseline-eigexplain-llm-100", "eig_explain"),
          "d34": load("eval-revised-eigexplain-llm-100", "eig_explain"),
          "d38": load("eval-d38-eigexplain-llm-100", "eig_explain")}
    R["C3"] = {k: measures(v) for k, v in c3.items()}
    R["C3_paired_baseline_vs_d34"] = paired(c3["baseline"], c3["d34"])
    R["C3_paired_baseline_vs_d38"] = paired(c3["baseline"], c3["d38"])
    R["C3_mechanism"] = {k: slip_mechanism(v, bank) for k, v in c3.items()}
    R["C3_certain_wrong_ids"] = {k: [s for s in v if certain_wrong(v[s])] for k, v in c3.items()}

    # C4, C5 (full agent, 100 students)
    base_q = load("eval-baseline-qwen-100-paced", "interviewer")
    d38_q = load("eval-d38-qwen-100", "interviewer")
    d38_g = load("eval-d38-gemma-100", "interviewer")
    R["C4"] = {"baseline_qwen": measures(base_q), "d38_qwen": measures(d38_q), "paired": paired(base_q, d38_q),
               "mechanism": {"baseline": slip_mechanism(base_q, bank), "d38": slip_mechanism(d38_q, bank)}}
    first50 = [f"sim-{i:03d}" for i in range(50)]
    R["C5"] = {"qwen_100": measures(d38_q), "gemma_100": measures(d38_g),
               "qwen_first50": measures({s: d38_q[s] for s in first50}),
               "gemma_first50": measures({s: d38_g[s] for s in first50}),
               "paired_first50_qwen_vs_gemma": paired(d38_q, d38_g, first50),
               "paired_100_qwen_vs_gemma": paired(d38_q, d38_g)}
    R["calibration_d38_qwen"] = calibration(d38_q)
    R["subgroups_d38_qwen"] = subgroups(d38_q)

    # C7 (LLM students, 12) vs bank students with the same profiles
    c7 = load("eval-llmstudents-faithful", "interviewer")
    unexpected_in_c7 = sum(1 for recs in c7.values() for x in recs if x.get("kind") == "call"
                           and x.get("tool") == "ask_probe" and x.get("accepted")
                           and x["data"].get("answer_matches") == ["unexpected"])
    R["C7"] = {"llm_students": measures(c7), "bank_same_ids_d38_qwen": measures({s: d38_q[s] for s in c7}),
               "paired_bank_vs_llm": paired({s: d38_q[s] for s in c7}, c7),
               "unexpected_answers_in_c7": unexpected_in_c7}

    # C8 reproducibility (old-code Qwen, same students)
    hw11 = load("baseline-qwen-d32", "interviewer")
    n1 = load("eval-baseline-qwen-100", "interviewer")
    n1_valid = {s: v for s, v in n1.items() if result(v)["terminal"] != "ERROR"}

    def agreement(a, b):
        ids = sorted(set(a) & set(b))
        same_status = sum(success(a[s]) == success(b[s]) for s in ids)
        same_profile = sum(set(result(a[s])["estimate"]["most_likely"]) == set(result(b[s])["estimate"]["most_likely"])
                           for s in ids if result(a[s]).get("estimate") and result(b[s]).get("estimate"))
        return {"pairs": len(ids), "same_success_status": same_status, "same_profile": same_profile}

    R["C8"] = {"hw11_vs_paced": agreement(hw11, base_q), "night1_vs_paced": agreement(n1_valid, base_q)}

    # budget waits
    waits = {}
    for d in ("eval-baseline-qwen-100-paced", "eval-d38-qwen-100", "eval-d38-gemma-100", "eval-d38-eigexplain-llm-100"):
        f = RUNS / d / "budget_waits.jsonl"
        waits[d] = len(f.read_text().splitlines()) if f.exists() else 0
    R["budget_waits"] = waits

    # retained cases (protocol §6 rules)
    def lowest(sessions, pred):
        for s in sorted(sessions):
            if pred(sessions[s]):
                return s
        return None

    R["retained"] = {
        "R1": lowest(d38_q, lambda v: len(result(v)["planted"]) >= 2 and success(v)),
        "R2": lowest(d38_q, lambda v: not result(v)["planted"] and success(v)),
        "R3": next((s for s in sorted(c3["d38"]) if success(c3["d38"][s]) and not success(c3["baseline"][s])), None),
        "R3_alt_lost": next((s for s in sorted(c3["d38"]) if not success(c3["d38"][s]) and success(c3["baseline"][s])), None),
        "R4": lowest(d38_q, certain_wrong) or lowest(d38_q, lambda v: not success(v)),
        "R5": lowest(d38_q, lambda v: result(v)["terminal"] == "BUDGET"),
        "R6": "eval-unsupported/interviewer_sim-000",
        "R7_success": lowest(c7, success),
        "R7_failure": lowest(c7, lambda v: not success(v)),
    }

    (RUNS / "eval-analysis.json").write_text(json.dumps(R, indent=2, sort_keys=True, default=str))
    write_markdown(R)
    print((ROOT / "docs" / "evaluation-results.md").read_text())
    return 0


def row(name, m):
    brier = "n/a" if m["brier"] is None else f"{m['brier']:.3f}"
    return (f"| {name} | {m['n']} | {pct(m['exact_rate'])} | {m['certain_wrong']} | {brier} | "
            f"{m['diagnosed']} / {m['budget']} / {m['errors']} | {m['mean_probes']:.1f} | {m['mean_explanations']:.1f} |")


HEAD = ("| Configuration | Students | Exact match ↑ | Certain but wrong ↓ | Brier ↓ | DIAGNOSED / BUDGET / ERROR | "
        "Probes | Explanations |\n|---|---|---|---|---|---|---|---|")


def ptable(p, a, b):
    return (f"| Pairs | Both succeed | {b} only | {a} only | Neither |\n|---|---|---|---|---|\n"
            f"| {p['pairs']} | {p['both']} | {p['b only']} | {p['a only']} | {p['neither']} |")


def write_markdown(R):
    L = ["# Evaluation Results (HW-12)", "",
         "Generated by `scripts/analyze_eval.py` from the retained runs; all numbers also in `runs/eval-analysis.json`. "
         "Protocol: `docs/evaluation-protocol.md`. ↑ higher is better, ↓ lower is better. "
         "A session succeeds when it ends DIAGNOSED or BUDGET with the planted profile exactly; "
         "certain but wrong = ended DIAGNOSED with a wrong profile.", ""]
    L += ["## C1 Adaptive vs. fixed (offline, oracle interpreter)", "", HEAD]
    for k, name in (("fixed", "Fixed order"), ("shuffled", "Shuffled order"), ("eig", "Information gain"),
                    ("eig_explain_d34", "Information gain + explanations (before D38)"),
                    ("eig_explain_d38", "Information gain + explanations (D38)")):
        L.append(row(name, R["C1"][k]))
    L += ["", "Paired, fixed (a) vs. information gain (b):", "", ptable(R["C1_paired_eig_vs_fixed"], "fixed", "eig"), ""]
    L += ["## C2 Student confidence ratings (offline)", "", HEAD]
    for d in ("eig", "eig_explain"):
        L.append(row(f"{d}, with ratings", R["C2"][d]["with"]))
        L.append(row(f"{d}, without ratings", R["C2"][d]["without"]))
    L += [""]
    L += ["## C3 The refinement, live interpreter, same 100 students", "", HEAD]
    for k, name in (("baseline", "Baseline (3a00ed7)"), ("d34", "D34 only"), ("d38", "D34 + D38")):
        L.append(row(name, R["C3"][k]))
    L += ["", "Paired, baseline (a) vs. D34 + D38 (b):", "", ptable(R["C3_paired_baseline_vs_d38"], "baseline", "D38"), "",
          "Mechanism check (interpreter judgments on bank explanations, right / total):", "",
          "| Kind | Baseline | D34 | D34 + D38 |", "|---|---|---|---|"]
    kinds = sorted(set().union(*[set(v) for v in R["C3_mechanism"].values()]))
    for k in kinds:
        cells = [f"{R['C3_mechanism'][c].get(k, {}).get('right', 0)}/{R['C3_mechanism'][c].get(k, {}).get('total', 0)}"
                 for c in ("baseline", "d34", "d38")]
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", f"Certain-but-wrong students: {R['C3_certain_wrong_ids']}", ""]
    L += ["## C4 Full agent, Qwen interviewer, same 100 students", "", HEAD,
          row("Baseline (3a00ed7)", R["C4"]["baseline_qwen"]), row("D34 + D38", R["C4"]["d38_qwen"]), "",
          ptable(R["C4"]["paired"], "baseline", "D38"), ""]
    L += ["## C5 Interviewer model (D34 + D38 code)", "", HEAD,
          row("Qwen, first 50", R["C5"]["qwen_first50"]), row("Gemma, first 50", R["C5"]["gemma_first50"]),
          row("Qwen, all 100", R["C5"]["qwen_100"]), row("Gemma, all 100", R["C5"]["gemma_100"]), ""]
    L += ["## Efficiency (per session; failures included)", "",
          "| Configuration | Model calls | Median model s | 95th pct model s | Calls per success ↓ | Rejections |",
          "|---|---|---|---|---|---|"]
    for name, m in (("Baseline Qwen", R["C4"]["baseline_qwen"]), ("D38 Qwen", R["C4"]["d38_qwen"]),
                    ("D38 Gemma", R["C5"]["gemma_100"])):
        L.append(f"| {name} | {m['mean_calls']:.1f} | {m['median_seconds']:.1f} | {m['p95_seconds']:.1f} | "
                 f"{m['calls_per_success']:.1f} | {m['rejections']} |")
    L += ["", f"Budget waits (10 min each): {R['budget_waits']}", ""]
    L += ["## C6 Robustness to vague and hedged answers (offline)", "",
          "| Decider | No vague answers | 15% vague | Pass-to-fail rate ↓ |", "|---|---|---|---|"]
    for d in ("eig", "eig_explain"):
        c = R["C6"][d]
        L.append(f"| {d} | {pct(c['original_no_vague']['exact_rate'])} | {pct(c['variant_15pct_vague']['exact_rate'])} | "
                 f"{pct(c['pass_to_fail_rate'], 1)} |")
    L += ["", "## C7 LLM students (12 faithful profiles) vs. bank students with the same profiles", "", HEAD,
          row("LLM students (Gemma), Qwen interviewer", R["C7"]["llm_students"]),
          row("Bank students, same ids (D38 Qwen run)", R["C7"]["bank_same_ids_d38_qwen"]), "",
          f"Unexpected answers given by the LLM students: {R['C7']['unexpected_answers_in_c7']}", ""]
    L += ["## C8 Reproducibility (old code, Qwen, same students)", "",
          "| Comparison | Pairs | Same success status | Same reported profile |", "|---|---|---|---|"]
    for k, name in (("hw11_vs_paced", "HW-11 run vs. night-2 baseline"), ("night1_vs_paced", "Night-1 valid sessions vs. night-2 baseline")):
        c = R["C8"][k]
        L.append(f"| {name} | {c['pairs']} | {c['same_success_status']} | {c['same_profile']} |")
    L += ["", "## Calibration of agent certainty", ""]
    for key, name in (("calibration_d38_qwen", "Full agent, D38 Qwen, 100 students (800 probabilities)"),
                      ("calibration_offline_eig_explain_d38", "Offline eig_explain D38, 500 students (4000 probabilities)")):
        c = R[key]
        L += [f"**{name}.** Calibration error ↓ {c['calibration_error']:.3f}.", "",
              "| Probability bin | Count | Mean probability | Observed share planted |", "|---|---|---|---|"]
        for b in c["bins"]:
            L.append(f"| {b['bin']} | {b['n']} | {pct(b.get('mean_prob'), 1)} | {pct(b.get('observed'), 1)} |"
                     if b["n"] else f"| {b['bin']} | 0 | | |")
        L.append("")
    L += ["## Subgroups by number of planted misconceptions", "", "| Misconceptions | D38 Qwen (100) | Offline eig_explain D38 (500) |",
          "|---|---|---|"]
    for k in ("0", "1", "2", "3+"):
        a, b = R["subgroups_d38_qwen"].get(k), R["subgroups_offline_eig_explain_d38"].get(k)
        fa = f"{a['success']}/{a['n']} ({pct(a['rate'])})" if a else "—"
        fb = f"{b['success']}/{b['n']} ({pct(b['rate'])})" if b else "—"
        L.append(f"| {k} | {fa} | {fb} |")
    L += ["", "## Retained cases (protocol §6)", "", "```", json.dumps(R["retained"], indent=2), "```", ""]
    (ROOT / "docs" / "evaluation-results.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
