"""The paired diagnosis scenarios, rebuilt from public data.

The manifest results/faults/scenarios_supplement.json: BATS v1.0 plus the L3 supplement
(supplement/), scenarios s1, s1r, s3m and s4 in two look-alike pairs, with the separating stream on
rung 1 (SpC for pair A, ActP for pair B; the manifest states it per scenario).

    python -m bara.scenarios          # builds the stores under $DERIVED_DIR/scenarios_supplement
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from bara import BATS_DIR, DERIVED_DIR, RESULTS_DIR, SUPPLEMENT_DIR, graphfix

B = "large_office__2a_tampa"
MANIFEST = RESULTS_DIR / "faults" / "scenarios_supplement.json"
OUT = DERIVED_DIR / "scenarios_supplement"


def build_supplement() -> dict[str, tuple[Path, Path]]:
    """(graph, store) for each building of the supplement manifest: the merge script of the
    deposited supplement, then the inverse links (bara.graphfix) on each merged graph."""
    out = OUT
    names = [f"{B}__{s}" for s in ("faulted", "act", "s1r", "s4", "s3m")]
    if not all((out / n / "kg_linked.ttl").exists() for n in names):
        spec = importlib.util.spec_from_file_location("merge_supplement", SUPPLEMENT_DIR / "merge_supplement.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main(BATS_DIR, out)
        for n in names:
            graphfix.add_inverses(out / n / "kg.ttl", out / n / "kg_linked.ttl")
    return {n: (out / n / "kg_linked.ttl", out / n) for n in names}


def load() -> tuple[list[dict], dict[str, tuple[Path, Path]]]:
    """(faultbank questions, building -> (graph, store)) of the paired scenarios."""
    from bara.faultbank import questions
    return questions(MANIFEST), build_supplement()


if __name__ == "__main__":
    qs, stores = load()
    print(len(qs), "questions;", ", ".join(sorted(stores)))
