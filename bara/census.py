"""Ceiling census over real Brick graphs: what real buildings expose (agent-free, graph-only).

    python -m bara.census                                   # -> results/census/census_v2.{json,md}
    python -m bara.census --graphs <folder> --out <folder>  # another revision of the Mortar graphs

Reads the stream classes (bara.canon.STREAMS) from a Brick graph and scores both readiness
ceilings, two ways per building:
  declared  every typed point counts
  linked    only points that carry a time-series reference count
The gap between the two is the "graph promises more than the data holds" finding. Also runs the
ranking-robustness analysis: how often random domain weights reorder a pair of buildings.

Sources (downloaded by scripts/fetch_data.py; see bara/__init__.py for the locations):
  Mortar  $MORTAR_DIR/graphs/*.ttl   (series linked by ref:hasTimeseriesId): gtfierro/mortargraphs
          at revision 8844574c (2026-08-11, migrated off deprecated Brick classes), the graphs the
          Mortar agent runs use as well. The deprecated classes' replacements are followed (see
          FOLLOW_REPLACEMENTS).
  BTS     $BTS_DIR/Site_*.ttl        (series linked by senaps:stream_id)

A stream class is a set of Brick classes (subclasses included) plus, for generic classes, a rule on
what the point is attached to. RULES below is that mapping as data (the appendix table tab:brickmap).
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, URIRef

from bara import BRICK_TTL, BTS_DIR, MORTAR_DIR, RESULTS_DIR
from bara.canon import DOMAINS, ceiling, end_use_streams, weighted_score

_OUT = RESULTS_DIR / "census"
_ONTOLOGY = BRICK_TTL
MORTAR_GRAPHS_DIR = Path(os.environ.get("MORTAR_GRAPHS_DIR", MORTAR_DIR / "graphs"))

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
SENAPS = Namespace("http://senaps.io/schema/1.0/senaps#")

# Class names from older Brick releases that the public graphs still use -> Brick 1.4 names.
ALIASES = {
    "Building_Electric_Meter": "Building_Electrical_Meter", "Electric_Meter": "Electrical_Meter",
    "Electrical_Power_Sensor": "Electric_Power_Sensor",
    "Electrical_Energy_Sensor": "Electric_Energy_Sensor",
    "Supply_Air_flow": "Supply_Air_Flow_Sensor", "AHU": "Air_Handler_Unit",
    "Occupied_Cooling_Temperature_Setpoint": "Occupied_Air_Temperature_Cooling_Setpoint",
    "Occupied_Heating_Temperature_Setpoint": "Occupied_Air_Temperature_Heating_Setpoint",
}
# Names in the actuation canon (ACTUATION) that Brick 1.4 does not define. Public graphs use the
# first one, so both are matched as literal class names.
_LEGACY_LITERALS = {"Outside_Air_Damper_Command", "Lighting_Command"}
# Count a deprecated class's Brick replacement with it (see Ontology). The August 2026 Mortar graphs
# replaced Zone_Air_Temperature_Setpoint and Speed_Status by their replacements, which the rules
# would otherwise miss (the June 2026 revision gives the same census either way).
FOLLOW_REPLACEMENTS = True
_SKIP = {"mortar": {"smc"}}  # smc.ttl carries the same 505 series ids as bldg30.ttl


@dataclass(frozen=True)
class Rule:
    stream: str
    roots: tuple[str, ...] = ()      # Brick classes that count on their own (subclasses included)
    generic: tuple[str, ...] = ()    # generic classes that count only when attached as below
    attached: tuple[str, ...] = ()   # attachment groups (any of); see _GROUP_ROOTS
    roots_need_attachment: bool = False


RULES: tuple[Rule, ...] = (
    Rule("T", roots=("Zone_Air_Temperature_Sensor", "Room_Air_Temperature_Sensor"),
         generic=("Air_Temperature_Sensor", "Temperature_Sensor"), attached=("zone", "terminal")),
    Rule("Sp", roots=("Zone_Air_Temperature_Setpoint", "Room_Air_Temperature_Setpoint",
                      "Effective_Air_Temperature_Cooling_Setpoint",
                      "Effective_Air_Temperature_Heating_Setpoint",
                      "Occupied_Air_Temperature_Cooling_Setpoint",
                      "Occupied_Air_Temperature_Heating_Setpoint",
                      "Unoccupied_Air_Temperature_Cooling_Setpoint",
                      "Unoccupied_Air_Temperature_Heating_Setpoint"),
         generic=("Cooling_Temperature_Setpoint", "Heating_Temperature_Setpoint",
                  "Temperature_Setpoint"), attached=("zone", "terminal")),
    # the terminal actuation signal, as command (ActC) and as response (ActP): a stuck damper is told
    # from a load change only by a command that moves while the position stays
    Rule("ActC", roots=("Damper_Position_Command", "Damper_Position_Setpoint", "Valve_Command",
                        "Heating_Command", "Cooling_Command"),
         attached=("zone", "terminal"), roots_need_attachment=True),
    Rule("ActP", roots=("Damper_Position_Sensor", "Valve_Position_Sensor"),
         generic=("Position_Sensor", "Supply_Air_Flow_Sensor", "Discharge_Air_Flow_Sensor",
                  "Air_Flow_Sensor"), attached=("zone", "terminal"), roots_need_attachment=True),
    Rule("SAT", roots=("Supply_Air_Temperature_Sensor", "Discharge_Air_Temperature_Sensor")),
    Rule("OAT", roots=("Outside_Air_Temperature_Sensor",)),
    Rule("Occ", roots=("Occupancy_Sensor", "Occupancy_Count_Sensor", "Motion_Sensor")),
    Rule("CO2", roots=("CO2_Sensor",)),
    Rule("OAF", roots=("Outside_Air_Flow_Sensor",)),
    Rule("Lgt", roots=("Illuminance_Sensor", "Luminance_Sensor", "Luminance_Command")),
    Rule("Run", roots=("On_Off_Status", "Start_Stop_Status", "Enable_Status", "Run_Status",
                       "System_Status", "Speed_Status", "On_Off_Command", "Start_Stop_Command",
                       "Enable_Command", "Run_Enable_Command", "Speed_Command",
                       "Frequency_Command", "Pump_Command", "Fan_Command",
                       "Output_Frequency_Sensor"),
         attached=("central",), roots_need_attachment=True),
    Rule("Load", roots=("Air_Flow_Sensor", "Water_Flow_Sensor", "Thermal_Power_Sensor"),
         attached=("central",), roots_need_attachment=True),
)
# Power and energy points become Whole, Pwr, Lgt or an end-use submeter by what they are attached to.
_METERED = ("Electric_Power_Sensor", "Electric_Energy_Sensor", "Power_Sensor", "Energy_Sensor",
            "Electrical_Meter")
_NOT_INPUT_POWER = ("Thermal_Power_Sensor",)  # delivered output: counted as Load, not Pwr
_SCHEDULED_PREFIXES = ("Occupied_", "Unoccupied_")

_GROUP_ROOTS = {
    "zone": ("Location", "HVAC_Zone"),
    "terminal": ("Terminal_Unit",),
    "damper_valve": ("Damper", "Valve"),
    "lighting": ("Lighting_Equipment", "Lighting_System", "Lighting"),
    "building": ("Building", "Building_Electrical_Meter"),
    "submeter": ("Meter",),
    "hvac": ("HVAC_Equipment", "Water_Loop", "Air_Loop", "Chilled_Water_System",
             "Hot_Water_System"),
}
_GROUP_EXTRA = {"zone": {"Open_space", "Enclosed_space", "space"}}  # untyped spaces in BTS

# The actuation canon of the paper (tab:actcanon) as Brick roots, per domain:
# (A1 = writable setpoint, A2 = direct command).
ACTUATION = {
    "thermal": (("Zone_Air_Temperature_Setpoint", "Room_Air_Temperature_Setpoint"),
                ("Damper_Position_Command", "Valve_Command", "Heating_Command")),
    "airquality": (("Air_Flow_Setpoint", "Speed_Setpoint"), ("Outside_Air_Damper_Command",)),
    "equipment": (("On_Off_Command", "Enable_Command", "Start_Stop_Command"),
                  ("Speed_Setpoint", "Speed_Command", "Frequency_Command")),
    "lighting": (("Luminance_Setpoint", "Illuminance_Setpoint"),
                 ("Luminance_Command", "Lighting_Command")),
}


class Ontology:
    """Brick subclass closure, used to expand rule roots to every subclass. With *replacements*, a
    deprecated class also brings in the class Brick names as its replacement (brick:isReplacedBy,
    e.g. Zone_Air_Temperature_Setpoint -> Target_Zone_Air_Temperature_Setpoint), and that class's
    subclasses: a graph migrated off deprecated classes then keeps its stream classes."""

    def __init__(self, path: Path = _ONTOLOGY, replacements: bool | None = None):
        g = Graph().parse(str(path), format="turtle")
        self._children: dict[URIRef, set[URIRef]] = defaultdict(set)
        for s, o in g.subject_objects(RDFS.subClassOf):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                self._children[o].add(s)
        self._replaced_by: dict[URIRef, set[URIRef]] = defaultdict(set)
        if FOLLOW_REPLACEMENTS if replacements is None else replacements:
            for s, o in g.subject_objects(BRICK.isReplacedBy):
                if isinstance(o, URIRef):
                    self._replaced_by[s].add(o)
        self.known = {str(c).split("#")[-1] for c in itertools.chain(self._children,
                      *self._children.values())}

    def closure(self, *names: str) -> frozenset[str]:
        out, stack = set(), [BRICK[n] for n in names]
        while stack:
            c = stack.pop()
            name = str(c).split("#")[-1]
            if name not in out:
                out.add(name)
                stack.extend(self._children.get(c, ()))
                stack.extend(self._replaced_by.get(c, ()))
        return frozenset(out)


class _Classifier:
    def __init__(self, onto: Ontology):
        self.rules = [(r, onto.closure(*r.roots), frozenset(r.generic)) for r in RULES]
        self.groups = {k: onto.closure(*v) | _GROUP_EXTRA.get(k, set())
                       for k, v in _GROUP_ROOTS.items()}
        self.groups["submeter"] -= onto.closure("Building_Meter")
        self.groups["central"] = self.groups["hvac"] - self.groups["terminal"] \
            - self.groups["damper_valve"]
        self.metered = onto.closure(*_METERED) - onto.closure(*_NOT_INPUT_POWER)
        self.whole = onto.closure("Building_Electrical_Meter")
        self.points = onto.closure("Point")
        self.actuation = {d: (onto.closure(*a1), onto.closure(*a2))
                          for d, (a1, a2) in ACTUATION.items()}

    def groups_of(self, types: set[str]) -> set[str]:
        return {k for k, members in self.groups.items() if types & members}


def unknown_rule_classes(onto: Ontology | None = None) -> set[str]:
    """Class names used by the rules that the ontology does not define (typos, renamed classes)."""
    onto = onto or Ontology()
    used = {n for r in RULES for n in r.roots + r.generic} | set(_METERED + _NOT_INPUT_POWER)
    used |= {n for roots in _GROUP_ROOTS.values() for n in roots}
    used |= {n for a1, a2 in ACTUATION.values() for n in a1 + a2} | set(ALIASES.values())
    return {n for n in used if n not in onto.known} - _LEGACY_LITERALS


def _load(path: Path):
    g = Graph().parse(str(path), format="turtle")
    types: dict = defaultdict(set)
    for s, o in g.subject_objects(RDF.type):
        name = str(o).split("#")[-1]
        types[s].add(ALIASES.get(name, name))
    parents: dict = defaultdict(set)
    for e, p in g.subject_objects(BRICK.hasPoint):
        parents[p].add(e)
    for p, e in g.subject_objects(BRICK.isPointOf):
        parents[p].add(e)
    owners: dict = defaultdict(set)  # a damper or valve -> the unit it is part of
    for part, whole in g.subject_objects(BRICK.isPartOf):
        owners[part].add(whole)
    for whole, part in g.subject_objects(BRICK.hasPart):
        owners[part].add(whole)
    feeds: dict = defaultdict(set)
    for a, b in g.subject_objects(BRICK.feeds):
        feeds[a].add(b)
    for b, a in g.subject_objects(BRICK.isFedBy):
        feeds[a].add(b)
    linked = {s for s in g.subjects(SENAPS.stream_id, None)}
    for s, ext in g.subject_objects(REF.hasExternalReference):
        if (ext, REF.hasTimeseriesId, None) in g:
            linked.add(s)
    return types, parents, owners, feeds, linked


def _attachment(point, types, parents, owners, clf: _Classifier) -> set[str]:
    """Attachment groups of a point: its parents, and the unit a parent damper/valve belongs to."""
    groups: set[str] = set()
    for e in parents[point]:
        here = clf.groups_of(types[e])
        groups |= here
        if "damper_valve" in here:
            for unit in owners[e]:
                groups |= clf.groups_of(types[unit])
    return groups


def _meter_end_uses(meter, types, feeds, clf: _Classifier) -> set[str]:
    """End uses downstream of a submeter, following brick:feeds for two hops."""
    found: set[str] = set()
    frontier = {meter}
    for _ in range(2):
        frontier = set().union(*(feeds[e] for e in frontier)) if frontier else set()
        for e in frontier:
            groups = clf.groups_of(types[e])
            if groups & {"hvac", "terminal"}:
                found.add("hvac")
            if "lighting" in groups:
                found.add("lighting")
    return found or {"other"}


# The published BATS graphs type zone-level lighting power as a generic Electric_Power_Sensor on
# the HVAC_Zone (BuildStream's Lighting_Electrical_Power loses its class in the release). Under the
# stated rule below, a power point attached to a zone counts as lighting. The paper states the rule.
ZONE_POWER_IS_LIGHTING = True
# A metered point with no parent and no feeds relation says nothing about what it meters, so it
# counts as no stream class. Set True to count it as an unknown end-use submeter (Sub, and Sub2
# with a second one).
UNATTACHED_METER_IS_SUBMETER = False
# Sensitivity only: root classes only. No generic class counts through what it is
# attached to, and a metered point counts only when it is itself a building meter (Whole).
STRICT_MAPPING = False
# Sensitivity only: a metered point attached to nothing and feeding nothing counts as the whole-building
# meter. On the Mortar graphs of 8844574c these are exactly the 16 former Building_Electric_Meter points.
UNATTACHED_METER_IS_WHOLE = False


def stream_classes(path: Path, clf: _Classifier, *,
                   linked_only: bool) -> tuple[set[str], set[str], int]:
    """(stream classes, all point type names, number of points considered) of one graph."""
    types, parents, owners, feeds, linked = _load(path)
    points = [p for p in types if p in linked] if linked_only else \
        [p for p in types if types[p] & (clf.points | clf.whole) or parents[p] or p in linked]
    have, end_uses, roles, names = set(), set(), set(), set()
    for p in points:
        ts = types[p]
        names |= ts
        att = _attachment(p, types, parents, owners, clf)
        for rule, roots, generic in clf.rules:
            attached = bool(att & set(rule.attached))
            if (ts & roots and (attached or not rule.roots_need_attachment)) \
                    or (ts & generic and attached and not STRICT_MAPPING):
                have.add(rule.stream)
                if rule.stream == "Sp":
                    scheduled = any(t.startswith(_SCHEDULED_PREFIXES) for t in ts & roots)
                    roles.add("scheduled" if scheduled else "in_effect")
        if (ts & clf.whole or (ts & clf.metered and "building" in att and not STRICT_MAPPING)
                or (UNATTACHED_METER_IS_WHOLE and ts & clf.metered and not parents[p] and not feeds[p])):
            have.add("Whole")
        elif ts & clf.metered and not STRICT_MAPPING:
            if "lighting" in att:
                have.add("Lgt")
                end_uses.add("lighting")
            elif ZONE_POWER_IS_LIGHTING and "zone" in att and not att & {"central", "terminal"}:
                have.add("Lgt")
                end_uses.add("lighting")
            elif att & {"central", "terminal"}:
                have.add("Pwr")
                end_uses.add("hvac")
            elif parents[p] or feeds[p] or UNATTACHED_METER_IS_SUBMETER:
                for e in parents[p] or [p]:
                    end_uses |= _meter_end_uses(e, types, feeds, clf)
            # else: a meter point attached to nothing and feeding nothing says nothing about what it
            # meters, so it realizes no stream class
    if roles == {"scheduled", "in_effect"}:
        have.add("SpC")
    return have | end_use_streams(end_uses), names, len(points)


def actuation_ceiling(names: set[str], clf: _Classifier) -> tuple[float, dict[str, int]]:
    per = {d: (2 if a1 & names and a2 & names else 1 if a1 & names else 0)
           for d, (a1, a2) in clf.actuation.items()}
    return sum(per.values()) / (2 * len(per)), per


def sources() -> list[tuple[str, str, Path]]:
    out = [("mortar", p.stem, p) for p in sorted(MORTAR_GRAPHS_DIR.glob("*.ttl"),
                                                 key=lambda q: (len(q.stem), q.stem))
           if p.stem not in _SKIP["mortar"]]
    out += [("bts", p.stem, p) for p in sorted(BTS_DIR.glob("Site_*.ttl"))]
    return out


def flip_analysis(rows: list[dict], draws: int = 2000, seed: int = 7) -> dict:
    """Share of random positive domain weightings that reorder at least one pair of buildings."""
    rng = random.Random(seed)
    pairs = [(a, b) for a, b in itertools.combinations(rows, 2) if a["c_ans"] != b["c_ans"]]
    flipped, any_flip = Counter(), 0
    for _ in range(draws):
        w = {d: rng.expovariate(1.0) for d in DOMAINS}
        hit = False
        for a, b in pairs:
            base = a["c_ans"] - b["c_ans"]
            new = weighted_score(a["by_domain"], w) - weighted_score(b["by_domain"], w)
            if base * new < 0:
                flipped[(a["building"], b["building"])] += 1
                hit = True
        any_flip += hit
    return {"draws": draws, "pairs": len(pairs), "draws_with_a_flip": any_flip,
            "pairs_that_ever_flip": len(flipped)}


def build(out: Path = _OUT) -> dict:
    """Census of every source graph: census_v2.json and census_v2.md in *out*. Ceilings are stored
    unrounded and rounded once, when printed."""
    clf = _Classifier(Ontology())
    rows = []
    for source, name, path in sources():
        declared, _, n_points = stream_classes(path, clf, linked_only=False)
        linked, names, n_linked = stream_classes(path, clf, linked_only=True)
        c_decl, c_link = ceiling(declared), ceiling(linked)
        c_act, act = actuation_ceiling(names, clf)
        rows.append({"source": source, "building": name, "points": n_points,
                     "linked_points": n_linked, "streams": sorted(linked), "streams_declared": sorted(declared),
                     "c_ans_declared": c_decl.score, "c_ans": c_link.score,
                     "by_domain": c_link.by_domain, "c_act": c_act, "actuation": act})
    with_data = [r for r in rows if r["linked_points"]]
    report = {"canon": "v2", "rows": rows, "n": len(rows), "n_with_data": len(with_data),
              "flips": flip_analysis(with_data)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "census_v2.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8",
                                              newline="\n")
    _write_md(report, out)
    return report


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1          # average rank for ties
        i = j + 1
    return r


def _spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5


def _reversed_pairs(a: list[float], b: list[float]) -> tuple[int, int]:
    """(pairs ordered oppositely, pairs both measures separate)."""
    both = rev = 0
    for i, j in itertools.combinations(range(len(a)), 2):
        da, db = a[i] - a[j], b[i] - b[j]
        if da and db:
            both += 1
            rev += da * db < 0
    return rev, both


PAPER_STREAMS = [("SAT", "supply air temperature"), ("OAT", "outside air temperature"),
                 ("Load", "equipment load"), ("Run", "run status"), ("T", "zone temperature"),
                 ("Sp", "zone setpoint"), ("ActC", "terminal actuation command"), ("ActP", "terminal actuation response"),
                 ("Sub", "end-use submeter"), ("Pwr", "equipment power"),
                 ("Whole", "whole-building meter"), ("Occ", "occupancy"), ("CO2", "CO2")]


def paper_numbers(report: dict) -> dict:
    """Every census number the manuscript quotes, over the graphs with linked series."""
    rows = report["rows"]
    data = [r for r in rows if r["linked_points"]]
    vals = sorted(r["c_ans"] for r in data)
    acts = sorted(r["c_act"] for r in data)
    c = [r["c_ans"] for r in data]
    npts, ncls = [r["linked_points"] for r in data], [len(r["streams"]) for r in data]
    by_k = defaultdict(list)
    for r in data:
        by_k[len(r["streams"])].append(r["c_ans"])
    f = report["flips"]
    return {
        "graphs": len(rows), "with_linked_series": len(data),
        "c_ans_median": vals[len(vals) // 2], "c_ans_max": vals[-1], "c_ans_distinct": len(set(vals)),
        "declared_above_linked": sum(1 for r in rows if r["c_ans_declared"] > r["c_ans"]),
        "stream_counts": {s: sum(1 for r in data if s in r["streams"]) for s, _ in PAPER_STREAMS},
        "c_act_min": acts[0], "c_act_max": acts[-1], "c_act_median": acts[len(acts) // 2],
        "c_act_zero": sum(1 for a in acts if a == 0),
        "weightings_with_a_flip": f["draws_with_a_flip"], "weightings": f["draws"],
        "pairs_that_flip": f["pairs_that_ever_flip"], "pairs_unequal": f["pairs"],
        "rho_linked_points": round(_spearman(c, npts), 2),
        "reversed_vs_linked_points": _reversed_pairs(c, npts),
        "rho_stream_classes": round(_spearman(c, ncls), 2),
        "reversed_vs_stream_classes": _reversed_pairs(c, ncls),
        "range_by_class_count": {k: (min(v), max(v)) for k, v in sorted(by_k.items()) if len(v) > 1},
    }


def _write_md(report: dict, out: Path = _OUT) -> None:
    rows = report["rows"]
    data = [r for r in rows if r["linked_points"]]
    vals = sorted(r["c_ans"] for r in data)
    over = [r["building"] for r in rows if r["c_ans_declared"] > r["c_ans"]]
    f = report["flips"]
    L = ["# Ceiling census over real Brick graphs", "",
         f"{len(rows)} graphs, {len(data)} with linked series, "
         f"{sum(1 for r in data if r['streams'])} of those with at least one canon stream class. "
         "Statistics below are over the graphs with linked series. Graph-only and agent-free "
         "(`python -m bara.census`). declared = every typed point; linked = points that carry a "
         "time-series reference.", "",
         f"- Linked ceiling: min {vals[0]:.3f}, median {vals[len(vals) // 2]:.3f}, "
         f"max {vals[-1]:.3f}, {len(set(vals))} distinct values.",
         f"- The graph declares more than its linked data supports in {len(over)} of {len(rows)} "
         f"graphs: {', '.join(over)}.",
         f"- Ranking robustness: {f['draws_with_a_flip']} of {f['draws']} random domain weightings "
         f"reorder at least one pair; {f['pairs_that_ever_flip']} of {f['pairs']} pairs ever flip.",
         ]
    n = paper_numbers(report)
    L += ["", "## Numbers used in the paper", "",
          f"- Linked C_ans: median {n['c_ans_median']:.3f}, max {n['c_ans_max']:.3f}, "
          f"{n['c_ans_distinct']} distinct values; declared above linked in "
          f"{n['declared_above_linked']} of {n['graphs']} graphs.",
          "- Graphs (of the " + str(n["with_linked_series"]) + " with linked series) linking each class: "
          + ", ".join(f"{lab} {n['stream_counts'][s]}" for s, lab in PAPER_STREAMS) + ".",
          f"- C_act: {n['c_act_min']:.3f} to {n['c_act_max']:.3f}, median {n['c_act_median']:.3f}; "
          f"{n['c_act_zero']} graphs expose no writable setpoint or command.",
          f"- Weightings: {n['weightings_with_a_flip']} of {n['weightings']} reorder a pair; "
          f"{n['pairs_that_flip']} of {n['pairs_unequal']} pairs with unequal ceilings ever flip.",
          f"- Against the number of linked points: Spearman {n['rho_linked_points']:.2f}, "
          f"{n['reversed_vs_linked_points'][0]} of {n['reversed_vs_linked_points'][1]} pairs reversed. "
          f"Against the number of linked stream classes: {n['rho_stream_classes']:.2f}, "
          f"{n['reversed_vs_stream_classes'][0]} of {n['reversed_vs_stream_classes'][1]} reversed.",
          "- C_ans range among graphs linking the same number of stream classes: "
          + "; ".join(f"{k}: {a:.3f}-{b:.3f}" for k, (a, b) in n["range_by_class_count"].items()) + ".",
          "", "## Per graph", "",
          "| source | building | points | linked | C_ans declared | C_ans linked | C_act | "
          "linked stream classes |", "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        L.append(f"| {r['source']} | {r['building']} | {r['points']} | {r['linked_points']} | "
                 f"{r['c_ans_declared']:.3f} | "
                 f"{r['c_ans']:.3f} | {r['c_act']:.3f} | {' '.join(r['streams']) or '-'} |")
    (out / "census_v2.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--graphs", type=Path, default=None,
                    help="folder of Mortar graphs (default: $MORTAR_GRAPHS_DIR or $MORTAR_DIR/graphs)")
    ap.add_argument("--out", type=Path, default=_OUT,
                    help="folder for census_v2.json and census_v2.md (default: results/census)")
    a = ap.parse_args()
    if a.graphs is not None:
        MORTAR_GRAPHS_DIR = a.graphs
    rep = build(a.out)
    print(f"{rep['n']} graphs, {rep['n_with_data']} with linked series; flips: {rep['flips']}; "
          f"written to {a.out}")
