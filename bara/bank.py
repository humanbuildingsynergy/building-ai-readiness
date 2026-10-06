"""The question bank: templates over the canon cells, instantiated from a building's own data.

Self-contained: a Brick graph plus a CSV store (points.csv and timeseries.csv, or catalog.csv and
values.csv with the same columns) is all it reads, so it runs on simulated and on real buildings
alike. Each question class is a template bound to one canon cell and one level. ``build_bank``
samples *n* instances per class across zones, equipment and seasons from a fixed seed, and computes
the ground-truth answer in code. A class whose streams the building lacks yields no instances; the
sweep counts those cells as data limitation.

Every question states its own conventions (window ends, units, sign), so that a disagreement over
conventions is not scored as an AI failure. The bank holds the L1 and L2 classes of the diagnosis
and explanation cells and one L3 explanation class (e_explanation_occ). Thermal cause attribution
at L3 needs labelled faults and is in bara.faultbank.

Answer shapes: number ``{"value": x}``, boolean ``{"value": true|false}``, entity ``{"entity": "name"}``.
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, URIRef

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")

# Brick classes (local names) that realize each stream role in this bank.
CLASSES = {
    "T": {"Zone_Air_Temperature_Sensor"},
    "SpCool": {"Zone_Air_Cooling_Temperature_Setpoint", "Effective_Air_Temperature_Cooling_Setpoint",
               "Zone_Air_Temperature_Setpoint"},      # a single zone setpoint serves as the reference
    "SpHeat": {"Zone_Air_Heating_Temperature_Setpoint", "Effective_Air_Temperature_Heating_Setpoint"},
    "ActC": {"Damper_Position_Command", "Damper_Position_Setpoint", "Heating_Command", "Valve_Command",
             "Cooling_Command"},
    "ActP": {"Damper_Position_Sensor", "Valve_Position_Sensor", "Position_Sensor", "Supply_Air_Flow_Sensor",
             "Discharge_Air_Flow_Sensor", "Air_Flow_Sensor"},     # as the census's ActP on a terminal
    "Occ": {"Occupancy_Count_Sensor", "Occupancy_Sensor"},
    "CO2": {"CO2_Sensor"},
    "OAF": {"Outside_Air_Flow_Sensor"},
    "Whole": {"Building_Electrical_Meter", "Building_Electric_Meter"},
    "Power": {"Electric_Power_Sensor"},
    "Run": {"On_Off_Status", "Run_Status", "Enable_Status", "On_Off_Command", "Start_Stop_Command"},
    "Flow": {"Supply_Air_Flow_Sensor", "Air_Flow_Sensor", "Discharge_Air_Flow_Sensor"},
    "FlowSp": {"Air_Flow_Setpoint", "Supply_Air_Flow_Setpoint", "Discharge_Air_Flow_Setpoint"},
    "HeatV": {"Heating_Valve_Command", "Hot_Water_Valve_Command", "Heating_Command"},
    "CoolV": {"Cooling_Valve_Command", "Chilled_Water_Valve_Command", "Cooling_Command"},
    "OAT": {"Outside_Air_Temperature_Sensor"},
}
def with_replacements(names: set[str]) -> set[str]:
    """*names* plus the classes Brick declares as their replacements (brick:isReplacedBy, e.g.
    Zone_Air_Temperature_Setpoint -> Target_Zone_Air_Temperature_Setpoint), transitively. The map is
    bara/brick/replacements.json, read off the Brick release the census uses; a graph migrated off
    deprecated classes then keeps its roles (the rule of bara.census.Ontology)."""
    path = Path(__file__).resolve().parent / "brick" / "replacements.json"
    repl = json.loads(path.read_text(encoding="utf-8"))
    out, stack = set(), list(names)
    while stack:
        n = stack.pop()
        if n not in out:
            out.add(n)
            stack.extend(repl.get(n, ()))
    return out


CLASSES = {role: with_replacements(names) for role, names in CLASSES.items()}
_KIND = {"HVAC_Zone": "HVAC zone", "Room": "room", "Space": "space", "Floor": "floor"}
_ZONE_TYPES = {"HVAC_Zone"}
# Locations contain zones and equipment as parts; their points must not be folded into them, or the
# building, site and floors become "equipment" with the zones' lighting power (on the small office,
# equipment_with("Power") would return Building, Site and Floor01).
_LOCATION_TYPES = {"Location", "Building", "Site", "Floor", "Storey", "Room", "Space", "Wing",
                   "Area", "Outdoor_Area", "Zone"}
# Stated in every lighting question: the published BATS graphs type zone lighting power as a
# generic power sensor on the zone (see bara.census.ZONE_POWER_IS_LIGHTING).
LIGHTING_RULE = "In this building the electric power sensor attached to a zone meters that zone's lighting."
_SEASON_MONTHS = (1, 4, 7, 10)


@dataclass(frozen=True)
class QClass:
    """One question class: its canon cell, level, the stream classes it needs, graph hops."""
    cid: str
    domain: str
    intent: str
    level: int
    requires: tuple[str, ...]
    answer_type: str            # number | boolean | entity
    tol_abs: float = 0.0
    tol_rel: float = 0.0
    hops: int = 1


class Building:
    """Graph + store access for the templates. Series are dicts ``"YYYY-MM-DDTHH" -> value``."""

    def __init__(self, kg_ttl: Path, store_dir: Path, zone_types: set[str] | None = None):
        self.zone_types = set(zone_types or _ZONE_TYPES)   # real graphs: {"VAV"}, points hang there
        self.g = Graph().parse(str(kg_ttl), format="turtle")
        self._label_index = None
        self.store_dir = Path(store_dir)
        # BuildStream stores use catalog.csv / values.csv; the published BATS corpus uses
        # points.csv / timeseries.csv. Same columns.
        legacy = (self.store_dir / "catalog.csv").exists()
        self._catalog = self.store_dir / ("catalog.csv" if legacy else "points.csv")
        self._values = self.store_dir / ("values.csv" if legacy else "timeseries.csv")
        with self._catalog.open(encoding="utf-8", newline="") as f:
            self.in_store = {r["timeseries_id"] for r in csv.DictReader(f)}
        self._series: dict[str, dict[str, float]] | None = None
        self._types = defaultdict(set)
        for s, o in self.g.subject_objects(RDF.type):
            self._types[s].add(str(o).split("#")[-1])
        self._points = defaultdict(set)
        for p, e in self.g.subject_objects(BRICK.isPointOf):
            self._points[e].add(p)
        for e, p in self.g.subject_objects(BRICK.hasPoint):
            self._points[e].add(p)
        # A part's points count as its whole's: real graphs hang the damper signal on a Damper
        # that isPartOf the VAV, while the zone temperature hangs on the VAV itself.
        parts = defaultdict(set)
        for part, whole in self.g.subject_objects(BRICK.isPartOf):
            parts[whole].add(part)
        for whole, part in self.g.subject_objects(BRICK.hasPart):
            parts[whole].add(part)
        for whole in list(parts):
            if self._types[whole] & _LOCATION_TYPES:
                continue                          # a floor holds its zones' points only in space
            seen, todo = set(), list(parts[whole])
            while todo:
                part = todo.pop()
                if part in seen or part == whole:
                    continue
                seen.add(part)
                self._points[whole] |= self._points.get(part, set())
                todo.extend(parts.get(part, ()))

    # ── graph ────────────────────────────────────────────────────────────────────────────────
    def named(self, e) -> str:
        """The label as a question states it. Where another graph entity carries the same label (BATS
        gives an HVAC zone and a room the same DataCenter_*_ZN_6 label), the entity type is named
        too, so the question has one referent. Ground truth and aliases keep the bare label."""
        lab = self.label(e)
        if self._label_index is None:
            self._label_index = defaultdict(set)
            for s, o in self.g.subject_objects(RDFS.label):
                self._label_index[str(o)].add(s)
        others = self._label_index.get(lab, set()) - {e}
        if not others:
            return lab
        kind = lambda x: next((_KIND.get(t, t.replace("_", " ")) for t in sorted(self._types[x])), "entity")
        rest = sorted({kind(o) for o in others})
        return f"{lab} (the {kind(e)} with this label, not the {' or '.join(rest)} that shares it)"

    def label(self, e) -> str:
        return str(self.g.value(e, RDFS.label) or str(e).split("#")[-1])

    def aliases(self, e) -> list[str]:
        """Every name the graph ties to *e*: its label, its id, the labels and ids of the rooms or
        zones it feeds or contains, and of its own points. An entity answer counts if it names any
        of these, so the grader measures which entity was found, not which name was chosen."""
        names = {self.label(e), str(e).split("#")[-1]}
        linked = set(self.g.objects(e, BRICK.feeds)) | set(self.g.objects(e, BRICK.hasPart)) \
            | set(self.g.subjects(BRICK.isFedBy, e)) | set(self.g.subjects(BRICK.isPartOf, e)) \
            | set(self._points[e])
        for o in linked:
            if self._types[o] & self.zone_types or self._types[o] & {"Room", "Space", "Floor"} \
                    or o in self._points[e]:
                names |= {self.label(o), str(o).split("#")[-1]}
        # The room a terminal feeds names that terminal only when no other terminal feeds it
        # (Mortar types it HVACZone, which the checks above do not match). Uniqueness is counted
        # over the whole building, so it never accepts a room two terminals share.
        if self._types[e] & self.zone_types:
            for o in set(self.g.objects(e, BRICK.feeds)) | set(self.g.subjects(BRICK.isFedBy, e)):
                feeders = {s for s in set(self.g.subjects(BRICK.feeds, o)) | set(self.g.objects(o, BRICK.isFedBy))
                           if self._types[s] & self.zone_types}
                if feeders == {e}:
                    names |= {self.label(o), str(o).split("#")[-1]}
        return sorted(n for n in names if n)

    def entities(self, type_names: set[str]) -> list:
        return sorted((e for e, ts in self._types.items() if ts & type_names), key=str)

    def series_id(self, entity, role: str) -> str | None:
        """Series id of the entity's point in *role*, only if the store holds that series."""
        for p in sorted(self._points[entity], key=str):
            if self._types[p] & CLASSES[role]:
                for ext in self.g.objects(p, REF.hasExternalReference):
                    tsid = self.g.value(ext, REF.hasTimeseriesId)
                    if tsid is not None and str(tsid) in self.in_store:
                        return str(tsid)
        return None

    def with_roles(self, type_names: set[str], *roles: str) -> list:
        return [e for e in self.entities(type_names) if all(self.series_id(e, r) for r in roles)]

    def any_with(self, *roles: str) -> list:
        """Any entity, zone or equipment, that carries all *roles*."""
        return [e for e in sorted(self._points, key=str) if all(self.series_id(e, r) for r in roles)]

    def building_series(self, role: str) -> dict[str, float] | None:
        """The first stored series of a building-level class (meter, weather), wherever it hangs."""
        for p in sorted((p for p, ts in self._types.items() if ts & CLASSES[role]), key=str):
            for ext in self.g.objects(p, REF.hasExternalReference):
                tsid = self.g.value(ext, REF.hasTimeseriesId)
                if tsid is not None and str(tsid) in self.in_store:
                    return self.series(str(tsid))
        return None

    def equipment_with(self, *roles: str) -> list:
        """Non-zone entities (equipment) that carry all *roles*."""
        return [e for e in sorted(self._points, key=str)
                if not self._types[e] & (self.zone_types | _LOCATION_TYPES)
                and all(self.series_id(e, r) for r in roles)]

    def served_zones(self, equipment) -> list:
        """Zones downstream of *equipment* through brick:feeds (any depth)."""
        seen, frontier, zones = set(), {equipment}, []
        while frontier:
            nxt = set()
            for e in frontier:
                for o in list(self.g.objects(e, BRICK.feeds)) + list(self.g.subjects(BRICK.isFedBy, e)):
                    if o not in seen:
                        seen.add(o)
                        nxt.add(o)
                        if self._types[o] & self.zone_types:
                            zones.append(o)
            frontier = nxt
        return sorted(zones, key=str)

    # ── store ────────────────────────────────────────────────────────────────────────────────
    def series(self, tsid: str) -> dict[str, float]:
        if self._series is None:
            self._series = defaultdict(dict)
            with self._values.open(encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        self._series[r["timeseries_id"]][r["timestamp"][:13]] = float(r["value"])
                    except ValueError:
                        continue
        return self._series.get(tsid, {})

    def of(self, entity, role: str) -> dict[str, float]:
        return self.series(self.series_id(entity, role))

    @property
    def year(self) -> int:
        tsid = next(iter(sorted(self.in_store)))
        return int(min(self.series(tsid))[:4])


def day(series: dict[str, float], date: str) -> list[float]:
    return [v for k, v in sorted(series.items()) if k.startswith(date)]


def hours(series: dict[str, float], date: str, start: int, end: int) -> list[float]:
    """Values of *date* for hours start..end, both ends included."""
    return [series[k] for h in range(start, end + 1) if (k := f"{date}T{h:02d}") in series]


# ── templates ─────────────────────────────────────────────────────────────────────────────────────
# Each template returns (text, ground truth) or None when the sampled entities or window cannot
# support it.
def _date(b: Building, rng) -> str:
    return f"{b.year}-{rng.choice(_SEASON_MONTHS):02d}-{rng.randint(2, 27):02d}"


def _hour(rng) -> int:
    return rng.randint(8, 17)


def t_status_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T") or [None])
    d, h = _date(b, rng), _hour(rng)
    v = b.of(z, "T").get(f"{d}T{h:02d}") if z is not None else None
    return None if v is None else (
        f"What was the air temperature in zone {b.named(z)} at {d} {h:02d}:00, in °C?", v)


def t_status_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T", "SpCool") or [None])
    if z is None:
        return None
    d, h = _date(b, rng), _hour(rng)
    t, sp = b.of(z, "T").get(f"{d}T{h:02d}"), b.of(z, "SpCool").get(f"{d}T{h:02d}")
    return None if None in (t, sp) else (
        f"At {d} {h:02d}:00, how far was zone {b.named(z)} from its cooling setpoint, in °C? "
        "Give temperature minus setpoint, so a negative value means below the setpoint.", t - sp)


def t_summary_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T") or [None])
    d = _date(b, rng)
    vals = day(b.of(z, "T"), d) if z is not None else []
    return None if len(vals) < 24 else (
        f"What was the mean air temperature in zone {b.named(z)} on {d} (all 24 hourly values), in °C?",
        sum(vals) / len(vals))


def _outside(b, z, d) -> int | None:
    t, lo, hi = b.of(z, "T"), b.of(z, "SpHeat"), b.of(z, "SpCool")
    keys = [k for k in sorted(t) if k.startswith(d) and k in lo and k in hi]
    return None if len(keys) < 24 else sum(1 for k in keys if t[k] < lo[k] or t[k] > hi[k])


def t_summary_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T", "SpHeat", "SpCool") or [None])
    d = _date(b, rng)
    n = _outside(b, z, d) if z is not None else None
    return None if n is None else (
        f"On {d}, for how many of the 24 hourly values was zone {b.named(z)} outside its own setpoint "
        "band, meaning below its heating setpoint or above its cooling setpoint at that hour?", n)


def t_verification_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T", "SpHeat", "SpCool") or [None])
    d = _date(b, rng)
    n = _outside(b, z, d) if z is not None else None
    return None if n is None else (
        f"Did zone {b.named(z)} stay within its own heating and cooling setpoints at every hourly "
        f"value on {d}?", n == 0)


def t_comparison_2(b, rng):
    zones = b.with_roles(b.zone_types, "T")
    if len(zones) < 2:
        return None
    a, c = rng.sample(zones, 2)
    d, h = _date(b, rng), _hour(rng)
    ta, tc = b.of(a, "T").get(f"{d}T{h:02d}"), b.of(c, "T").get(f"{d}T{h:02d}")
    return None if None in (ta, tc) else (
        f"At {d} {h:02d}:00, what was the air temperature of zone {b.named(a)} minus that of zone "
        f"{b.named(c)}, in °C? A positive value means {b.named(a)} was warmer.", ta - tc)


def t_comparison_2hop(b, rng):
    units = [(u, zs) for u in b.entities({"Air_Handler_Unit", "AHU"})
             if len(zs := [z for z in b.served_zones(u) if b.series_id(z, "T")]) >= 2]
    if not units:
        return None
    u, zs = rng.choice(units)
    d, h = _date(b, rng), _hour(rng)
    temps = {z: b.of(z, "T").get(f"{d}T{h:02d}") for z in zs}
    if None in temps.values():
        return None
    ranked = sorted(temps.items(), key=lambda kv: -kv[1])
    if ranked[0][1] - ranked[1][1] < 0.2:          # a near tie is not a fair ranking question
        return None
    return (f"Among the zones served by air handler {b.named(u)}, which zone had the highest air "
            f"temperature at {d} {h:02d}:00?", ranked[0][0])


def t_comparison_3(b, rng):
    zones = b.with_roles(b.zone_types, "T", "SpCool", "ActC", "ActP")     # posed where T+Sp+ActC+ActP hold
    if len(zones) < 2:
        return None
    a, c = rng.sample(zones, 2)
    d = _date(b, rng)
    pa, pc = hours(b.of(a, "ActC"), d, 8, 18), hours(b.of(c, "ActC"), d, 8, 18)   # computes with the command
    return None if not pa or not pc else (
        f"On {d} between 08:00 and 18:00 (both included), what was the mean terminal damper signal of "
        f"zone {b.named(a)} minus that of zone {b.named(c)}, in the signal's own unit?",
        sum(pa) / len(pa) - sum(pc) / len(pc))


def t_verification_3(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T", "SpCool", "ActC", "ActP") or [None])
    if z is None:
        return None
    t, sp, act = b.of(z, "T"), b.of(z, "SpCool"), b.of(z, "ActC")       # computes with the command
    hot = [k for k in sorted(t) if k in sp and k in act and t[k] > sp[k]]
    if len(hot) < 5:
        return None
    d = rng.choice(hot)[:10]
    vals = [act[k] for k in hot if k.startswith(d)]
    return (f"On {d}, over the hourly values at which zone {b.named(z)} was above its cooling "
            "setpoint, what was the mean terminal damper signal, in the signal's own unit?",
            sum(vals) / len(vals))


def _whole(b):
    return b.building_series("Whole")


def e_status_1(b, rng):
    w, d = _whole(b), _date(b, rng)
    vals = day(w, d) if w else []
    return None if len(vals) < 24 else (
        f"How much electricity did the whole building use on {d}, in joules? The meter series holds "
        "joules per hour; add the 24 hourly values.", sum(vals))


def e_summary_1(b, rng):
    w = _whole(b)
    if not w:
        return None
    m = f"{b.year}-{rng.choice(_SEASON_MONTHS):02d}"
    vals = [v for k, v in w.items() if k.startswith(m)]
    return None if not vals else (
        f"What was the highest hourly whole-building electricity use in {m}, in joules per hour?",
        max(vals))


def _lighting(b):
    return [b.of(z, "Power") for z in b.with_roles(b.zone_types, "Power")]


def e_summary_2(b, rng):
    w, lights, d = _whole(b), _lighting(b), _date(b, rng)
    if not w or not lights or len(day(w, d)) < 24:
        return None
    lit = sum(sum(day(s, d)) for s in lights) * 3600          # W over hourly values -> J
    return (f"{LIGHTING_RULE} What fraction of the whole building's electricity on {d} went to lighting? Lighting "
            "power is metered per zone in watts (hourly values); the building meter is in joules per "
            "hour. Give a number between 0 and 1.", lit / sum(day(w, d)))


def e_comparison_2(b, rng):
    w = _whole(b)
    d1, d2 = _date(b, rng), _date(b, rng)
    if not w or d1 == d2 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    return (f"How much more electricity did the whole building use on {d1} than on {d2}, in joules? "
            "Give a negative value if it used less.", sum(day(w, d1)) - sum(day(w, d2)))


def e_comparison_3(b, rng):
    # canon energy L3 is Whole + Sub2 + OAT: without outside temperature the end-use split cannot be
    # told from a weather-driven change, so the class needs OAT like its cell
    w, lights, equip = _whole(b), _lighting(b), b.equipment_with("Power")
    if not b.building_series("OAT"):
        return None
    d1, d2 = _date(b, rng), _date(b, rng)
    if not (w and lights and equip) or d1 == d2 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    def joules(group, d):
        return sum(sum(day(s, d)) for s in group) * 3600
    hv = [b.of(e, "Power") for e in equip]
    delta = {"HVAC": joules(hv, d2) - joules(hv, d1), "lighting": joules(lights, d2) - joules(lights, d1)}
    delta["other"] = (sum(day(w, d2)) - sum(day(w, d1))) - delta["HVAC"] - delta["lighting"]
    ranked = sorted(delta.items(), key=lambda kv: -kv[1])
    if ranked[0][1] <= 0 or ranked[0][1] - ranked[1][1] < 0.05 * abs(ranked[0][1]):
        return None
    return (f"{LIGHTING_RULE} Between {d1} and {d2}, which end use increased its electricity use the most: HVAC "
            "(the metered HVAC equipment), lighting (the zone lighting meters), or other (the rest of "
            "the building meter)? Answer HVAC, lighting or other.", ranked[0][0])


def q_status_1(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    d, h = _date(b, rng), _hour(rng)
    v = b.of(e, "Power").get(f"{d}T{h:02d}") if e is not None else None
    return None if v is None else (
        f"What was the electrical power of {b.named(e)} at {d} {h:02d}:00, in watts?", v)


def q_status_2(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    if e is None:
        return None
    s = b.of(e, "Power")
    d, h = _date(b, rng), _hour(rng)
    v, peak = s.get(f"{d}T{h:02d}"), max(s.values(), default=0)
    return None if v is None or peak <= 0 else (
        f"At {d} {h:02d}:00, what was the electrical power of {b.named(e)} as a fraction of its own "
        "highest hourly value in the whole record? Give a number between 0 and 1.", v / peak)


def q_comparison_2(b, rng):
    equip, d = b.equipment_with("Power"), _date(b, rng)
    if len(equip) < 3:
        return None
    equip = rng.sample(equip, 3)            # a sampled trio, so the answer is not always the chiller
    use = sorted(((sum(day(b.of(e, "Power"), d)), e) for e in equip), key=lambda x: -x[0])
    if use[0][0] <= 0 or use[0][0] - use[1][0] < 0.05 * use[0][0]:
        return None
    names = ", ".join(sorted(b.named(e) for e in equip))
    return (f"Among {names}, which one used the most electricity on {d}? Answer with its name.",
            use[0][1])


def q_comparison_3(b, rng):
    equip = b.equipment_with("Power", "Flow", "Run")    # canon equipment L3: Pwr + Run + Load
    if len(equip) < 2:
        return None
    a, c = rng.sample(equip, 2)
    d = _date(b, rng)
    fa, fc = day(b.of(a, "Flow"), d), day(b.of(c, "Flow"), d)
    return None if not fa or not fc else (
        f"On {d}, what was the mean air flow of {b.named(a)} minus that of {b.named(c)}, over all "
        "hourly values, in the flow series' own unit?", sum(fa) / len(fa) - sum(fc) / len(fc))


def q_verification_3(b, rng):
    e = rng.choice(b.equipment_with("Power", "Run", "Flow") or [None])   # canon L3: Pwr + Run + Load
    if e is None:
        return None
    d = _date(b, rng)
    p, r = b.of(e, "Power"), b.of(e, "Run")
    keys = [k for k in sorted(p) if k.startswith(d) and k in r]
    return None if len(keys) < 24 else (
        f"On {d}, at how many hourly values did {b.named(e)} draw more than 1 W while its run signal "
        "was off (zero)?", sum(1 for k in keys if r[k] == 0 and p[k] > 1.0))


def a_status_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "CO2") or [None])
    d, h = _date(b, rng), _hour(rng)
    v = b.of(z, "CO2").get(f"{d}T{h:02d}") if z is not None else None
    return None if v is None else (
        f"What was the CO₂ concentration in zone {b.named(z)} at {d} {h:02d}:00, in ppm?", v)


def a_summary_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "CO2", "Occ") or [None])
    if z is None:
        return None
    d = _date(b, rng)
    c, o = b.of(z, "CO2"), b.of(z, "Occ")
    keys = [k for k in sorted(c) if k.startswith(d) and k in o]
    return None if len(keys) < 24 else (
        f"On {d}, at how many hourly values was zone {b.named(z)} occupied (occupancy above zero) "
        "with CO₂ above 800 ppm?", sum(1 for k in keys if o[k] > 0 and c[k] > 800))


