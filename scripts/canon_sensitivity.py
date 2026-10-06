"""Sensitivity of the headline results to the canon (manuscript table tab:canon-sens).

    python scripts/canon_sensitivity.py        # prints a Markdown table

Recomputes, under the declared canon and four alternatives, the ceiling of the sweep building at
each profile, its realized readiness and AI failure at the metered profile (rung accuracies from the
rich block of results/final/run8.md), and the median and maximum ceiling of the real graphs with
linked series with their Spearman rank correlation against the declared canon
(results/census/census_v2.json). The first row reproduces the declared canon's numbers.

A rung counts only when every lower rung of its cell is reached, and a share is the sum over the
cells divided by the sum of their caps. With equal domain shares, each domain's share is computed
on its own and the domains are averaged.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bara import canon, census  # noqa: E402

DECLARED = canon.CANONS["v2"].rungs

# The stream classes of the sweep building's store at each profile. SWEEP_STORE["metered"] is the
# metered profile as BATS realizes it: BATS publishes no outside air temperature series, so OAT is
# absent, and the zone lighting and equipment power meters give the end-use classes Sub and Sub2.
SWEEP_STORE = {
    "minimal": {"T"},
    "comfort": {"T", "Sp"},
    "standard": {"T", "Sp", "Occ"},
    "metered": {"T", "Sp", "Occ", "Whole", "Sub", "Sub2", "Pwr", "Lgt"},
}

# (label, cell filter or level cap, equal domain shares)
VARIANTS = [
    ("declared", None, False),
    ("no air quality", "no_airquality", False),
    ("no occupancy, lighting", "no_occupancy_lighting", False),
    ("no level above L2", "cap_l2", False),
    ("equal domain shares", None, True),
]


def rung_accuracies() -> dict[tuple[str, str, int], float]:
    """(domain, intent, level) -> accuracy, from the rich block of run8.md (metered = rich)."""
    text = (ROOT / "results" / "final" / "run8.md").read_text(encoding="utf-8")
    block = text[text.index("## rich: per-rung accuracy"):]
    block = block[:block.index("###")]
    return {(domain, intent, int(level)): float(acc)
            for domain, intent, level, acc in re.findall(r"\| (\w+) (\w+) L(\d) \| ([\d.]+) \|", block)}


def reached_level(rungs, have: set[str]) -> int:
    """Highest level whose requirement, and every lower one, is in *have*."""
    level = 0
    for lv, required in enumerate(rungs, start=1):
        if not required <= have:
            break
        level = lv
    return level


def variant_cells(change: str | None) -> dict:
    """The canon's cells under one alternative: a domain left out, or every cell capped at L2."""
    cells = {}
    for (domain, intent), rungs in DECLARED.items():
        if change == "no_airquality" and domain == "airquality":
            continue
        if change == "no_occupancy_lighting" and domain in ("occupancy", "lighting"):
            continue
        cells[(domain, intent)] = rungs[:2] if change == "cap_l2" else rungs
    return cells


def share(cells: dict, credit, equal_domains: bool) -> float:
    """Sum of credit(cell, rungs) over the cells, divided by the sum of caps (per domain, then
    averaged, with *equal_domains*)."""
    groups = ([[k for k in cells if k[0] == d] for d in sorted({d for d, _ in cells})]
              if equal_domains else [list(cells)])
    shares = [sum(credit(k, cells[k]) for k in keys) / sum(len(cells[k]) for k in keys) for keys in groups]
    return sum(shares) / len(shares)


def ceiling(cells: dict, have: set[str], equal_domains: bool = False) -> float:
    return share(cells, lambda _cell, rungs: reached_level(rungs, have), equal_domains)


def realized(cells: dict, have: set[str], accuracy: dict, equal_domains: bool = False) -> float:
    """Sum of the measured accuracies of the reached rungs, divided like the ceiling."""
    return share(cells, lambda cell, rungs: sum(accuracy[(*cell, lv)]
                                                for lv in range(1, reached_level(rungs, have) + 1)),
                 equal_domains)


def main() -> None:
    accuracy = rung_accuracies()
    report = json.loads((ROOT / "results" / "census" / "census_v2.json").read_text(encoding="utf-8"))
    linked = [set(r["streams"]) for r in report["rows"] if r["linked_points"] > 0]
    declared_census = [ceiling(DECLARED, have) for have in linked]
    profiles = list(SWEEP_STORE)
    lines = ["| canon | caps | " + " | ".join(f"C {p}" for p in profiles)
             + " | A_r metered | AI failure | AI failure / C | real median | real max | rank correlation |",
             "|---|---:|" + "---:|" * (len(profiles) + 6)]
    for label, change, equal_domains in VARIANTS:
        cells = variant_cells(change)
        sweep = [ceiling(cells, SWEEP_STORE[p], equal_domains) for p in profiles]
        c_metered = sweep[-1]
        a_r = realized(cells, SWEEP_STORE["metered"], accuracy, equal_domains)
        failure = c_metered - a_r
        real = [ceiling(cells, have, equal_domains) for have in linked]
        rho = census._spearman(declared_census, real)
        caps = sum(len(r) for r in cells.values())
        lines.append(f"| {label} | {caps} | " + " | ".join(f"{x:.3f}" for x in sweep)
                     + f" | {a_r:.3f} | {failure:.3f} | {failure / c_metered:.3f} | "
                     f"{statistics.median(real):.3f} | {max(real):.3f} | {rho:.3f} |")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
