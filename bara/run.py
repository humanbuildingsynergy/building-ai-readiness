"""Re-run the agent: every block of episodes behind the result tables (level 3; a GPU and Ollama).

    python -m bara.run <block>     sweep | others | agents | mortar | graphs | pairs | premise | unanswerable
    python -m bara.run premise --dry-run       the premise block's questions and episodes, no model
    python -m bara.reproduce agent --smoke     one class, one BATS building, one repeat

Each block writes, under $DERIVED_DIR/agent_runs/<label>/<model>/, one JSON transcript per episode
and a summary per building (summary_<building>.json/.md) in the same format as the deposited runs in
results/agent_runs, so ``python -m bara.tables --runs $DERIVED_DIR/agent_runs`` renders them. A block
whose summary exists is loaded, not re-run (resume after an interruption). Prompt, tools, grader and
guard are those of bara.agent, bara.bank and bara.decompose; the bank is built with seed 0.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from bara import BATS_DIR, DERIVED_DIR, MORTAR_DIR, agent, bank, canon, decompose
from bara.stores import bank_paths, restrict, rung_store, store_ceiling

REF = "qwen3.8-27b-128k"            # the reference agent (Ollama run model; see README)
COMPARE = ["gemma4-31b-128k", "qwen2.5-32b-32k", "gemma2:9b", "llama3.1-8b-128k", "mistral-nemo-12b-128k"]
SWEEP = "large_office__2a_tampa"
SWEEP_PROFILES = ("minimal", "comfort", "standard", "rich")     # metered = rich on published BATS
MORTAR = ["bldg40", "bldg15", "bldg11", "bldg13", "bldg34", "bldg32", "bldg4", "bldg5"]
EQUIP_ENERGY = {"q_comparison_2", "q_status_1", "q_status_2", "e_comparison_2"}
# Classes re-run after a correction to how their questions name locations. Their rows come from the
# re-run blocks (final8c_rich on the sweep building, final8c on the other buildings).
RERUN_CLASSES = ("q_status_1", "q_status_2", "q_comparison_2")
# The 29 classes added to the bank's first 35 to probe the rungs those leave unprobed.
ADDED_CLASSES = ["t_comparison_1", "t_verification_1", "t_diagnosis_1", "t_diagnosis_2", "t_explanation_1",
               "t_explanation_2", "e_comparison_1", "e_diagnosis_1", "e_diagnosis_2", "e_explanation_1",
               "e_explanation_2", "q_comparison_1", "q_summary_1", "q_summary_2", "q_verification_1",
               "q_verification_2", "q_diagnosis_1", "q_diagnosis_2", "q_explanation_1", "q_explanation_2",
               "l_status_1", "l_summary_1", "l_comparison_1", "l_diagnosis_1", "o_status_2", "o_summary_1",
               "o_comparison_1", "o_comparison_2", "o_diagnosis_1"]


def client():
    """The Ollama client every block uses; the model is named in each request."""
    from bara.agent_local import OllamaClient
    return OllamaClient()


def summarize(building: str, model: str, label: str, rows: list[dict], out: Path | None = None) -> dict:
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r["score"])
    n = max(len(rows), 1)
    s = {"building": building, "model": model, "episodes": len(rows),
         "accuracy": sum(r["score"] for r in rows) / n,
         "outcomes": {o: sum(r["outcome"] == o for r in rows)
                      for o in ("answered", "abstained", "refused", "no_answer", "error")},
         "mean_input_tokens": sum(r["input_tokens"] for r in rows) / n,
         "mean_output_tokens": sum(r["output_tokens"] for r in rows) / n,
         "mean_seconds": sum(r["seconds"] for r in rows) / n,
         "per_question": {q: {"n": len(v), "mean": sum(v) / len(v), "min": min(v), "max": max(v)}
                          for q, v in sorted(by_q.items())},
         "rows": rows}
    d = (out or agent._OUT) / label / model.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"summary_{building}.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    L = [f"# Agent run `{label}` — {model} on {building}", "",
         f"{len(rows)} episodes, accuracy {s['accuracy']:.3f}. Outcomes: {s['outcomes']}.",
         f"Mean per episode: {s['mean_input_tokens']:.0f} input tokens, {s['mean_output_tokens']:.0f} "
         f"output tokens, {s['mean_seconds']:.0f} s.", "",
         "| question | n | mean score | min | max |", "|---|---:|---:|---:|---:|"]
    L += [f"| {q} | {v['n']} | {v['mean']:.2f} | {v['min']:.1f} | {v['max']:.1f} |"
          for q, v in s["per_question"].items()]
    (d / f"summary_{building}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return s


def bank_block(building: str, label: str, *, model: str = REF, repeats: int = 1, kg: str = "linked",
               classes: set[str] | None = None, store: Path | None = None, graph: Path | None = None,
               zone_types: set[str] | None = None, limit: int | None = None) -> dict:
    """One block: build the bank (seed 0, 3 instances per class), refuse any question on a rung the
    store's ceiling does not credit (the guard), and run every question *repeats* times."""
    done = agent._OUT / label / model.replace(":", "_") / f"summary_{building}.json"
    if done.exists() and limit is None:
        return json.loads(done.read_text(encoding="utf-8"))
    if store is None:
        graph, store = bank_paths(building, kg)
        bank_graph = bank_paths(building, "linked")[0]
    else:
        bank_graph = graph
    qs = bank.build_bank(bank_graph, store, n=3, seed=0, zone_types=zone_types)
    if classes:
        qs = [q for q in qs if q["class"] in classes]
    decompose.check_credited(qs, store_ceiling(graph, store))
    c, rows = client(), []
    for q, rep in [(q, r) for q in qs for r in range(repeats)][:limit]:
        ep = agent.run_episode(c, model, f"{building}__full__{q['question_id']}__r{rep}", q["text"],
                               q["schema"], agent.Workspace(graph, store), run_label=label)
        score = bank.grade(q, ep.answer) if ep.outcome == "answered" else 0.0
        rows.append({"question": q["class"], "instance": q["question_id"], "domain": q["domain"],
                     "intent": q["intent"], "level": q["level"], "hops": q["hops"], "profile": "full",
                     "repeat": rep, "outcome": ep.outcome, "score": score, "turns": ep.turns,
                     "tool_calls": ep.tool_calls, "input_tokens": ep.input_tokens,
                     "output_tokens": ep.output_tokens, "seconds": ep.seconds,
                     "reported_model": ep.reported_model})
        print(f"  {q['question_id']:22s} r{rep} {ep.outcome:10s} score={score:.1f} {ep.seconds}s", flush=True)
    return summarize(building, model, label, rows)


