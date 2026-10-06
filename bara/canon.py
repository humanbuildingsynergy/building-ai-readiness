"""The question canon: the fixed instrument of the study.

A canon is a requirement table: for every (domain, intent) cell, the stream classes needed to reach
each answer-completeness level (L1 value, L2 value + reference, L3 value + reference + cause). The
cap of a cell is its highest level. The answerable-readiness ceiling of an instrumentation profile
is sum(achieved levels) / sum(caps).

The paper's canon has 76 caps and is stored under the name v2 (CANONS["v2"]). Its L3 rows list the
stream classes that separate a declared set of candidate causes (CAUSES below). Air-quality
comparison reaches L3, so every domain with a declared cause set reaches L3 on its comparison,
verification, diagnosis and explanation cells.

Pure data and arithmetic: no graph, no store, no AI. ``bara.census`` reads stream classes from
Brick graphs.
"""
from __future__ import annotations

from dataclasses import dataclass

DOMAINS = ("thermal", "energy", "airquality", "equipment", "occupancy", "lighting")
INTENTS = ("status", "summary", "comparison", "verification", "diagnosis", "explanation")

Cell = tuple[str, str]
Rungs = tuple[frozenset[str], ...]  # cumulative requirement per level; len(rungs) is the cap


def _rows(*rows: tuple[str, tuple[str, ...], tuple[str, ...]]) -> dict[Cell, Rungs]:
    """Expand ``(domain, intents, ("T", "T+Sp", ...))`` rows into per-cell rungs."""
    out: dict[Cell, Rungs] = {}
    for domain, intents, levels in rows:
        rungs = tuple(frozenset(lv.split("+")) for lv in levels)
        for intent in intents:
            out[(domain, intent)] = rungs
    return out


# ── the canon; see STREAMS for the vocabulary ──────────────────────────────────────────────────
_V2 = _rows(
    ("thermal", ("status", "summary"), ("T", "T+Sp")),
    ("thermal", ("comparison",), ("T", "T", "T+Sp+ActC+ActP")),
    ("thermal", ("verification",), ("T", "T+Sp", "T+Sp+ActC+ActP")),
    ("thermal", ("diagnosis", "explanation"), ("T", "T+Sp", "T+Sp+SpC+ActC+ActP+SAT")),
    ("energy", ("status",), ("Whole",)),
    ("energy", ("summary",), ("Whole", "Whole+Sub")),
    ("energy", ("comparison", "diagnosis", "explanation"), ("Whole", "Whole", "Whole+Sub2+OAT")),
    ("airquality", ("status", "summary"), ("CO2", "CO2+Occ")),
    ("airquality", ("comparison",), ("CO2", "CO2", "CO2+Occ+OAF")),
    ("airquality", ("verification", "diagnosis", "explanation"), ("CO2", "CO2+Occ", "CO2+Occ+OAF")),
    ("equipment", ("status", "summary"), ("Pwr", "Pwr")),
    ("equipment", ("comparison", "verification", "diagnosis", "explanation"),
     ("Pwr", "Pwr", "Pwr+Run+Load")),
    ("occupancy", ("status", "summary", "comparison", "diagnosis"), ("Occ", "Occ")),
    ("lighting", ("status", "diagnosis"), ("Lgt", "Lgt+Occ")),
    ("lighting", ("summary", "comparison"), ("Lgt", "Lgt")),
)

# Stream-class vocabulary (the legend of the requirement table).
STREAMS: dict[str, str] = {
    "T": "zone air temperature",
    "Sp": "zone temperature setpoint in effect (heating or cooling)",
    "SpC": "scheduled (occupied/unoccupied) setpoint held apart from the setpoint in effect",
    "ActC": "terminal actuation command (damper or valve command or setpoint, heating or cooling command)",
    "ActP": "terminal actuation response (damper or valve position, terminal airflow)",
    "SAT": "supply air temperature of the air system serving the zone",
    "OAT": "outside air temperature",
    "Occ": "occupancy (presence or count)",
    "CO2": "zone CO2 concentration",
    "OAF": "outdoor-air flow",
    "Whole": "whole-building electricity meter",
    "Sub": "at least one end-use submeter (HVAC, lighting, plug loads, thermal energy)",
    "Sub2": "two end-use groups metered (the third is the residual of the whole)",
    "Pwr": "equipment input power (electricity or fuel)",
    "Run": "equipment run command or status",
    "Load": "equipment load (air or water flow, delivered heating or cooling)",
    "Lgt": "lighting power, lighting status, or illuminance",
}