def a_comparison_2(b, rng):
    zones = b.with_roles(b.zone_types, "CO2")
    if len(zones) < 2:
        return None
    a, c = rng.sample(zones, 2)
    d = _date(b, rng)
    va, vc = day(b.of(a, "CO2"), d), day(b.of(c, "CO2"), d)
    return None if not va or not vc else (
        f"On {d}, what was the mean CO₂ of zone {b.named(a)} minus that of zone {b.named(c)}, over "
        "all hourly values, in ppm?", sum(va) / len(va) - sum(vc) / len(vc))


def a_verification_3(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "CO2", "Occ", "OAF") or [None])
    if z is None:
        return None
    d = _date(b, rng)
    o, f = b.of(z, "Occ"), b.of(z, "OAF")
    occ = [f[k] for k in sorted(o) if k.startswith(d) and k in f and o[k] > 0]
    emp = [f[k] for k in sorted(o) if k.startswith(d) and k in f and o[k] == 0]
    return None if len(occ) < 3 or len(emp) < 3 else (
        f"On {d}, was the mean outdoor-air flow to zone {b.named(z)} higher at the occupied hourly "
        "values (occupancy above zero) than at the unoccupied ones?",
        sum(occ) / len(occ) > sum(emp) / len(emp))


def o_status_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    d, h = _date(b, rng), _hour(rng)
    v = b.of(z, "Occ").get(f"{d}T{h:02d}") if z is not None else None
    return None if v is None else (
        f"How many people were in zone {b.named(z)} at {d} {h:02d}:00?", v)