def others() -> list[str]:
    return sorted(p.name for p in (BATS_DIR / "buildings").iterdir() if p.name != SWEEP)


# ── the blocks ────────────────────────────────────────────────────────────────────────────────
def first_classes() -> set[str]:
    """The bank's first 35 classes: every class except the 29 added ones."""
    return {q.cid for q, _ in bank.BANK} - set(ADDED_CLASSES)


def sweep():
    """Table 8 (tab:sweep) and Figure 7 (fig:decomp): the sweep building at each profile, 3 repeats.
    The bank's first 35 classes go to final1_<profile> (the 3 re-run classes to final8c_rich, where
    the rich profile is the only one that holds their equipment power) and the 29 added classes to
    final8_<profile>."""
    g = bank_paths(SWEEP, "linked")[0]
    for prof in SWEEP_PROFILES:
        st = restrict(SWEEP, canon.PROFILES[prof], prof)
        bank_block(SWEEP, f"final1_{prof}", repeats=3, store=st, graph=g,
                   classes=first_classes() - set(RERUN_CLASSES))
        bank_block(SWEEP, f"final8_{prof}", repeats=3, store=st, graph=g, classes=set(ADDED_CLASSES))
    bank_block(SWEEP, "final8c_rich", repeats=3, store=restrict(SWEEP, canon.PROFILES["rich"], "rich"),
               graph=g, classes=set(RERUN_CLASSES))


def other_buildings():
    """Table 10 (tab:others): the other eight BATS buildings, full store, 1 repeat. The bank's first
    35 classes go to final2 (the 3 re-run classes to final8c) and the 29 added classes to final8b."""
    for b in others():
        bank_block(b, "final2", classes=first_classes() - set(RERUN_CLASSES))
        bank_block(b, "final8b", classes=set(ADDED_CLASSES))
        bank_block(b, "final8c", classes=set(RERUN_CLASSES))