# Declared cause sets: (domain, candidate cause, what the data shows, separating streams).
# The L3 requirement of a domain is its L2 requirement plus the union of the separating streams.
# "T(peers)" is the same stream class on other zones, so it adds no requirement.
CAUSES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("thermal", "schedule change",
     "scheduled setpoint and setpoint in effect move together", ("SpC",)),
    ("thermal", "local override or controller offset",
     "setpoint in effect moves, scheduled setpoint stays", ("SpC",)),
    ("thermal", "terminal-unit fault (stuck damper or valve)",
     "the command moves or saturates while the position stays", ("ActC", "ActP")),
    ("thermal", "local load change",
     "command and position move together in the correcting direction", ("ActC", "ActP")),
    ("thermal", "supply-side capacity loss",
     "supply air temperature off its normal value, peer zones deviate together", ("SAT", "T(peers)")),
    ("thermal", "zone sensor fault",
     "reading departs from peers with setpoints, command and position unchanged",
     ("T(peers)", "ActC", "ActP")),
    ("equipment", "commanded change", "run command or status changes with power", ("Run",)),
    ("equipment", "load change", "flow or delivered output changes with power", ("Load",)),
    ("equipment", "degradation or fault", "power rises at unchanged command and load",
     ("Run", "Load")),
    ("energy", "weather-driven change",
     "use moves with outside air temperature, as on comparable days", ("OAT",)),
    ("energy", "which end use changed",
     "two metered end-use groups fix the third as the residual", ("Sub2",)),
    ("airquality", "occupancy above design", "occupancy rises with CO2", ("Occ",)),
    ("airquality", "insufficient outdoor air", "outdoor-air flow low at normal occupancy", ("OAF",)),
)


@dataclass(frozen=True)
class Canon:
    name: str
    rungs: dict[Cell, Rungs]

    def cap(self, domain: str, intent: str) -> int:
        """Target level of a cell; 0 if the cell is not in the canon."""
        return len(self.rungs.get((domain, intent), ()))

    @property
    def total(self) -> int:
        """The canon total: the sum of caps (the denominator of the ceiling)."""
        return sum(len(r) for r in self.rungs.values())

    def cap_matrix(self) -> dict[str, dict[str, int]]:
        """The cap table of the paper (tab:canon): domain -> intent -> cap (0 marks a cell outside
        the canon)."""
        return {d: {i: self.cap(d, i) for i in INTENTS} for d in DOMAINS}

    def achieved_level(self, domain: str, intent: str, have: set[str]) -> int:
        """Highest level whose required stream classes are all in *have* (0 if L1 is unmet)."""
        level = 0
        for r, required in enumerate(self.rungs.get((domain, intent), ()), start=1):
            if required <= have:
                level = r
        return level


CANONS: dict[str, Canon] = {"v2": Canon("v2", _V2)}


@dataclass(frozen=True)
class Ceiling:
    canon: str
    streams: tuple[str, ...]
    per_cell: dict[Cell, int]
    by_domain: dict[str, tuple[int, int]]  # domain -> (achieved, cap) sums
    achieved: int
    total: int

    @property
    def score(self) -> float:
        return self.achieved / self.total


def ceiling(have, canon: str = "v2") -> Ceiling:
    """Answerable-readiness ceiling of the stream-class set *have* under the canon *canon*."""
    c, have = CANONS[canon], set(have)
    per_cell = {cell: c.achieved_level(*cell, have) for cell in c.rungs}
    by_domain = {d: (sum(v for (dd, _), v in per_cell.items() if dd == d),
                     sum(len(r) for (dd, _), r in c.rungs.items() if dd == d)) for d in DOMAINS}
    return Ceiling(canon, tuple(sorted(have)), per_cell, by_domain,
                   sum(per_cell.values()), c.total)


def weighted_score(by_domain: dict[str, tuple[int, int]], weights: dict[str, float]) -> float:
    """Ceiling under per-domain weights (the reweighting the ranking-robustness analysis varies)."""
    num = sum(weights[d] * a for d, (a, _) in by_domain.items())
    den = sum(weights[d] * t for d, (_, t) in by_domain.items())
    return num / den


END_USE = {"Pwr": "hvac", "Lgt": "lighting"}  # which metered classes count as which end use


# Instrumentation profiles: nested sets of the stream classes a profile lets a building expose.
# "metered" is the sensing ASHRAE 90.1-2022 requires of a large building; "rich" adds the control
# points that the Guideline 36 sequences read and write.
_ZONE = ("T", "Sp", "Occ")
PROFILES: dict[str, frozenset[str]] = {
    "minimal": frozenset(_ZONE[:1]),
    "comfort": frozenset(_ZONE[:2]),
    "standard": frozenset(_ZONE),
    "metered": frozenset(_ZONE + ("Whole", "Lgt", "Pwr", "OAT")),
    "rich": frozenset(_ZONE + ("Whole", "Lgt", "Pwr", "OAT", "SAT", "SpC", "ActC", "ActP", "Run", "Load",
                               "CO2", "OAF")),
}


def end_use_streams(groups: set[str]) -> set[str]:
    """The derived classes Sub / Sub2 from the set of metered end-use groups."""
    return ({"Sub"} if groups else set()) | ({"Sub2"} if len(groups) >= 2 else set())


def _print_tables(canon: str) -> None:
    c = CANONS[canon]
    print(f"\ncanon {canon}: total {c.total}")
    print(f"{'domain':12}" + "".join(f"{i[:6]:>8}" for i in INTENTS))
    for d, row in c.cap_matrix().items():
        print(f"{d:12}" + "".join(f"{(v or '-'):>8}" for v in row.values()))
    seen: dict[tuple[str, Rungs], list[str]] = {}
    for (d, i), rungs in c.rungs.items():
        seen.setdefault((d, rungs), []).append(i)
    for (d, rungs), intents in seen.items():
        levels = ["+".join(sorted(r)) for r in rungs] + ["-"] * (3 - len(rungs))
        print(f"  {d:11} {', '.join(intents):52} " + " | ".join(f"{lv:16}" for lv in levels))


if __name__ == "__main__":
    for name in CANONS:
        _print_tables(name)
