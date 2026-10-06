"""Diagnosis questions from a fault-scenario manifest, asked up an instrumentation ladder.

A scenario is one labelled fault in one building (manifests: results/faults/*.json). Each scenario is asked several times, each time with a
different set of stream classes in scope. With the separating streams absent the cause is not
identifiable and the right answer is an abstention; bara.decompose.diagnosis_outcome scores that.

The candidate causes are given in the question, the same list for every rung of a ladder, so the only
thing that changes between rungs is the data in scope.
"""
from __future__ import annotations

import json
from pathlib import Path

from bara.canon import CAUSES

SHAPE = '{"cause": "<one of the candidate causes, copied exactly>"}'


def separators(domain: str, cause: str, rivals: list[str]) -> set[str]:
    """Stream classes needed to tell *cause* from every rival, read off the canon's cause table."""
    table = {c: set(s) for d, c, _shows, s in CAUSES if d == domain}
    need: set[str] = set()
    for name in [cause, *rivals]:
        need |= table[name]
    return {s for s in need if s != "T(peers)"}


def ladder(base: set[str], needed: set[str]) -> list[set[str]]:
    """Stream sets from *base* up to base + needed, adding one separating class at a time."""
    rungs, have = [set(base)], set(base)
    for s in sorted(needed - base):
        have = have | {s}
        rungs.append(set(have))
    return rungs


def questions(manifest_path: Path) -> list[dict]:
    out = []
    for sc in json.loads(Path(manifest_path).read_text(encoding="utf-8"))["scenarios"]:
        # a scenario may state its separating streams; otherwise they are read off the cause table
        need = set(sc.get("separating_streams") or separators(sc["domain"], sc["true_cause"], sc["rival_causes"]))
        causes = sorted([sc["true_cause"], *sc["rival_causes"]])
        text = (f"{sc['observation']} Which one of these causes do the data support: "
                f"{'; '.join(causes)}? Use only the data available for this building. If the "
                "available streams cannot tell these causes apart, abstain and name the streams "
                "you would need.")
        for i, streams in enumerate(ladder(set(sc["base_streams"]), need)):
            out.append({"question_id": f"{sc['id']}#rung{i}", "scenario": sc["id"],
                        "building": sc["building"], "domain": sc["domain"], "intent": "diagnosis",
                        "level": 3, "text": text, "schema": SHAPE, "streams_in_scope": sorted(streams),
                        "answerable": need <= streams, "true_cause": sc["true_cause"],
                        "candidate_causes": causes})
    return out
