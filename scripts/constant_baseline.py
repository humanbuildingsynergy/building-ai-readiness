"""What a constant guesser would score on the sweep's questions at the metered profile (no runs).

    python scripts/constant_baseline.py      # -> results/final/constant_baseline.md

For each class posed at the metered (= rich) profile of the sweep building, one fixed answer is
graded against every instance of the class with the class's own grader. Three versions:

  best in hindsight  the fixed answer that passes the most instances (it may be set to one of the
                     truths, so a number class passes at least one of its three instances)
  a priori           0 for a number, false for a yes/no, the most common name for an entity
  leave-one-out      the hindsight answer chosen on the other instances, graded on the one left out

The 456 questions of the metered profile are 152 instances asked in 3 repeats; a constant answer is
the same in every repeat, so its share over the instances is its share over the 456.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import RESULTS_DIR, bank, canon  # noqa: E402
from bara import tables as T  # noqa: E402
from bara.stores import bank_paths, restrict  # noqa: E402

OUT = RESULTS_DIR / "final" / "constant_baseline.md"


def names(q) -> set:
    n = lambda s: "".join(ch for ch in str(s).lower() if ch.isalnum())
    return {n(q["gold"])} | {n(a) for a in q.get("aliases", [])}


def passes(qc, q, c) -> bool:
    if qc.answer_type == bank.B:
        return c == q["gold"]
    if qc.answer_type == bank.E:
        return c in names(q)
    return abs(c - q["gold"]) <= max(qc.tol_abs, qc.tol_rel * abs(q["gold"]))


def best(qc, train):
    if qc.answer_type == bank.B:
        cands = [False, True]
    elif qc.answer_type == bank.E:
        cands = sorted({n for q in train for n in names(q)})
    else:
        tol = lambda g: max(qc.tol_abs, qc.tol_rel * abs(g))
        cands = sorted({0.0} | {q["gold"] + d * tol(q["gold"]) for q in train for d in (-1, 0, 1)})
    return max(cands, key=lambda c: sum(passes(qc, q, c) for q in train))


def main() -> None:
    g = bank_paths(T.SWEEP, "linked")[0]
    qs = {q["question_id"]: q for q in bank.build_bank(g, restrict(T.SWEEP, canon.PROFILES["rich"], "rich"), n=3, seed=0)}
    rows = T._first_bank(T.RUNS, "final1_rich", T.SWEEP, "final8c_rich") + T._rows(T.RUNS, "final8_rich", T.SWEEP)
    posed = sorted({r["instance"] for r in rows})
    cl = {q.cid: q for q, _ in bank.BANK}
    agent = {i: sum(r["score"] for r in rows if r["instance"] == i) / sum(1 for r in rows if r["instance"] == i) for i in posed}
    tot = Counter()
    lines = []
    for cid in sorted({i.split("#")[0] for i in posed}):
        inst_ids = [i for i in posed if i.split("#")[0] == cid]
        inst, qc = [qs[i] for i in inst_ids], cl[cid]
        hb = best(qc, inst)
        k_h = sum(passes(qc, q, hb) for q in inst)
        c0 = 0.0 if qc.answer_type == bank.N else False if qc.answer_type == bank.B else hb
        k_p = sum(passes(qc, q, c0) for q in inst)
        k_l = sum(passes(qc, q, best(qc, inst[:j] + inst[j + 1:])) for j, q in enumerate(inst) if len(inst) > 1)
        tot.update(n=len(inst), h=k_h, p=k_p, l=k_l)
        a = sum(agent[i] for i in inst_ids) / len(inst_ids)
        lines.append(f"| {cid} | {qc.answer_type} | {len(inst)} | {k_h} | {k_p} | {k_l} | {a:.2f} | "
                     f"{', '.join(str(q['gold']) for q in inst)} |")
    n = tot["n"]
    L = ["# A constant guesser at the metered profile of the sweep", "",
         "Versions as in scripts/constant_baseline.py. Instances passed out of " f"{n} "
         f"({n * 3} questions with the 3 repeats); the reference agent's accuracy at this profile is in run8.md.", "",
         "| version | instances passed | share |", "|---|---:|---:|",
         f"| best in hindsight | {tot['h']} | {tot['h'] / n:.3f} |",
         f"| a priori (0 / false / most common name) | {tot['p']} | {tot['p'] / n:.3f} |",
         f"| leave-one-out | {tot['l']} | {tot['l'] / n:.3f} |", "",
         "## Per class", "",
         "| class | answer | instances | hindsight | a priori | leave-one-out | agent (mean over repeats) | truths |",
         "|---|---|---:|---:|---:|---:|---:|---|"] + lines
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L[:10]))


if __name__ == "__main__":
    main()
