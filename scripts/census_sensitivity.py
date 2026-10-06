"""The census under alternative mapping rules. Graph-only, no agent.

    python scripts/census_sensitivity.py        # -> results/census/census_sensitivity.md

Variants (flags of bara.census, all off in the census as reported):
  current           the census as deposited (census_v2.json)
  meter as Whole    UNATTACHED_METER_IS_WHOLE: a metered point attached to nothing and feeding nothing
                    counts as the whole-building meter. On the 8844574c Mortar graphs these are exactly
                    the 16 points the June 2026 revision typed Building_Electric_Meter (4 of them linked).
  strict            STRICT_MAPPING: root classes only; no generic class counts through its attachment,
                    and a metered point counts only when it is itself a building meter.

For each: the numbers the manuscript quotes, the rank correlation of the linked ceilings with the
current mapping, and the largest single retrofit step per building (the stream class whose addition
raises the linked ceiling most; the count of buildings for each class).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import RESULTS_DIR, DERIVED_DIR, canon, census  # noqa: E402

OUT = RESULTS_DIR / "census" / "census_sensitivity.md"


def largest_step(streams) -> list[str]:
    have = set(streams)
    base = canon.ceiling(have).achieved
    gains = {s: canon.ceiling(have | {s}).achieved - base for s in canon.STREAMS if s not in have}
    top = max(gains.values())
    return sorted(s for s, g in gains.items() if g == top)


def variant(name: str, **flags) -> dict:
    for k, v in flags.items():
        setattr(census, k, v)
    try:
        rep = census.build(DERIVED_DIR / "census_sensitivity" / name)
    finally:
        for k in flags:
            setattr(census, k, False)
    return rep


def main() -> None:
    cur = json.loads((RESULTS_DIR / "census" / "census_v2.json").read_text(encoding="utf-8"))
    reps = {"current": cur, "meter as Whole": variant("meter_as_whole", UNATTACHED_METER_IS_WHOLE=True),
            "strict": variant("strict", STRICT_MAPPING=True)}
    base = {r["building"]: r["c_ans"] for r in cur["rows"] if r["linked_points"]}
    ks = sorted(base)
    L = ["# Census under alternative mapping rules", "", "Variants as in scripts/census_sensitivity.py. "
         f"{len(ks)} graphs with linked series of 45.", "",
         "| number | " + " | ".join(reps) + " |", "|---|" + "---:|" * len(reps)]
    num = {k: census.paper_numbers(r) for k, r in reps.items()}
    rows = [("linked C_ans median", lambda n, r: f"{n['c_ans_median']:.3f}"),
            ("linked C_ans max", lambda n, r: f"{n['c_ans_max']:.3f}"),
            ("distinct values", lambda n, r: str(n["c_ans_distinct"])),
            ("declared above linked (of 45)", lambda n, r: str(n["declared_above_linked"])),
            ("graphs linking Whole", lambda n, r: str(n["stream_counts"]["Whole"])),
            ("graphs linking Sub", lambda n, r: str(n["stream_counts"]["Sub"])),
            ("graphs linking Pwr", lambda n, r: str(n["stream_counts"]["Pwr"])),
            ("weightings that reorder a pair (of 2000)", lambda n, r: str(n["weightings_with_a_flip"])),
            ("pairs that ever flip", lambda n, r: f"{n['pairs_that_flip']} of {n['pairs_unequal']}"),
            ("C_act median", lambda n, r: f"{n['c_act_median']:.3f}"),
            ("Spearman with the current linked C_ans", lambda n, r: f"{census._spearman([base[k] for k in ks], [{x['building']: x['c_ans'] for x in r['rows']}[k] for k in ks]):.3f}")]
    for label, f in rows:
        L.append(f"| {label} | " + " | ".join(f(num[k], reps[k]) for k in reps) + " |")
    L += ["", "## Largest single retrofit step (buildings per stream class; ties listed together)", "",
          "| variant | largest step |", "|---|---|"]
    for k, r in reps.items():
        c = Counter("/".join(largest_step(x["streams"])) for x in r["rows"] if x["linked_points"])
        L.append(f"| {k} | " + ", ".join(f"{s} {v}" for s, v in c.most_common()) + " |")
    changed = {k: [(x["building"], base[x["building"]], x["c_ans"]) for x in r["rows"]
                   if x["linked_points"] and x["c_ans"] != base[x["building"]]] for k, r in reps.items() if k != "current"}
    L += ["", "## Graphs whose linked ceiling changes", ""]
    L += [f"- {k}: " + (", ".join(f"{b} {a:.3f}->{n:.3f}" for b, a, n in v) or "none") for k, v in changed.items()]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
