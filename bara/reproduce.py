"""The three reproduction levels, each checked against the deposited results.

    python -m bara.reproduce tables           level 1: every table in results/final from the deposited
                                              run summaries (CPU, seconds, no download)
    python -m bara.reproduce census           level 2: the census of 45 real graphs and every ceiling,
                                              from the public data (scripts/fetch_data.py first)
    python -m bara.reproduce agent --smoke    level 3: one agent episode on BATS with the local reference
                                              model (Ollama and a GPU; scripts/fetch_data.py --bats first)

Each level writes into $DERIVED_DIR/reproduce/<level>/ and compares with the deposit: files must be
identical (level 1 and 2); the smoke episode's question must equal the deposited one and both
episodes must grade to the deposited score (level 3). The exit code is 0 only when all checks pass.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import json
import sys
from pathlib import Path

from bara import DERIVED_DIR, RESULTS_DIR

OUT = DERIVED_DIR / "reproduce"
# the smoke episode: one of the bank's first 35 classes on a BATS building, full store, the deposited
# first repeat
SMOKE = {"building": "large_office__4a_newyork", "label": "final2", "instance": "t_status_1#1"}


def _same(new: Path, old: Path) -> bool:
    ok = new.exists() and old.exists() and filecmp.cmp(new, old, shallow=False)
    print(f"  {'identical' if ok else 'DIFFERENT'}  {old.relative_to(RESULTS_DIR.parent)}")
    return ok


def tables() -> bool:
    from bara.tables import build_all
    out = OUT / "tables"
    if out.exists():
        shutil.rmtree(out)                  # only the tables of this build are compared
    names = build_all(out=out)
    print(f"level 1: {len(names)} tables from results/agent_runs")
    return all([_same(out / n, RESULTS_DIR / "final" / n) for n in names])


def census() -> bool:
    from bara import census as C
    from bara import stores
    out = OUT / "census"
    rep = C.build(out)
    print(f"level 2: census of {rep['n']} graphs ({rep['n_with_data']} with linked series)")
    ok = [_same(out / f"census_v2.{x}", RESULTS_DIR / "census" / f"census_v2.{x}") for x in ("json", "md")]
    stores.compute_ceilings(path=out / "ceilings.json")
    ok.append(_same(out / "ceilings.json", stores.CEILINGS))
    c = json.loads((out / "ceilings.json").read_text(encoding="utf-8"))
    sweep = c["large_office__2a_tampa"]
    print("  sweep building by profile:", ", ".join(f"{p} {sweep[p]['achieved']}/{sweep[p]['total']}"
                                                    for p in ("minimal", "comfort", "standard", "rich")),
          "| full stores:", ", ".join(f"{b} {v['full']['achieved']}" for b, v in sorted(c.items())))
    return all(ok)


def agent_smoke(model: str | None = None) -> bool:
    from bara import agent, bank
    from bara.run import REF, client
    from bara.stores import bank_paths
    model = model or REF
    b, label, inst = SMOKE["building"], SMOKE["label"], SMOKE["instance"]
    runs = RESULTS_DIR / "agent_runs" / label / REF
    row = next(r for r in json.loads((runs / f"summary_{b}.json").read_text(encoding="utf-8"))["rows"]
               if r["instance"] == inst and r["repeat"] == 0)
    (saved_path,) = runs.glob(f"{b}__full__{inst}__r0_*.json")
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    graph, store = bank_paths(b, "linked")
    q = next(q for q in bank.build_bank(graph, store, n=3, seed=0) if q["question_id"] == inst)
    # transcripts start at the agent's first turn, so the rebuilt question is matched by the entity
    # it names (identifiers with an underscore, e.g. the zone), which the deposited agent looked up
    names = [w.strip("?,.") for w in q["text"].split() if "_" in w]
    seen = json.dumps(saved["transcript"])
    checks = {"rebuilt question names what the deposited agent looked up": bool(names) and all(n in seen for n in names),
              "deposited answer regrades to its score": bank.grade(q, saved["answer"]) == row["score"]}
    print(f"level 3 (smoke): {b} {inst}, {model}; deposited: {row['outcome']}, score {row['score']}")
    agent._OUT = OUT / "agent"
    ep = agent.run_episode(client(), model, f"{b}__full__{inst}__r0", q["text"], q["schema"],
                           agent.Workspace(graph, store), run_label="smoke")
    score = bank.grade(q, ep.answer) if ep.outcome == "answered" else 0.0
    print(f"  new episode: {ep.outcome}, answer {ep.answer}, score {score}, {ep.turns} turns, {ep.seconds} s")
    checks["new episode grades to the deposited score"] = score == row["score"]
    for k, v in checks.items():
        print(f"  {'pass' if v else 'FAIL'}  {k}")
    return all(checks.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("level", choices=["tables", "census", "agent"])
    ap.add_argument("--smoke", action="store_true", help="level 3: the single smoke episode (the only mode)")
    ap.add_argument("--model", help="Ollama model (default: the reference model)")
    a = ap.parse_args()
    if a.level == "agent" and not a.smoke:
        ap.error("level 3 runs one episode with --smoke; the full blocks are `python -m bara.run <block>`")
    ok = {"tables": tables, "census": census}.get(a.level, lambda: agent_smoke(a.model))()
    print("all checks pass" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
