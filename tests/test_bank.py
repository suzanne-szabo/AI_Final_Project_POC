"""Black-box tests for the explanation bank and interpreter test sets (specs/students.md §2, D22)."""

import json
from pathlib import Path

from mm_agent.catalog import IDS
from mm_agent.probes import BANK, BY_ID
from mm_agent.students import ExplanationBank

DATA = Path(__file__).resolve().parent.parent / "data"


def load_jsonl(name):
    return [json.loads(line) for line in (DATA / name).read_text().splitlines() if line.strip()]


def test_bank_loads_with_full_coverage():
    bank = ExplanationBank.load(DATA / "explanation_bank.jsonl")
    assert bank.missing() == []
    for probe in BANK:
        for m in probe.keys:
            for clarity in ("clear", "vague"):
                assert bank.entries(probe.id, "misconception", m, clarity)
        for clarity in ("clear", "vague"):
            assert bank.entries(probe.id, "correct", clarity=clarity)
        assert bank.entries(probe.id, "slip")
        assert bank.entries(probe.id, "none")


def test_bank_fields_are_consistent():
    rows = load_jsonl("explanation_bank.jsonl")
    assert len(rows) >= 94
    assert len({r["text"] for r in rows}) == len(rows)
    for r in rows:
        probe = BY_ID[r["probe_id"]]
        if r["kind"] == "misconception":
            assert r["answer"] == probe.keys[r["misconception"]]
            assert r["holds"] == [r["misconception"]]
            assert set(r["evident"]) <= set(r["holds"])
        elif r["kind"] == "correct":
            assert r["answer"] == probe.correct and r["holds"] == [] and r["evident"] == []
        elif r["kind"] == "slip":
            assert r["answer"] is None and r["holds"] == [] and r["evident"] == []
        else:
            assert r["kind"] == "none" and r["clarity"] == "none"
            assert r["holds"] is None and r["evident"] == [] and r["informative"] is False
        if r["clarity"] == "clear":
            assert r["informative"] is True


def test_lookup_and_bad_bank(tmp_path):
    bank = ExplanationBank.load(DATA / "explanation_bank.jsonl")
    row = load_jsonl("explanation_bank.jsonl")[0]
    entry = bank.lookup(row["text"])
    assert entry is not None and entry.id == row["id"] and entry.probe_id == row["probe_id"]
    assert bank.lookup("text that is not in the bank") is None
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({**row, "kind": "nonsense"}) + "\n")
    try:
        ExplanationBank.load(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("a bad kind must raise ValueError")


def test_interpreter_test_sets():
    clean, vague = load_jsonl("explanations.jsonl"), load_jsonl("explanations_vague.jsonl")
    assert len(vague) >= 30
    for r in clean + vague:
        assert isinstance(r["informative"], bool)
        assert all(m in IDS for m in r["labels"])
        if not r["informative"]:
            assert r["labels"] == []
    assert {r["kind"] for r in vague} >= {"vague", "none", "mixed", "partly_wrong"}
    e22 = next(r for r in clean if r["id"] == "E22")
    assert e22["informative"] is False and e22["labels"] == []


def test_no_text_is_shared_between_bank_and_test_sets():
    bank = {r["text"] for r in load_jsonl("explanation_bank.jsonl")}
    tests = {r["explanation"] for r in load_jsonl("explanations.jsonl") + load_jsonl("explanations_vague.jsonl")}
    assert not bank & tests