def o_summary_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    d = _date(b, rng)
    vals = hours(b.of(z, "Occ"), d, 8, 18) if z is not None else []
    return None if len(vals) < 11 else (
        f"What was the mean occupancy of zone {b.named(z)} on {d} over the hourly values from 08:00 "
        "to 18:00, both included, in people?", sum(vals) / len(vals))


def o_diagnosis_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    if z is None:
        return None
    d = _date(b, rng)
    o = b.of(z, "Occ")
    keys = [k for k in sorted(o) if k.startswith(d)]
    return None if len(keys) < 24 else (
        f"On {d}, at how many hourly values outside 08:00–18:00 (so before 08:00 or after 18:00) was "
        f"zone {b.named(z)} occupied (occupancy above zero)?",
        sum(1 for k in keys if o[k] > 0 and not 8 <= int(k[11:13]) <= 18))


def l_status_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Power", "Occ") or [None])
    if z is None:
        return None
    d, h = _date(b, rng), rng.randint(0, 23)
    p, o = b.of(z, "Power").get(f"{d}T{h:02d}"), b.of(z, "Occ").get(f"{d}T{h:02d}")
    return None if None in (p, o) else (
        f"{LIGHTING_RULE} At {d} {h:02d}:00, were the lights in zone {b.named(z)} on (lighting power above 1 W) while "
        "the zone was unoccupied (occupancy zero)?", p > 1.0 and o == 0)


