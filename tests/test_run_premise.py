"""The premise block of bara.run builds pair B with the premise stated, as deposited (no agent, no GPU)."""
import json

from bara import RESULTS_DIR, run
from bara.scenarios import MANIFEST

RUNS = RESULTS_DIR / "agent_runs" / "final4s_premise"


def _no_agent(model):
    raise AssertionError("the dry run must not start an agent")


def test_premise_block_builds_the_80_deposited_episodes_with_the_premise_after_the_observation(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "client", _no_agent)
    monkeypatch.setattr(run, "DERIVED_DIR", tmp_path)
    ids = run.premise(dry_run=True)
    # the manifest the block writes is the deposited one
    written = json.loads((tmp_path / "scenarios_supplement_premise.json").read_text(encoding="utf-8"))
    deposited = RESULTS_DIR / "faults" / "scenarios_supplement_premise.json"
    assert written == json.loads(deposited.read_text(encoding="utf-8"))
    # the episodes are those of the deposited transcripts
    episodes = sorted(json.loads(f.read_text(encoding="utf-8"))["question_id"] for f in RUNS.glob("*/*.json"))
    assert len(ids) == 80 and sorted(ids) == episodes
    # the premise follows the observation, once, before the question proper
    obs = {sc["id"]: sc["observation"] for sc in json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]}
    qs = run.premise_questions(tmp_path / "m.json")
    assert sorted(q["question_id"] for q in qs) == ["s3m#rung0", "s3m#rung1", "s4#rung0", "s4#rung1"]
    for q in qs:
        assert q["text"].startswith(f"{obs[q['scenario']]} {run.PREMISE} Which one of these causes")
        assert q["text"].count(run.PREMISE) == 1
    # the rungs, streams and causes are those of the deposited rows. The rows name the damper-position
    # stream "Act"; it is the supplement's damper position, which the stores count as ActP
    # (bara.stores.rung_store)
    act = lambda s: tuple(sorted("ActP" if x == "Act" else x for x in s))
    rows = {(r["scenario"], r["rung"], act(r["streams"]), r["answerable"], r["true_cause"])
            for r in json.loads((RUNS / "rows.json").read_text(encoding="utf-8"))}
    assert rows == {(q["scenario"], q["question_id"].split("#")[1], tuple(q["streams_in_scope"]),
                     q["answerable"], q["true_cause"]) for q in qs}