def agents():
    """Figure 8 (fig:agents): each comparison model on the sweep building's full store, the bank's
    first 35 classes, 1 repeat (final3). The reference row is read from the sweep."""
    for m in COMPARE:
        bank_block(SWEEP, "final3", model=m, classes=first_classes())


def mortar():
    for b in MORTAR:
        bank_block(b, "final5", repeats=3 if b in ("bldg40", "bldg15") else 1,
                   graph=MORTAR_DIR / "graphs" / f"{b}.ttl", store=MORTAR_DIR / "stores" / b,
                   zone_types={"VAV", "RVAV"})


def graphs():
    for kg, lab in (("kg.ttl", "final6_published"), ("linked", "final6_linked")):
        bank_block(SWEEP, lab, repeats=3, kg=kg, classes=EQUIP_ENERGY)


def pairs(repeats: int = 20):
    """The paired diagnosis scenarios (BATS v1.0 plus the supplement): every rung, *repeats* repeats.
    Repeats 0-4 go to final4s/rows.json and the rest to final4s_more/rows.json, as deposited."""
    from bara import scenarios
    qs, stores = scenarios.load()
    c, rows = client(), {"final4s": [], "final4s_more": []}
    for q in qs:
        kg, src = stores[q["building"]]
        st = rung_store(kg, src, set(q["streams_in_scope"]), f"final4s__{q['question_id'].replace('#', '_')}")
        for rep in range(repeats):
            label = "final4s" if rep < 5 else "final4s_more"
            ep = agent.run_episode(c, REF, f"{q['building']}__{q['question_id']}__r{rep}", q["text"],
                                   q["schema"], agent.Workspace(kg, st), run_label=label)
            named = (ep.answer or {}).get("cause") if ep.outcome == "answered" else None
            rows[label].append({"scenario": q["scenario"], "rung": q["question_id"].split("#")[1],
                                "streams": q["streams_in_scope"], "answerable": q["answerable"],
                                "repeat": rep, "outcome": ep.outcome, "named": named,
                                "true_cause": q["true_cause"], "seconds": ep.seconds, "turns": ep.turns})
            print(f"  {q['question_id']:10s} r{rep} {ep.outcome:10s} {named}", flush=True)
    for label, rs in rows.items():
        if rs:
            d = agent._OUT / label
            d.mkdir(parents=True, exist_ok=True)
            (d / "rows.json").write_text(json.dumps(rs, indent=1), encoding="utf-8")


PREMISE = ("The reported zone temperature comes from a monitoring sensor. The zone's controller uses its "
           "own thermostat, which is not in the data.")


def premise_questions(manifest: Path | None = None) -> list[dict]:
    """Pair B (s3m, s4) of the paired-scenario manifest with PREMISE stated after its observation. The
    manifest is written to *manifest* (default $DERIVED_DIR/scenarios_supplement_premise.json; the
    deposited copy is results/faults/scenarios_supplement_premise.json)."""
    from bara import scenarios
    from bara.faultbank import questions
    m = json.loads(scenarios.MANIFEST.read_text(encoding="utf-8"))
    m["scenarios"] = [dict(sc, observation=f"{sc['observation']} {PREMISE}") for sc in m["scenarios"]
                      if sc["id"] in ("s3m", "s4")]
    manifest = manifest or DERIVED_DIR / "scenarios_supplement_premise.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return questions(manifest)