def l_summary_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Power") or [None])
    d = _date(b, rng)
    vals = day(b.of(z, "Power"), d) if z is not None else []
    return None if len(vals) < 24 else (
        f"{LIGHTING_RULE} How much lighting energy did zone {b.named(z)} use on {d}, in joules? Lighting power is in "
        "watts at hourly values.", sum(vals) * 3600)


def l_comparison_2(b, rng):
    zones, d = b.with_roles(b.zone_types, "Power"), _date(b, rng)
    if len(zones) < 3:
        return None
    zones = rng.sample(zones, 3)
    use = sorted(((sum(day(b.of(z, "Power"), d)), z) for z in zones), key=lambda x: -x[0])
    if use[0][0] <= 0 or use[0][0] - use[1][0] < 0.05 * use[0][0]:
        return None
    names = ", ".join(sorted(b.named(z) for z in zones))
    return (f"{LIGHTING_RULE} Among zones {names}, which one used the most lighting energy on {d}? Answer with the "
            "zone's name.", use[0][1])


def l_diagnosis_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Power", "Occ") or [None])
    if z is None:
        return None
    d = _date(b, rng)
    p, o = b.of(z, "Power"), b.of(z, "Occ")
    keys = [k for k in sorted(p) if k.startswith(d) and k in o]
    return None if len(keys) < 24 else (
        f"{LIGHTING_RULE} On {d}, at how many hourly values were the lights in zone {b.named(z)} on (lighting power "
        "above 1 W) while the zone was unoccupied (occupancy zero)?",
        sum(1 for k in keys if p[k] > 1.0 and o[k] == 0))


# ── classes taken from the Mortar analytics applications ─────────────────────────────────────────
def t_verification_3_flow(b, rng):        # rogue_zone_airflow
    ok = set(b.with_roles(b.zone_types, "T", "SpCool", "ActC", "ActP"))    # posed where its rung holds
    e = rng.choice([x for x in b.any_with("Flow", "FlowSp") if x in ok] or [None])
    if e is None:
        return None
    d = _date(b, rng)
    f, sp = b.of(e, "Flow"), b.of(e, "FlowSp")
    keys = [k for k in sorted(f) if k.startswith(d) and k in sp]
    return None if len(keys) < 24 else (
        f"On {d}, at how many hourly values was the air flow of {b.named(e)} more than 10% away from "
        "its air flow setpoint? Count only hours with a setpoint above zero.",
        sum(1 for k in keys if sp[k] > 0 and abs(f[k] - sp[k]) > 0.10 * sp[k]))


def q_verification_3_simul(b, rng):       # simultaneous_heating_cooling_ahus
    # canon equipment L3: Pwr + Run + Load, so the unit also needs its power and its flow
    e = rng.choice(b.any_with("HeatV", "CoolV", "Power", "Flow") or [None])
    if e is None:
        return None
    d = _date(b, rng)
    hv, cv = b.of(e, "HeatV"), b.of(e, "CoolV")
    keys = [k for k in sorted(hv) if k.startswith(d) and k in cv]
    return None if len(keys) < 24 else (
        f"On {d}, at how many hourly values were the heating and the cooling valve signals of "
        f"{b.named(e)} both above zero?", sum(1 for k in keys if hv[k] > 0 and cv[k] > 0))


