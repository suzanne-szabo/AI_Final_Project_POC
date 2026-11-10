"""Write data/explanation_bank.jsonl from the explanations below (specs/students.md §2, D22).

    uv run python scripts/build_explanation_bank.py

The texts are the source of truth; edit them here and rerun. Each probe has, for every misconception in
its answer keys, one clear and one vague explanation; one clear and one vague correct explanation; one
careless-slip explanation; and one non-informative explanation. Vague misconception explanations are
hedged but still recognizable, so their `evident` label is the misconception.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# probe_id -> {"mis": {misconception: (clear, vague)}, "correct": (clear, vague), "slip": text, "none": text}
EXPLANATIONS: dict[str, dict] = {
    "P01": {
        "mis": {
            "A1_LINKED": (
                "When b = a runs, b gets tied to a, so when a changes to 7 later, b changes to 7 along with it.",
                "b kind of goes with a after that line, so I figured they'd both end up 7?"),
            "A2_REVERSED": (
                "b = a puts b's value into a, so a becomes 3 for a moment, then a = 7. b was never changed, so it's still 3.",
                "I read b = a like b hands its number over to a, so b keeps its 3 I think."),
        },
        "correct": (
            "b = a copies a's current value, 5, into b. Changing a to 7 afterwards doesn't touch b.",
            "b got whatever a was at that point, which was 5, and then only a changed after. I think."),
        "slip": "Oops, I mixed up the order of the print and wrote the numbers backwards.",
        "none": "idk, just a guess.",
    },
    "P02": {
        "mis": {
            "A2_REVERSED": (
                "x = y means x gives its 10 to y, so y becomes 10 and x stays 10.",
                "the value moves from x over to y on that line, so both are 10? not totally sure."),
        },
        "correct": (
            "x = y makes x take y's value, 20. y doesn't change, so both print 20.",
            "x picks up y's number so it's 20 and 20 I guess."),
        "slip": "I rushed and copied the starting values instead of tracing line 3.",
        "none": "honestly no idea, it just looked right.",
    },
    "P03": {
        "mis": {
            "A3_COPY_ON_ASSIGN": (
                "b = a makes b its own separate copy of the list, so appending 3 to b leaves a as [1, 2].",
                "b is kind of a duplicate of a, so adding to b shouldn't really change a?"),
            "A2_REVERSED": (
                "b = a gives b's value to a, but b doesn't exist yet, so that line should crash with an error.",
                "it's trying to put b into a before b is made, so I think it errors out."),
        },
        "correct": (
            "a and b are two names for the same list, so appending 3 through b shows up when you print a.",
            "b and a are kind of the same list, so a gets the 3 too I think."),
        "slip": "I forgot the append line when I traced it.",
        "none": "I just went with my gut on this one.",
    },
    "P04": {
        "mis": {
            "A1_LINKED": (
                "other is linked to nums after other = nums, so setting other to [9] changes nums to [9] too.",
                "they're connected after the second line, so whatever other gets nums probably gets."),
        },
        "correct": (
            "other = [9] just points other at a new list. nums still refers to the original [4].",
            "other got a brand new list I think, so nums is still [4]."),
        "slip": "I misread the last line and printed other instead of nums.",
        "none": "no clue, that's just what came to mind.",
    },
    "P05": {
        "mis": {
            "F1_RETURN_IS_PRINT": (
                "f prints 3, and printing is how it gives the value back, so y is 3 and print(y) shows 3 again.",
                "f puts out the 3, so y should be 3 too I guess, and then it prints again."),
        },
        "correct": (
            "f prints 3 but never returns anything, so it gives back None, and printing y shows None.",
            "there's no return so y is kind of nothing, None I think."),
        "slip": "I lost track of which line printed what.",
        "none": "I'm not sure how to explain it.",
    },
    "P06": {
        "mis": {
            "F1_RETURN_IS_PRINT": (
                "double(4) returns 8, and returning shows the number on the screen, then done gets printed.",
                "the 8 comes out when it returns, I think, and then done."),
        },
        "correct": (
            "double(4) returns 8 but nothing prints it, so the value is thrown away and only done appears.",
            "the 8 just goes back and nobody uses it, so it's only done? probably."),
        "slip": "I didn't read the whole program carefully and guessed the output.",
        "none": "it's what I'd expect, that's all.",
    },
    "P07": {
        "mis": {
            "F2_PARAM_LINKED": (
                "x is passed into bump as n, and n = n + 1 changes x as well, so x prints 6.",
                "bump adds one to the number you give it, so x goes up to 6? kind of."),
        },
        "correct": (
            "n is a separate local name inside bump; rebinding n to 6 doesn't affect x, which is still 5.",
            "the change only happens inside bump I think, so x is still 5."),
        "slip": "I typed the wrong number by accident.",
        "none": "idk really.",
    },
    "P08": {
        "mis": {
            "F3_DEF_RUNS_BODY": (
                "The program hits greet first, so it prints hi, and then it prints start.",
                "hi comes first since it's at the top I think, then start."),
        },
        "correct": (
            "def only defines greet; it is never called, so the only output is start.",
            "greet isn't really used anywhere, so just start? I think."),
        "slip": "I mixed this up with the previous program.",
        "none": "seems right to me, can't say why.",
    },
    "P09": {
        "mis": {
            "F3_DEF_RUNS_BODY": (
                "Python runs top to bottom, so the print inside show runs first, then B, then show() prints A again.",
                "A shows up at the top since that's where it's written, then B, then A from the call maybe."),
        },
        "correct": (
            "Defining show prints nothing; B prints first, and then calling show() prints A.",
            "B first because show only runs at the end when it's called, I'm fairly sure."),
        "slip": "I swapped the two lines when I wrote my answer.",
        "none": "just a feeling.",
    },
    "P10": {
        "mis": {
            "F4_LOCALS_OUTLIVE_CALL": (
                "make() set secret to 42, and it still exists after the call, so print(secret) shows 42.",
                "secret got set to 42 in there, so it should still be 42 afterwards I think."),
        },
        "correct": (
            "secret is local to make and disappears when the call ends, so print(secret) raises a NameError.",
            "secret only lives inside make I think, so it can't be printed out here."),
        "slip": "I didn't notice which variable was printed.",
        "none": "I don't know, I just picked one.",
    },
    "P11": {
        "mis": {
            "F4_LOCALS_OUTLIVE_CALL": (
                "setup returns 4 into result, and value is still 3 from inside the function, so it prints 4 3.",
                "value was 3 in setup so it's probably still around, so 4 and 3."),
        },
        "correct": (
            "value is local to setup and is gone after it returns, so print(result, value) fails with a NameError.",
            "value belongs to the function, so outside it doesn't really exist? so error."),
        "slip": "I lost track partway through tracing.",
        "none": "not really sure, sorry.",
    },
    "P12": {
        "mis": {
            "F5_RUNS_AFTER_RETURN": (
                "The function returns n but keeps going to the next line, so after is printed, and then 2.",
                "after still runs I think since it's in the function, then the 2."),
        },
        "correct": (
            "return ends check immediately, so print('after') never runs; only 2 is printed.",
            "the line after return gets skipped I'm pretty sure, so just 2."),
        "slip": "I put the lines in the wrong order by mistake.",
        "none": "that was a guess honestly.",
    },
    "P13": {
        "mis": {
            "F5_RUNS_AFTER_RETURN": (
                "5 is positive so it hits return pos, but the function keeps going and the last return replaces it with non-pos.",
                "the last return is the one that counts in the end I think, so non-pos."),
        },
        "correct": (
            "x > 0 is true, so return 'pos' ends the function right there and pos is printed.",
            "it returns pos and stops? I think it doesn't get to the other one."),
        "slip": "I misread 5 as a negative number.",
        "none": "can't explain it, it just seemed right.",
    },
    "P14": {
        "mis": {
            "A3_COPY_ON_ASSIGN": (
                "items is a copy of data inside the function, so appending 1 to items leaves data empty.",
                "the function gets its own version of the list I think, so data stays []."),
        },
        "correct": (
            "items and data refer to the same list, so appending through items changes data to [1].",
            "it's the same list being passed in, so data gets the 1 probably."),
        "slip": "I forgot that add was called before the print.",
        "none": "I'm guessing here.",
    },
    "P15": {
        "mis": {
            "F2_PARAM_LINKED": (
                "triple sets n to 6, and since n is x, x becomes 6 too, and y gets 6.",
                "x gets tripled by the function so x and y are both 6 I think."),
        },
        "correct": (
            "n is local; rebinding it doesn't change x, so x is still 2 and y is the returned 6.",
            "x stays 2 since only n changed inside, and y is 6, pretty sure."),
        "slip": "I wrote the numbers in the wrong order.",
        "none": "no real reason, just what I wrote.",
    },
}


def build() -> list[dict]:
    import sys
    sys.path.insert(0, str(ROOT))
    from mm_agent.probes import BY_ID

    rows: list[dict] = []

    def add(**row):
        rows.append({"id": f"B{len(rows) + 1:03d}", **row})

    for probe_id, spec in EXPLANATIONS.items():
        probe = BY_ID[probe_id]
        assert set(spec["mis"]) == set(probe.keys), probe_id
        for m, (clear, vague) in spec["mis"].items():
            for clarity, text in (("clear", clear), ("vague", vague)):
                add(probe_id=probe_id, kind="misconception", misconception=m, answer=probe.keys[m],
                    clarity=clarity, holds=[m], evident=[m], informative=True, text=text)
        for clarity, text in zip(("clear", "vague"), spec["correct"]):
            add(probe_id=probe_id, kind="correct", misconception=None, answer=probe.correct,
                clarity=clarity, holds=[], evident=[], informative=True, text=text)
        add(probe_id=probe_id, kind="slip", misconception=None, answer=None,
            clarity="clear", holds=[], evident=[], informative=True, text=spec["slip"])
        add(probe_id=probe_id, kind="none", misconception=None, answer=None,
            clarity="none", holds=None, evident=[], informative=False, text=spec["none"])
    return rows


def main() -> int:
    rows = build()
    texts = [r["text"] for r in rows]
    assert len(texts) == len(set(texts)), "duplicate texts"
    out = ROOT / "data" / "explanation_bank.jsonl"
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"wrote {len(rows)} entries to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
