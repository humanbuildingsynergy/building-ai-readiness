"""Graphs and stores: where a building's data are, which stream class each stored point realizes,
and the restricted copies the sweep and the diagnosis rungs run on."""
from __future__ import annotations

import csv
import functools
import json
from pathlib import Path

from rdflib import Graph, Namespace

from bara import BATS_DIR, DERIVED_DIR, RESULTS_DIR, canon, census, graphfix

REF = Namespace("https://brickschema.org/schema/Brick/ref#")
RESTRICTED = DERIVED_DIR / "restricted"


def bats_folder(building: str) -> Path:
    for sub in ("buildings", "faulted"):
        if (BATS_DIR / sub / building / "kg.ttl").exists():
            return BATS_DIR / sub / building
    raise FileNotFoundError(f"{building} is not in BATS_DIR={BATS_DIR} (run scripts/fetch_data.py)")


def bank_paths(building: str, kg: str = "kg.ttl") -> tuple[Path, Path]:
    """(graph, store) of a BATS building. *kg* is ``kg.ttl`` (published) or ``linked`` (the
    published graph plus the inverse of every hasPoint / isPointOf triple, bara.graphfix)."""
    folder = bats_folder(building)
    if kg == "linked":
        graph = graphfix._OUT / building / "kg_linked.ttl"
        if not graph.exists():
            graphfix.add_inverses(folder / "kg.ttl", graph)
        return graph, folder
    return (Path(kg) if Path(kg).is_absolute() else folder / kg), folder


@functools.lru_cache(maxsize=1)
def _clf():
    return census._Classifier(census.Ontology())


def point_streams(kg: Path, store: Path) -> dict[str, set[str]]:
    """series id -> stream classes of its point, by the census rules (one point at a time)."""
    clf = _clf()
    types, parents, owners, _feeds, _linked = census._load(kg)
    g = Graph().parse(str(kg), format="turtle")
    in_store = {r["timeseries_id"] for r in csv.DictReader((store / "points.csv").open(encoding="utf-8"))}
    out: dict[str, set[str]] = {}
    for p, ext in g.subject_objects(REF.hasExternalReference):
        tsid = g.value(ext, REF.hasTimeseriesId)
        if tsid is None or str(tsid) not in in_store:
            continue
        ts, att, have = types[p], census._attachment(p, types, parents, owners, clf), set()
        for rule, roots, generic in clf.rules:
            if (ts & roots and (bool(att & set(rule.attached)) or not rule.roots_need_attachment)) \
                    or (ts & generic and att & set(rule.attached)):
                have.add(rule.stream)
        if ts & clf.whole or (ts & clf.metered and "building" in att):
            have.add("Whole")
        elif ts & clf.metered:
            if "lighting" in att or (census.ZONE_POWER_IS_LIGHTING and "zone" in att
                                     and not att & {"central", "terminal"}):
                have.add("Lgt")
            elif att & {"central", "terminal"}:
                have.add("Pwr")
        out[str(tsid)] = have
    return out


def _copy(src: Path, keep: set[str], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for fname in ("points.csv", "timeseries.csv"):
        with (src / fname).open(encoding="utf-8", newline="") as f, \
             (out / fname).open("w", encoding="utf-8", newline="") as g:
            r, w = csv.reader(f), csv.writer(g)
            w.writerow(next(r))
            for row in r:
                if row and row[0] in keep:
                    w.writerow(row)
    return out


def restrict(building: str, keep: set[str], name: str) -> Path:
    """Copy of a BATS store holding only the points whose stream class is in *keep*."""
    kg, store = bank_paths(building, "linked")
    ids = {t for t, s in point_streams(kg, store).items() if s & keep}
    return _copy(store, ids, RESTRICTED / f"{building}__{name}")


def rung_store(kg: Path, src: Path, streams: set[str], name: str) -> Path:
    """Copy of *src* holding only the stream classes in scope. A scheduled setpoint (Occupied_*)
    counts as SpC here, never as Sp, so it appears only on a rung that puts SpC in scope; the
    supplement's damper position counts as ActP."""
    classes = {r["timeseries_id"]: r["point_class"] for r in
               csv.DictReader((src / "points.csv").open(encoding="utf-8"))}
    keep = set()
    for tid, s in point_streams(kg, src).items():
        s = {"SpC"} if classes[tid].startswith(("Occupied_", "Unoccupied_")) else s
        # the supplement's damper series is the simulated damper position (EnergyPlus "Zone Air Terminal
        # VAV Damper Position"), typed with the class the BATS graph declares; it is the response, ActP
        s = {"ActP"} if classes[tid] == "Damper_Position_Setpoint" else s
        if s & streams:
            keep.add(tid)
    return _copy(src, keep, RESTRICTED / name)


def store_ceiling(kg: Path, store: Path) -> canon.Ceiling:
    """Ceiling of the streams a store actually holds, by the census rules."""
    have: set[str] = set().union(set(), *point_streams(kg, store).values())
    have |= canon.end_use_streams({canon.END_USE[s] for s in have if s in canon.END_USE})
    return canon.ceiling(have)


def profile_ceiling(building: str, profile: str | None) -> canon.Ceiling:
    kg, store = bank_paths(building, "linked")
    have: set[str] = set().union(*point_streams(kg, store).values())
    if profile:
        have &= canon.PROFILES[profile]
    have |= canon.end_use_streams({canon.END_USE[s] for s in have if s in canon.END_USE})
    return canon.ceiling(have)


# ── deposited ceilings (level 1 reads them; level 2 recomputes them from BATS) ────────────────
CEILINGS = RESULTS_DIR / "ceilings.json"


def ceiling_record(c: canon.Ceiling) -> dict:
    return {"achieved": c.achieved, "total": c.total, "streams": sorted(c.streams),
            "per_cell": [[d, i, lv] for (d, i), lv in sorted(c.per_cell.items())]}


def ceiling_from_record(rec: dict) -> canon.Ceiling:
    return canon.ceiling(set(rec["streams"]))


def deposited_ceiling(building: str, profile: str | None) -> canon.Ceiling:
    """The ceiling as deposited in results/ceilings.json; recomputed from BATS when it is absent."""
    if CEILINGS.exists():
        rec = json.loads(CEILINGS.read_text(encoding="utf-8")).get(building, {}).get(profile or "full")
        if rec is not None:
            return ceiling_from_record(rec)
    return profile_ceiling(building, profile)


def compute_ceilings(sweep: str = "large_office__2a_tampa",
                     profiles=("minimal", "comfort", "standard", "rich"), path: Path = CEILINGS) -> dict:
    """results/ceilings.json from BATS: the sweep building per profile (with the streams of its
    restricted store) and every BATS building's full store."""
    out: dict = {}
    for b in sorted(p.name for p in (BATS_DIR / "buildings").iterdir() if (p / "kg.ttl").exists()):
        out[b] = {"full": ceiling_record(profile_ceiling(b, None))}
    kg = bank_paths(sweep, "linked")[0]
    for prof in profiles:
        rec = ceiling_record(profile_ceiling(sweep, prof))
        rec["store_streams"] = sorted(store_ceiling(kg, restrict(sweep, canon.PROFILES[prof], prof)).streams)
        out[sweep][prof] = rec
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    return out