def e_comparison_3_weather(b, rng):       # energy_consumption_baseline, dr_evaluation
    w, oat = _whole(b), b.building_series("OAT")
    if not (_lighting(b) and b.equipment_with("Power")):    # Sub2: the full energy L3 requirement
        return None
    d1, d2 = _date(b, rng), _date(b, rng)
    if not w or not oat or d1 == d2:
        return None
    t1, t2 = day(oat, d1), day(oat, d2)
    if len(t1) < 24 or len(t2) < 24 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    dt = sum(t2) / 24 - sum(t1) / 24
    return None if abs(dt) < 2.0 else (
        f"From {d1} to {d2}, by how many joules did whole-building daily electricity use change per "
        "degree Celsius of change in the daily mean outside air temperature? Give (use on the second "
        "date minus use on the first) divided by (mean outside temperature on the second date minus "
        "that on the first).", (sum(day(w, d2)) - sum(day(w, d1))) / dt)


def e_summary_1_weekday(b, rng):          # weekday_mean_energy
    import datetime
    w = _whole(b)
    if not w:
        return None
    m = rng.choice(_SEASON_MONTHS)
    days = sorted({k[:10] for k in w if k.startswith(f"{b.year}-{m:02d}")})
    totals = [sum(day(w, d)) for d in days
              if datetime.date.fromisoformat(d).weekday() < 5 and len(day(w, d)) == 24]
    return None if len(totals) < 5 else (
        f"What was the mean daily whole-building electricity use over the weekdays (Monday to Friday) "
        f"of {b.year}-{m:02d} that have all 24 hourly values, in joules per day?",
        sum(totals) / len(totals))


def e_explanation_occ(b, rng):            # occupancy_energy_correlation
    # canon energy L3 is Whole + Sub2 + OAT: gate on the full rung, Occ on top
    if not (b.building_series("OAT") and _lighting(b) and b.equipment_with("Power")):
        return None
    w, zones = _whole(b), b.with_roles(b.zone_types, "Occ")
    d = _date(b, rng)
    if not w or not zones:
        return None
    keys = [k for k in sorted(w) if k.startswith(d) and all(k in b.of(z, "Occ") for z in zones)]
    if len(keys) < 24:
        return None
    occ = [sum(b.of(z, "Occ")[k] for z in zones) for k in keys]
    use = [w[k] for k in keys]
    mo, mu = sum(occ) / 24, sum(use) / 24
    cov = sum((o - mo) * (u - mu) for o, u in zip(occ, use))
    so, su = sum((o - mo) ** 2 for o in occ) ** 0.5, sum((u - mu) ** 2 for u in use) ** 0.5
    return None if so == 0 or su == 0 else (
        f"On {d}, what was the Pearson correlation between the hourly whole-building electricity use "
        "and the hourly total occupancy summed over all zones that have an occupancy series?",
        cov / (so * su))


# ── the 29 added classes (bara.run.ADDED_CLASSES): L1 of probed L2 cells, and the L1/L2 rungs
# of the diagnosis and explanation cells. L1 reports or compares raw values, or checks a value
# against a threshold the question states; L2 judges against the building's own reference (a
# setpoint, its own record, its own schedule). Same graders and conventions as the rest.
def _two_zones(b, role, rng):
    zones = b.with_roles(b.zone_types, role)
    return rng.sample(zones, 2) if len(zones) >= 2 else (None, None)


def t_comparison_1(b, rng):
    a, c = _two_zones(b, "T", rng)
    if a is None:
        return None
    d, h = _date(b, rng), _hour(rng)
    ta, tc = b.of(a, "T").get(f"{d}T{h:02d}"), b.of(c, "T").get(f"{d}T{h:02d}")
    return None if None in (ta, tc) or abs(ta - tc) < 0.2 else (
        f"At {d} {h:02d}:00, was the air temperature of zone {b.named(a)} higher than that of zone "
        f"{b.named(c)}?", ta > tc)


def t_verification_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T") or [None])
    d = _date(b, rng)
    vals = day(b.of(z, "T"), d) if z is not None else []
    if len(vals) < 24:
        return None
    limit = round(sum(vals) / 24 + rng.choice([-1, 0, 1, 2]))
    return (f"On {d}, did zone {b.named(z)} stay at or below {limit} °C at every one of its 24 "
            "hourly values?", max(vals) <= limit)


def _top_zone(items, gap):
    ranked = sorted(items, key=lambda kv: -kv[1])
    return None if len(ranked) < 2 or ranked[0][1] - ranked[1][1] < gap else ranked[0][0]


def t_diagnosis_1(b, rng):
    zones = b.with_roles(b.zone_types, "T")
    d, h = _date(b, rng), _hour(rng)
    temps = [(z, b.of(z, "T").get(f"{d}T{h:02d}")) for z in zones]
    if len(temps) < 2 or any(v is None for _, v in temps):
        return None
    top = _top_zone(temps, 0.2)
    return None if top is None else (
        f"At {d} {h:02d}:00, which zone had the highest air temperature among all zones that have "
        "an air temperature sensor? Answer with the zone's name.", top)


def t_diagnosis_2(b, rng):
    zones = b.with_roles(b.zone_types, "T", "SpCool")
    d, h = _date(b, rng), _hour(rng)
    devs = []
    for z in zones:
        t, sp = b.of(z, "T").get(f"{d}T{h:02d}"), b.of(z, "SpCool").get(f"{d}T{h:02d}")
        if None in (t, sp):
            return None
        devs.append((z, t - sp))
    top = _top_zone(devs, 0.2) if len(devs) >= 2 else None
    return None if top is None else (
        f"At {d} {h:02d}:00, which zone was farthest above its own cooling setpoint (largest value of "
        "temperature minus cooling setpoint) among all zones that have both? Answer with the zone's "
        "name.", top)


def t_explanation_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T") or [None])
    d1, d2 = _date(b, rng), _date(b, rng)
    if z is None or d1 == d2:
        return None
    v1, v2 = day(b.of(z, "T"), d1), day(b.of(z, "T"), d2)
    return None if len(v1) < 24 or len(v2) < 24 else (
        f"By how much did the mean air temperature of zone {b.named(z)} change from {d1} to {d2}, "
        "in °C? Give the mean on the second date minus the mean on the first, each over all 24 "
        "hourly values.", sum(v2) / 24 - sum(v1) / 24)


def t_explanation_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "T", "SpCool") or [None])
    d1, d2 = _date(b, rng), _date(b, rng)
    if z is None or d1 == d2:
        return None
    t, sp = b.of(z, "T"), b.of(z, "SpCool")
    def dev(d):
        keys = [f"{d}T{h:02d}" for h in range(8, 19)]
        return None if any(k not in t or k not in sp for k in keys) else \
            sum(t[k] - sp[k] for k in keys) / len(keys)
    a, c = dev(d1), dev(d2)
    if None in (a, c) or abs(c - a) < 0.2:
        return None
    return (f"Over the hourly values from 08:00 to 18:00 (both included), the mean deviation of zone "
            f"{b.named(z)} from its cooling setpoint (temperature minus setpoint) was compared between "
            f"{d1} and {d2}. Did that mean deviation increase or decrease from the first date to the "
            "second? Answer increase or decrease.", "increase" if c > a else "decrease")


def e_comparison_1(b, rng):
    w = _whole(b)
    d1, d2 = _date(b, rng), _date(b, rng)
    if not w or d1 == d2 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    u1, u2 = sum(day(w, d1)), sum(day(w, d2))
    return None if abs(u1 - u2) < 0.02 * max(u1, u2) else (
        f"Did the whole building use more electricity on {d1} than on {d2}?", u1 > u2)


def _daily(w, month):
    days = sorted({k[:10] for k in w if k.startswith(month)})
    return {d: sum(day(w, d)) for d in days if len(day(w, d)) == 24}


