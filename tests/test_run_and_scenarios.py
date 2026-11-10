"""Black-box tests for the run command (specs/agent.md §6) and the interviewer-check scenarios (§7)."""

import json

import pytest

from mm_agent.check_scenarios import build_scenarios
from mm_agent.prompts import OPENING, SYSTEM_PROMPT
from mm_agent.run import main


def test_offline_run_writes_traces_summary_and_manifest(tmp_path):
    out = tmp_path / "run"
    deciders = ["fixed", "shuffled", "eig", "eig_explain"]
    assert main(["--deciders", *deciders, "--students", "4", "--seed", "3", "--out", str(out)]) == 0
    for d in deciders:
        for i in range(4):
            trace = [json.loads(l) for l in (out / f"{d}_sim-{i:03d}.jsonl").read_text().splitlines()]
            assert trace[0]["kind"] == "header" and trace[-1]["kind"] == "result"
    summary = json.loads((out / "summary.json").read_text())
    assert set(summary) == set(deciders)
    for s in summary.values():
        assert {"exact_match", "brier", "mean_probes", "mean_explanations", "diagnosed_rate",
                "confident_wrong_rate", "per_misconception"} <= set(s)
    assert (out / "summary.md").exists()
    manifest = json.loads((out / "manifest.json").read_text())
    assert {"command", "config", "models"} <= set(manifest)


def test_same_students_for_every_decider(tmp_path):
    out = tmp_path / "run"
    main(["--deciders", "eig", "fixed", "--students", "3", "--seed", "9", "--out", str(out)])
    for i in range(3):
        a = json.loads((out / f"eig_sim-{i:03d}.jsonl").read_text().splitlines()[0])
        b = json.loads((out / f"fixed_sim-{i:03d}.jsonl").read_text().splitlines()[0])
        assert a["planted"] == b["planted"]


def test_run_is_reproducible(tmp_path):
    args = ["--deciders", "eig_explain", "--students", "3", "--seed", "4"]
    main([*args, "--out", str(tmp_path / "a")])
    main([*args, "--out", str(tmp_path / "b")])
    for i in range(3):
        name = f"eig_explain_sim-{i:03d}.jsonl"
        assert (tmp_path / "a" / name).read_text() == (tmp_path / "b" / name).read_text()


@pytest.mark.parametrize("argv", [
    ["--deciders", "interviewer"],
    ["--deciders", "eig_explain", "--interpreter", "none"],
    ["--deciders", "eig", "--student", "llm", "--student-model", "X", "--interpreter", "oracle"],
    ["--deciders", "eig_explain", "--interpreter", "llm"],
])
def test_rejected_combinations_return_2(argv, tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    assert main([*argv, "--students", "1", "--out", str(tmp_path / "x")]) == 2


def test_scenarios_are_built_offline_in_their_stated_states():
    scenarios = {s.name: s for s in build_scenarios()}
    assert list(scenarios) == [f"S{i}" for i in range(1, 9)]
    for s in scenarios.values():
        assert s.messages[0].content == SYSTEM_PROMPT and s.messages[1].content == OPENING
        assert s.messages[-1].content.startswith("Step ")
    assert not scenarios["S1"].session.asked
    assert scenarios["S2"].session.asked and scenarios["S3"].session.asked
    assert scenarios["S4"].session.belief.is_confident(scenarios["S4"].session.config.low, scenarios["S4"].session.config.high)
    s5 = scenarios["S5"].session
    assert len(s5.asked) == 2 and not s5.belief.is_confident(s5.config.low, s5.config.high)
    s6 = scenarios["S6"].session
    assert s6.config.max_probes == 3 and len(s6.asked) == 3
    last_call = [r for r in scenarios["S8"].controller.trace if r["kind"] == "call"][-1]
    assert last_call["accepted"] is False and last_call["policy"] == "P4"


def test_scenario_expectations():
    s = {x.name: x for x in build_scenarios()}
    assert s["S1"].expected("rank_probes", True)
    assert s["S2"].expected("ask_explanation", True) and not s["S2"].expected("submit_diagnosis", False)
    assert s["S4"].expected("submit_diagnosis", True) and not s["S4"].expected("rank_probes", True)
    assert not s["S5"].expected("submit_diagnosis", False) and s["S5"].expected("ask_probe", True)
    assert s["S6"].expected("submit_diagnosis", True) and not s["S6"].expected("ask_probe", False)
    assert s["S7"].expected("ask_probe", True) and not s["S7"].expected("ask_explanation", True)
    assert s["S8"].expected("rank_probes", True) and not s["S8"].expected("ask_probe", False)