def premise(repeats: int = 20, dry_run: bool = False) -> list[str]:
    """Pair B re-run with the monitoring-sensor premise stated (premise_questions): the stores, rungs,
    model and grading of pairs, *repeats* repeats of every rung. Rows go to final4s_premise/rows.json
    and are checkpointed after every episode. With *dry_run*, the episodes are listed, not run."""
    label = "final4s_premise"
    qs = premise_questions()
    ids = [f"{q['building']}__{q['question_id']}__r{rep}" for q in qs for rep in range(repeats)]
    if dry_run:
        for q in qs:
            print(f"{q['building']}__{q['question_id']}  streams {q['streams_in_scope']}\n  {q['text']}")
        print(f"{len(qs)} questions x {repeats} repeats = {len(ids)} episodes", flush=True)
        return ids
    from bara import scenarios
    stores = scenarios.build_supplement()
    done = agent._OUT / label / "rows.json"
    rows = json.loads(done.read_text(encoding="utf-8")) if done.exists() else []
    have = {(r["scenario"], r["rung"], r["repeat"]) for r in rows}
    c = None
    for q in qs:
        kg, src = stores[q["building"]]
        st = rung_store(kg, src, set(q["streams_in_scope"]), f"final4s__{q['question_id'].replace('#', '_')}")
        rung = q["question_id"].split("#")[1]
        for rep in range(repeats):
            if (q["scenario"], rung, rep) in have:
                continue
            c = c or client()
            ep = agent.run_episode(c, REF, f"{q['building']}__{q['question_id']}__r{rep}", q["text"],
                                   q["schema"], agent.Workspace(kg, st), run_label=label)
            named = (ep.answer or {}).get("cause") if ep.outcome == "answered" else None
            rows.append({"scenario": q["scenario"], "rung": rung, "streams": q["streams_in_scope"],
                         "answerable": q["answerable"], "repeat": rep, "outcome": ep.outcome, "named": named,
                         "needed_streams": ep.needed_streams or "", "true_cause": q["true_cause"],
                         "seconds": ep.seconds, "turns": ep.turns})
            done.parent.mkdir(parents=True, exist_ok=True)
            done.write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(f"  {q['question_id']:10s} r{rep} {ep.outcome:10s} {named}", flush=True)
    return ids


def unanswerable():
    """Per profile of the sweep (minimal, comfort, standard): every class the profile cannot support
    but the full store can, 1 instance (question and ground truth from the full store), 3 repeats, on the
    profile's restricted store. The right outcome is an abstention. Rows go to final9/rows.json and
    are checkpointed after every episode."""
    done = agent._OUT / "final9" / "rows.json"
    rows = json.loads(done.read_text(encoding="utf-8")) if done.exists() else []
    have = {(r["profile"], r["instance"], r["repeat"]) for r in rows}
    g, full = bank_paths(SWEEP, "linked")
    c = client()
    for prof in ("minimal", "comfort", "standard"):
        store = restrict(SWEEP, canon.PROFILES[prof], prof)
        posed = {q["class"] for q in bank.build_bank(g, store, n=3, seed=0)}
        for q in [q for q in bank.build_bank(g, full, n=1, seed=0) if q["class"] not in posed]:
            for rep in range(3):
                if (prof, q["question_id"], rep) in have:
                    continue
                ep = agent.run_episode(c, REF, f"{SWEEP}__{prof}__{q['question_id']}__r{rep}", q["text"],
                                       q["schema"], agent.Workspace(g, store), run_label="final9")
                rows.append({"profile": prof, "class": q["class"], "instance": q["question_id"],
                             "domain": q["domain"], "intent": q["intent"], "level": q["level"],
                             "requires": q["requires"], "repeat": rep, "outcome": ep.outcome,
                             "overclaim": ep.outcome == "answered",
                             "answer_right": ep.outcome == "answered" and bank.grade(q, ep.answer) == 1.0,
                             "needed_streams": ep.needed_streams or "", "seconds": ep.seconds, "turns": ep.turns})
                done.parent.mkdir(parents=True, exist_ok=True)
                done.write_text(json.dumps(rows, indent=1), encoding="utf-8")
                print(f"  {prof:8s} {q['question_id']:22s} r{rep} {ep.outcome}", flush=True)


BLOCKS = {"sweep": sweep, "others": other_buildings, "agents": agents, "mortar": mortar,
          "graphs": graphs, "pairs": pairs, "premise": premise, "unanswerable": unanswerable}

if __name__ == "__main__":
    t0 = time.time()
    if "--dry-run" in sys.argv[2:]:
        if sys.argv[1] != "premise":
            sys.exit("--dry-run is available for the premise block only")
        premise(dry_run=True)
        sys.exit(0)
    BLOCKS[sys.argv[1]]()
    print(f"done in {time.time() - t0:.0f} s")