def e_diagnosis_1(b, rng):
    w = _whole(b)
    if not w:
        return None
    m = f"{b.year}-{rng.choice(_SEASON_MONTHS):02d}"
    totals = _daily(w, m)
    if len(totals) < 5:
        return None
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    runner_up = next((v for _, v in ranked[1:] if v < ranked[0][1]), None)
    if runner_up is not None and ranked[0][1] - runner_up < 0.01 * ranked[0][1]:
        return None                                   # a near tie is not a fair question
    return (f"In {m}, on which date did the whole building use the most electricity, counting only "
            "dates with all 24 hourly values? If several dates tie, give the earliest. Answer as "
            "YYYY-MM-DD.", ranked[0][0])


def e_diagnosis_2(b, rng):
    w = _whole(b)
    if not w:
        return None
    m = f"{b.year}-{rng.choice(_SEASON_MONTHS):02d}"
    totals = _daily(w, m)
    if len(totals) < 5:
        return None
    mean = sum(totals.values()) / len(totals)
    return (f"In {m}, on how many dates (counting only dates with all 24 hourly values) was the "
            "whole building's daily electricity use more than 10% above the mean daily use of those "
            "dates?", sum(1 for v in totals.values() if v > 1.10 * mean))


def e_explanation_1(b, rng):
    w = _whole(b)
    d1, d2 = _date(b, rng), _date(b, rng)
    if not w or d1 == d2 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    u1, u2 = sum(day(w, d1)), sum(day(w, d2))
    return None if u1 <= 0 or u1 == u2 else (
        f"By what fraction did whole-building daily electricity use change from {d1} to {d2}? Give "
        "(use on the second date minus use on the first) divided by use on the first date.",
        (u2 - u1) / u1)


def _occ_split(series, d1, d2):
    """Absolute change between two dates in the occupied (08-18) and the other hours."""
    occ = sum(series.get(f"{d2}T{h:02d}", 0) - series.get(f"{d1}T{h:02d}", 0) for h in range(8, 19))
    rest = sum(series.get(f"{d2}T{h:02d}", 0) - series.get(f"{d1}T{h:02d}", 0)
               for h in list(range(0, 8)) + list(range(19, 24)))
    return abs(occ), abs(rest)


def e_explanation_2(b, rng):
    w = _whole(b)
    d1, d2 = _date(b, rng), _date(b, rng)
    if not w or d1 == d2 or len(day(w, d1)) < 24 or len(day(w, d2)) < 24:
        return None
    occ, rest = _occ_split(w, d1, d2)
    return None if abs(occ - rest) < 0.05 * max(occ, rest, 1e-9) else (
        f"Between {d1} and {d2}, did whole-building electricity use change more, in absolute joules "
        "summed over hours, during the occupied hours 08:00 to 18:00 (both included) or during the "
        "other hours of the day? Answer occupied or unoccupied.", "occupied" if occ > rest else "unoccupied")


def q_comparison_1(b, rng):
    equip = b.equipment_with("Power")
    if len(equip) < 2:
        return None
    a, c = rng.sample(equip, 2)
    d, h = _date(b, rng), _hour(rng)
    pa, pc = b.of(a, "Power").get(f"{d}T{h:02d}"), b.of(c, "Power").get(f"{d}T{h:02d}")
    return None if None in (pa, pc) or abs(pa - pc) < 0.05 * max(pa, pc, 1e-9) else (
        f"At {d} {h:02d}:00, did {b.named(a)} draw more electrical power than {b.named(c)}?", pa > pc)


def q_summary_1(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    d = _date(b, rng)
    vals = day(b.of(e, "Power"), d) if e is not None else []
    return None if len(vals) < 24 else (
        f"What was the mean electrical power of {b.named(e)} on {d} over all 24 hourly values, in "
        "watts?", sum(vals) / 24)


def q_summary_2(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    if e is None:
        return None
    s, d = b.of(e, "Power"), _date(b, rng)
    vals, peak = day(s, d), max(s.values(), default=0)
    return None if len(vals) < 24 or peak <= 0 else (
        f"On {d}, at how many of its 24 hourly values was the electrical power of {b.named(e)} above "
        "half of its own highest hourly value in the whole record?", sum(1 for v in vals if v > 0.5 * peak))


def q_verification_1(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    if e is None:
        return None
    s, d = b.of(e, "Power"), _date(b, rng)
    vals, peak = day(s, d), max(s.values(), default=0)
    if len(vals) < 24 or peak <= 0:
        return None
    limit = round(peak * rng.choice([0.5, 0.95, 1.05]))
    return (f"On {d}, did {b.named(e)} draw more than {limit} W at any of its 24 hourly values?",
            max(vals) > limit)


def q_verification_2(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    if e is None:
        return None
    s, d = b.of(e, "Power"), _date(b, rng)
    vals, peak = day(s, d), max(s.values(), default=0)
    return None if len(vals) < 24 or peak <= 0 else (
        f"On {d}, did the electrical power of {b.named(e)} stay below 90% of its own highest hourly "
        "value in the whole record at every one of its 24 hourly values?", max(vals) < 0.9 * peak)


def q_diagnosis_1(b, rng):
    equip = b.equipment_with("Power")
    d, h = _date(b, rng), _hour(rng)
    vals = [(e, b.of(e, "Power").get(f"{d}T{h:02d}")) for e in equip]
    if len(vals) < 2 or any(v is None for _, v in vals):
        return None
    top = _top_zone(vals, 0.05 * max(v for _, v in vals))
    return None if top is None else (
        f"At {d} {h:02d}:00, which item of equipment drew the most electrical power among all "
        "equipment with a power sensor? Answer with its name.", top)


def q_diagnosis_2(b, rng):
    equip, d = b.equipment_with("Power"), _date(b, rng)
    if len(equip) < 3:
        return None
    equip = rng.sample(equip, 3)
    ratios = []
    for e in equip:
        s = b.of(e, "Power")
        vals, peak = day(s, d), max(s.values(), default=0)
        if len(vals) < 24 or peak <= 0:
            return None
        ratios.append((e, max(vals) / peak))
    top = _top_zone(ratios, 0.05)
    names = ", ".join(sorted(b.named(e) for e in equip))
    return None if top is None else (
        f"On {d}, which of {names} ran closest to its own highest hourly power in the whole record "
        "(largest ratio of that day's highest hourly power to its record high)? Answer with its name.", top)


def q_explanation_1(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    d1, d2 = _date(b, rng), _date(b, rng)
    if e is None or d1 == d2:
        return None
    s = b.of(e, "Power")
    v1, v2 = day(s, d1), day(s, d2)
    if len(v1) < 24 or len(v2) < 24 or sum(v1) == sum(v2):
        return None
    return (f"By how many joules did the daily electricity use of {b.named(e)} change from {d1} to "
            f"{d2}? Give use on the second date minus use on the first; power is in watts at hourly "
            "values.", (sum(v2) - sum(v1)) * 3600)


def q_explanation_2(b, rng):
    e = rng.choice(b.equipment_with("Power") or [None])
    d1, d2 = _date(b, rng), _date(b, rng)
    if e is None or d1 == d2:
        return None
    s = b.of(e, "Power")
    if len(day(s, d1)) < 24 or len(day(s, d2)) < 24:
        return None
    occ, rest = _occ_split(s, d1, d2)
    return None if abs(occ - rest) < 0.05 * max(occ, rest, 1e-9) else (
        f"Between {d1} and {d2}, did the electricity use of {b.named(e)} change more, in absolute "
        "terms summed over hours, during the occupied hours 08:00 to 18:00 (both included) or during "
        "the other hours of the day? Answer occupied or unoccupied.", "occupied" if occ > rest else "unoccupied")


def l_status_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Power") or [None])
    d, h = _date(b, rng), _hour(rng)
    v = b.of(z, "Power").get(f"{d}T{h:02d}") if z is not None else None
    return None if v is None else (
        f"{LIGHTING_RULE} What was the lighting power of zone {b.named(z)} at {d} {h:02d}:00, in watts?", v)


def l_summary_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Power") or [None])
    d = _date(b, rng)
    vals = day(b.of(z, "Power"), d) if z is not None else []
    return None if len(vals) < 24 else (
        f"{LIGHTING_RULE} What was the mean lighting power of zone {b.named(z)} on {d} over all 24 hourly "
        "values, in watts?", sum(vals) / 24)


def l_comparison_1(b, rng):
    a, c = _two_zones(b, "Power", rng)
    if a is None:
        return None
    d, h = _date(b, rng), _hour(rng)
    pa, pc = b.of(a, "Power").get(f"{d}T{h:02d}"), b.of(c, "Power").get(f"{d}T{h:02d}")
    return None if None in (pa, pc) or abs(pa - pc) < 0.05 * max(pa, pc, 1e-9) else (
        f"{LIGHTING_RULE} At {d} {h:02d}:00, was the lighting power of zone {b.named(a)} higher than that of "
        f"zone {b.named(c)}?", pa > pc)


def l_diagnosis_1(b, rng):
    zones = b.with_roles(b.zone_types, "Power")
    d, h = _date(b, rng), _hour(rng)
    vals = [(z, b.of(z, "Power").get(f"{d}T{h:02d}")) for z in zones]
    if len(vals) < 2 or any(v is None for _, v in vals):
        return None
    top = _top_zone(vals, 0.05 * max(v for _, v in vals))
    return None if top is None else (
        f"{LIGHTING_RULE} At {d} {h:02d}:00, which zone had the highest lighting power among all zones with a "
        "lighting meter? Answer with the zone's name.", top)


def o_status_2(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    if z is None:
        return None
    d, h = _date(b, rng), rng.randint(0, 23)
    o = b.of(z, "Occ")
    v, ref = o.get(f"{d}T{h:02d}"), hours(o, d, 8, 18)
    if v is None or len(ref) < 11 or v == sum(ref) / len(ref):
        return None
    return (f"At {d} {h:02d}:00, were there more people in zone {b.named(z)} than its own mean "
            f"occupancy over the hourly values from 08:00 to 18:00 (both included) on {d}?",
            v > sum(ref) / len(ref))


def o_summary_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    d = _date(b, rng)
    vals = day(b.of(z, "Occ"), d) if z is not None else []
    return None if len(vals) < 24 else (
        f"What was the highest hourly occupancy of zone {b.named(z)} on {d}, in people?", max(vals))


def o_comparison_1(b, rng):
    a, c = _two_zones(b, "Occ", rng)
    if a is None:
        return None
    d, h = _date(b, rng), _hour(rng)
    oa, oc = b.of(a, "Occ").get(f"{d}T{h:02d}"), b.of(c, "Occ").get(f"{d}T{h:02d}")
    return None if None in (oa, oc) or abs(oa - oc) < 1 else (
        f"At {d} {h:02d}:00, were there more people in zone {b.named(a)} than in zone {b.named(c)}?",
        oa > oc)


def o_comparison_2(b, rng):
    a, c = _two_zones(b, "Occ", rng)
    if a is None:
        return None
    d = _date(b, rng)
    va, vc = hours(b.of(a, "Occ"), d, 8, 18), hours(b.of(c, "Occ"), d, 8, 18)
    return None if len(va) < 11 or len(vc) < 11 else (
        f"On {d}, what was the mean occupancy of zone {b.named(a)} minus that of zone {b.named(c)}, "
        "over the hourly values from 08:00 to 18:00 (both included), in people?",
        sum(va) / len(va) - sum(vc) / len(vc))


def o_diagnosis_1(b, rng):
    z = rng.choice(b.with_roles(b.zone_types, "Occ") or [None])
    d = _date(b, rng)
    o = b.of(z, "Occ") if z is not None else {}
    keys = [k for k in sorted(o) if k.startswith(d)]
    if len(keys) < 24 or max(o[k] for k in keys) <= 0:
        return None
    best = max(keys, key=lambda k: (o[k], -int(k[11:13])))
    return (f"On {d}, at which hour of the day (0 to 23) did zone {b.named(z)} have the most people? "
            "If several hours tie, give the earliest.", int(best[11:13]))


N, B, E = "number", "boolean", "entity"
BANK: tuple[tuple[QClass, object], ...] = (
    (QClass("t_status_1", "thermal", "status", 1, ("T",), N, tol_abs=0.5), t_status_1),
    (QClass("t_status_2", "thermal", "status", 2, ("T", "Sp"), N, tol_abs=0.5), t_status_2),
    (QClass("t_summary_1", "thermal", "summary", 1, ("T",), N, tol_abs=0.5), t_summary_1),
    (QClass("t_summary_2", "thermal", "summary", 2, ("T", "Sp"), N, tol_abs=1), t_summary_2),
    (QClass("t_comparison_2", "thermal", "comparison", 2, ("T",), N, tol_abs=0.5), t_comparison_2),
    (QClass("t_comparison_2hop", "thermal", "comparison", 2, ("T",), E, hops=2), t_comparison_2hop),
    (QClass("t_comparison_3", "thermal", "comparison", 3, ("T", "Sp", "ActC", "ActP"), N, tol_rel=0.05, tol_abs=0.01),
     t_comparison_3),
    (QClass("t_verification_2", "thermal", "verification", 2, ("T", "Sp"), B), t_verification_2),
    (QClass("t_verification_3", "thermal", "verification", 3, ("T", "Sp", "ActC", "ActP"), N, tol_rel=0.05,
            tol_abs=0.01), t_verification_3),
    (QClass("e_status_1", "energy", "status", 1, ("Whole",), N, tol_rel=0.02), e_status_1),
    (QClass("e_summary_1", "energy", "summary", 1, ("Whole",), N, tol_rel=0.02), e_summary_1),
    (QClass("e_summary_2", "energy", "summary", 2, ("Whole", "Sub"), N, tol_abs=0.02), e_summary_2),
    (QClass("e_comparison_2", "energy", "comparison", 2, ("Whole",), N, tol_rel=0.02), e_comparison_2),
    (QClass("e_comparison_3", "energy", "comparison", 3, ("Whole", "Sub2", "OAT"), E, hops=2), e_comparison_3),
    (QClass("q_status_1", "equipment", "status", 1, ("Pwr",), N, tol_rel=0.02, tol_abs=1), q_status_1),
    (QClass("q_status_2", "equipment", "status", 2, ("Pwr",), N, tol_abs=0.02), q_status_2),
    (QClass("q_comparison_2", "equipment", "comparison", 2, ("Pwr",), E, hops=2), q_comparison_2),
    (QClass("q_comparison_3", "equipment", "comparison", 3, ("Pwr", "Run", "Load"), N, tol_rel=0.05),
     q_comparison_3),
    (QClass("q_verification_3", "equipment", "verification", 3, ("Pwr", "Run", "Load"), N, tol_abs=1),
     q_verification_3),
    (QClass("a_status_1", "airquality", "status", 1, ("CO2",), N, tol_rel=0.02), a_status_1),
    (QClass("a_summary_2", "airquality", "summary", 2, ("CO2", "Occ"), N, tol_abs=1), a_summary_2),
    (QClass("a_comparison_2", "airquality", "comparison", 2, ("CO2",), N, tol_rel=0.05, tol_abs=5),
     a_comparison_2),
    (QClass("a_verification_3", "airquality", "verification", 3, ("CO2", "Occ", "OAF"), B),
     a_verification_3),
    (QClass("o_status_1", "occupancy", "status", 1, ("Occ",), N, tol_abs=1, tol_rel=0.05), o_status_1),
    (QClass("o_summary_2", "occupancy", "summary", 2, ("Occ",), N, tol_abs=1, tol_rel=0.05), o_summary_2),
    (QClass("o_diagnosis_2", "occupancy", "diagnosis", 2, ("Occ",), N, tol_abs=1), o_diagnosis_2),
    (QClass("l_status_2", "lighting", "status", 2, ("Lgt", "Occ"), B), l_status_2),
    (QClass("l_summary_2", "lighting", "summary", 2, ("Lgt",), N, tol_rel=0.02), l_summary_2),
    (QClass("l_comparison_2", "lighting", "comparison", 2, ("Lgt",), E, hops=2), l_comparison_2),
    (QClass("l_diagnosis_2", "lighting", "diagnosis", 2, ("Lgt", "Occ"), N, tol_abs=1), l_diagnosis_2),
    (QClass("t_verification_3_flow", "thermal", "verification", 3, ("T", "Sp", "ActC", "ActP"), N, tol_abs=1),
     t_verification_3_flow),
    (QClass("q_verification_3_simul", "equipment", "verification", 3, ("Pwr", "Run", "Load"), N, tol_abs=1),
     q_verification_3_simul),
    (QClass("e_comparison_3_weather", "energy", "comparison", 3, ("Whole", "Sub2", "OAT"), N, tol_rel=0.05),
     e_comparison_3_weather),
    (QClass("e_summary_1_weekday", "energy", "summary", 1, ("Whole",), N, tol_rel=0.02),
     e_summary_1_weekday),
    (QClass("e_explanation_occ", "energy", "explanation", 3, ("Whole", "Sub2", "OAT", "Occ"), N, tol_abs=0.05),
     e_explanation_occ),
    # the 29 added classes, for the rungs the first 35 leave unprobed (bara.run.ADDED_CLASSES)
    (QClass("t_comparison_1", "thermal", "comparison", 1, ("T",), B), t_comparison_1),
    (QClass("t_verification_1", "thermal", "verification", 1, ("T",), B), t_verification_1),
    (QClass("t_diagnosis_1", "thermal", "diagnosis", 1, ("T",), E), t_diagnosis_1),
    (QClass("t_diagnosis_2", "thermal", "diagnosis", 2, ("T", "Sp"), E), t_diagnosis_2),
    (QClass("t_explanation_1", "thermal", "explanation", 1, ("T",), N, tol_abs=0.5), t_explanation_1),
    (QClass("t_explanation_2", "thermal", "explanation", 2, ("T", "Sp"), E), t_explanation_2),
    (QClass("e_comparison_1", "energy", "comparison", 1, ("Whole",), B), e_comparison_1),
    (QClass("e_diagnosis_1", "energy", "diagnosis", 1, ("Whole",), E), e_diagnosis_1),
    (QClass("e_diagnosis_2", "energy", "diagnosis", 2, ("Whole",), N, tol_abs=1), e_diagnosis_2),
    (QClass("e_explanation_1", "energy", "explanation", 1, ("Whole",), N, tol_abs=0.01, tol_rel=0.05), e_explanation_1),
    (QClass("e_explanation_2", "energy", "explanation", 2, ("Whole",), E), e_explanation_2),
    (QClass("q_comparison_1", "equipment", "comparison", 1, ("Pwr",), B), q_comparison_1),
    (QClass("q_summary_1", "equipment", "summary", 1, ("Pwr",), N, tol_abs=1, tol_rel=0.02), q_summary_1),
    (QClass("q_summary_2", "equipment", "summary", 2, ("Pwr",), N, tol_abs=1), q_summary_2),
    (QClass("q_verification_1", "equipment", "verification", 1, ("Pwr",), B), q_verification_1),
    (QClass("q_verification_2", "equipment", "verification", 2, ("Pwr",), B), q_verification_2),
    (QClass("q_diagnosis_1", "equipment", "diagnosis", 1, ("Pwr",), E), q_diagnosis_1),
    (QClass("q_diagnosis_2", "equipment", "diagnosis", 2, ("Pwr",), E), q_diagnosis_2),
    (QClass("q_explanation_1", "equipment", "explanation", 1, ("Pwr",), N, tol_rel=0.05), q_explanation_1),
    (QClass("q_explanation_2", "equipment", "explanation", 2, ("Pwr",), E), q_explanation_2),
    (QClass("l_status_1", "lighting", "status", 1, ("Lgt",), N, tol_abs=1, tol_rel=0.02), l_status_1),
    (QClass("l_summary_1", "lighting", "summary", 1, ("Lgt",), N, tol_abs=1, tol_rel=0.02), l_summary_1),
    (QClass("l_comparison_1", "lighting", "comparison", 1, ("Lgt",), B), l_comparison_1),
    (QClass("l_diagnosis_1", "lighting", "diagnosis", 1, ("Lgt",), E), l_diagnosis_1),
    (QClass("o_status_2", "occupancy", "status", 2, ("Occ",), B), o_status_2),
    (QClass("o_summary_1", "occupancy", "summary", 1, ("Occ",), N, tol_abs=1, tol_rel=0.05), o_summary_1),
    (QClass("o_comparison_1", "occupancy", "comparison", 1, ("Occ",), B), o_comparison_1),
    (QClass("o_comparison_2", "occupancy", "comparison", 2, ("Occ",), N, tol_abs=1, tol_rel=0.05), o_comparison_2),
    (QClass("o_diagnosis_1", "occupancy", "diagnosis", 1, ("Occ",), N, tol_abs=0), o_diagnosis_1),
)
SHAPES = {N: '{"value": <number>}', B: '{"value": <true|false>}', E: '{"entity": "<name>"}'}


def build_bank(kg_ttl: Path, store_dir: Path, *, n: int = 5, seed: int = 0, tries: int = 40,
               zone_types: set[str] | None = None) -> list[dict]:
    """Up to *n* distinct instances per question class, ground truth included (key "gold").
    Deterministic in *seed*."""
    b = Building(kg_ttl, store_dir, zone_types)
    out = []
    for qc, template in BANK:
        rng, seen = random.Random(f"{seed}:{qc.cid}"), set()
        for _ in range(tries):
            if len(seen) == n:
                break
            made = template(b, rng)
            if made is None or made[0] in seen:
                continue
            seen.add(made[0])
            gold, aliases = made[1], None
            if isinstance(gold, float):
                gold = round(gold, 6)
            elif qc.answer_type == E and isinstance(gold, URIRef):     # a graph entity
                gold, aliases = b.label(gold), b.aliases(gold)
            out.append({"question_id": f"{qc.cid}#{len(seen)}", "class": qc.cid, "domain": qc.domain,
                        "intent": qc.intent, "level": qc.level, "hops": qc.hops,
                        "requires": list(qc.requires), "answer_type": qc.answer_type,
                        "text": made[0], "schema": SHAPES[qc.answer_type], "gold": gold,
                        **({"aliases": aliases} if aliases else {})})
    return out


def grade(question: dict, answer: dict | None) -> float:
    """1.0 or 0.0 against the class's tolerance, fixed before any run; a missing answer scores 0."""
    qc = next(c for c, _ in BANK if c.cid == question["class"])
    gold = question["gold"]
    if not isinstance(answer, dict):
        return 0.0
    if qc.answer_type == E:
        norm = lambda s: "".join(ch for ch in str(s).lower() if ch.isalnum())
        accepted = {norm(gold)} | {norm(a) for a in question.get("aliases", [])}
        return float(norm(answer.get("entity")) in accepted)
    got = answer.get("value")
    if qc.answer_type == B:
        return float(isinstance(got, bool) and got == gold)
    try:
        return float(abs(float(got) - gold) <= max(qc.tol_abs, qc.tol_rel * abs(gold)))
    except (TypeError, ValueError):
        return 0.0
