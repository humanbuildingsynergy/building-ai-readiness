"""A small supplement to BATS v1.0 that makes L3 cause attribution testable.

BATS v1.0 exports no stream that separates the causes in its fault scenarios. This module adds the
two that the diagnosis scenarios need, for the large office in Tampa (2A):

  SpC  the scheduled cooling setpoint, next to the setpoint in effect. BuildStream already
       simulated it (EnergyPlus "Schedule Value" of CLGSETP_SCH_YES_OPTIMUM); the release omits it.
  ActP the VAV terminal damper position (the actuation response). Not simulated in v1.0;
       EnergyPlus reports it once the output variable "Zone Air Terminal VAV Damper Position" is
       requested.

and two paired scenarios whose base streams look like an existing one but whose cause differs:

  s1r  schedule change: Core_bottom's own heating and cooling setpoint schedules lowered by 1 C
       from 2018-06-15 (the look-alike of s1, the thermostat offset from the same date)
  s4   internal-load step: a new always-on equipment load in Core_mid from 2018-07-01 (the
       look-alike of s3m, the drifting Core_mid reading)

Every simulation is EnergyPlus 22.1 on the model file BuildStream wrote for the release, run with
the release's own command line (-w <epw> -d <dir> -r) and weather file. A re-run with only the damper
output added reproduces all 213 release columns exactly over 8,760 hours (checked in ``verify``),
so the supplement agrees with BATS v1.0 wherever both have a stream. BuildStream (frozen at v1.0)
is not imported or changed; its output files are read as data.

This is the provenance of the deposited supplement (supplement/); the reproduction levels never run
it. It needs EnergyPlus 22.1 (EPLUS_EXE), the Tampa TMY3 weather file (BATS_EPW) and the EnergyPlus
model files BuildStream v1.0 wrote for the release (BS_CORPUS: one folder per building with ep/
holding model.idf and its outputs), which are not part of the BATS release. Everything it writes
goes to $DERIVED_DIR/supplement_build (ROOT), never into supplement/ or results/: the package, the
merged stores and the scenario manifest (ROOT/scenarios_supplement.json, the same scenarios as the
deposited results/faults/scenarios_supplement.json).

    python -m bara.supplement            # simulate, write the package, the merged stores, the manifest
    python -m bara.supplement checks     # ... and print the look-alike and separation checks
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import re
import shutil
import subprocess
import uuid
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from bara import BATS_DIR, DATA_DIR, DERIVED_DIR, graphfix
from bara.drift import drift, label

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
BS_CORPUS = Path(os.environ.get("BS_CORPUS", DATA_DIR / "buildstream_corpus"))
EPW = Path(os.environ.get("BATS_EPW", DATA_DIR / "weather" / "USA_FL_Tampa-MacDill.AFB.747880_TMY3.epw"))
EPLUS = os.environ.get("EPLUS_EXE", "energyplus")
ROOT = DERIVED_DIR / "supplement_build"
WORK, PACKAGE, MERGED = ROOT / "work", ROOT / "package" / "bats_v1.0_l3_supplement", ROOT / "merged"
B = "large_office__2a_tampa"
DAMPER_VAR = "Zone Air Terminal VAV Damper Position"
S1R_ONSET, S4_ONSET = ("06/14", "06/15"), ("06/30", "07/01")   # last day before, first day of
S1R_DELTA_C = -1.0                                              # matches s1's 1 C thermostat offset
S4_WATTS = float(os.environ.get("S4_WATTS", "40000"))          # the added always-on load, W
DECIMALS = 3                  # BuildStream's linking step rounds every published value to 3 decimals
ROUND_TOL = 0.5 * 10 ** -DECIMALS + 1e-9


# ── EnergyPlus ───────────────────────────────────────────────────────────────────────────────
def simulate(name: str, idf_text: str) -> Path:
    """Run EnergyPlus once for *name* (skipped when its output exists); return the output dir."""
    d = WORK / name
    out = d / "out"
    if (out / "eplusout.csv").exists() and "Successfully" in (out / "eplusout.end").read_text():
        return out
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.idf").write_text(idf_text, encoding="latin-1")
    subprocess.run([EPLUS, "-w", str(EPW), "-d", str(out), "-r", str(d / "model.idf")],
                   check=True, capture_output=True)
    return out


def _idf(building: str) -> str:
    folder = BS_CORPUS / building
    name = "model_faulted.idf" if building.endswith("__faulted") else "model_with_outputs.idf"
    return (folder / name).read_text(encoding="latin-1")


def _with_damper(idf: str) -> str:
    return idf + f"\nOutput:Variable,*,{DAMPER_VAR},Hourly;\n"


def _compact(idf: str, name: str) -> str:
    m = re.search(r"Schedule:Compact,\s*\n\s*" + re.escape(name) + r"\s*,.*?;", idf, re.S | re.I)
    if m is None:
        raise KeyError(name)
    return m.group(0)


def _shifted_compact(src: str, old: str, new: str, cut: tuple[str, str], delta: float) -> str:
    """Copy of a one-period Schedule:Compact: unchanged through cut[0], shifted by *delta* after."""
    text = "\n".join(line.split("!")[0] for line in src.splitlines())   # IDF comments run to EOL
    fields = [f.strip() for f in text.strip().rstrip(";").split(",")]
    fields = [f for f in fields if f]
    assert fields[0].lower() == "schedule:compact" and fields[1] == old, fields[:2]
    body = fields[3:]
    assert sum(f.lower().startswith("through:") for f in body) == 1, f"{old} has several periods"
    after = [f if not re.fullmatch(r"-?\d+(\.\d+)?", f) else f"{float(f) + delta:.2f}" for f in body[1:]]
    out = [f"Through: {cut[0]}", *body[1:], "Through: 12/31", *after]
    return "Schedule:Compact,\n    " + ",\n    ".join([new, fields[2], *out]) + ";\n"


def idf_s1r(idf: str) -> str:
    """Core_bottom gets its own setpoint schedules, lowered by 1 C from 06/15 (a schedule change)."""
    clg = _shifted_compact(_compact(idf, "CLGSETP_SCH_YES_OPTIMUM"), "CLGSETP_SCH_YES_OPTIMUM",
                           "SUPP_S1R_CLG", S1R_ONSET, S1R_DELTA_C)
    htg = _shifted_compact(_compact(idf, "HTGSETP_SCH_YES_OPTIMUM"), "HTGSETP_SCH_YES_OPTIMUM",
                           "SUPP_S1R_HTG", S1R_ONSET, S1R_DELTA_C)
    dsp = re.search(r"ThermostatSetpoint:DualSetpoint,\s*\n\s*Core_bottom Dual SP Control\s*,.*?;", idf, re.S)
    new_dsp = ("ThermostatSetpoint:DualSetpoint,\n    Core_bottom Dual SP Control,\n    SUPP_S1R_HTG,\n"
               "    SUPP_S1R_CLG;")
    out = idf.replace(dsp.group(0), new_dsp)
    return out + "\n" + clg + htg + "Output:Variable,SUPP_S1R_CLG,Schedule Value,Hourly;\n"


def idf_s4(idf: str, watts: float = S4_WATTS) -> str:
    """A new always-on equipment load in Core_mid from 07/01 (a local load change)."""
    sch = (f"Schedule:Compact,\n    SUPP_S4_STEP,\n    Fraction,\n    Through: {S4_ONSET[0]},\n"
           "    For: AllDays,\n    Until: 24:00,\n    0,\n    Through: 12/31,\n    For: AllDays,\n"
           "    Until: 24:00,\n    1;\n")
    eq = ("ElectricEquipment,\n    SUPP_S4_Core_mid_Added_Load,\n    Core_mid,\n    SUPP_S4_STEP,\n"
          f"    EquipmentLevel,\n    {watts:.1f},\n    ,\n    ,\n    0,\n    0.5,\n    0,\n    MiscPlug;\n")
    return _with_damper(idf) + "\n" + sch + eq


# ── from EnergyPlus columns to BATS series ids ───────────────────────────────────────────────
def _columns(out: Path) -> tuple[list[str], dict[str, list[float]]]:
    cols: dict[str, list[float]] = {}
    stamps: list[str] = []
    for fname in ("eplusout.csv", "eplusmtr.csv"):
        if not (out / fname).exists():
            continue
        with (out / fname).open(newline="") as f:
            rows = list(csv.reader(f))
        head, body = rows[0], rows[1:]
        if fname == "eplusout.csv":
            stamps = [r[0] for r in body]
        for j, h in enumerate(head[1:], start=1):
            try:
                cols[h.strip()] = [float(r[j]) for r in body]
            except (ValueError, IndexError):
                pass
    return stamps, cols


def _store_series(store: Path) -> tuple[dict[str, dict], dict[str, list[tuple[str, float]]]]:
    pts = {r["timeseries_id"]: r for r in csv.DictReader((store / "points.csv").open(encoding="utf-8"))}
    ser: dict[str, list] = defaultdict(list)
    with (store / "timeseries.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ser[r["timeseries_id"]].append((r["timestamp"], float(r["value"])))
    return pts, ser


def _owner_labels(kg: Path) -> dict[str, set[str]]:
    """point uri -> upper-case labels of the entity it belongs to (EnergyPlus keys are upper case)."""
    g = Graph().parse(str(kg), format="turtle")
    out: dict[str, set[str]] = defaultdict(set)
    for p, e in list(g.subject_objects(BRICK.isPointOf)) + [(p, e) for e, p in g.subject_objects(BRICK.hasPoint)]:
        lab = g.value(e, RDFS.label)
        if lab is not None:
            out[str(p)].add(str(lab).upper())
    return out


def column_map(pub_store: Path, ref_out: Path, kg: Path) -> dict[str, str]:
    """BATS series id -> EnergyPlus column. A column must agree with the series on all 8,760
    values to the release's rounding (BuildStream's linking step rounds to 3 decimals, so within
    0.0005); where several do (zones on a shared schedule), the one whose key is the label of the
    point's owner is taken. Anything left ambiguous or unmatched raises."""
    _, cols = _columns(ref_out)
    pts, ser = _store_series(pub_store)
    owners = _owner_labels(kg)
    out = {}
    for tid, s in ser.items():
        vals = [v for _, v in s]
        hits = [c for c, cv in cols.items() if len(cv) == len(vals)
                and all(abs(a - b) <= ROUND_TOL for a, b in zip(cv, vals))]
        if len(hits) > 1:
            named = [c for c in hits if c.split(":")[0].strip().upper() in owners[pts[tid]["point_uri"]]]
            hits = named if len(named) == 1 else hits
        if len(hits) != 1:
            raise ValueError(f"{pts[tid]['point_uri']}: {len(hits)} matching columns {hits[:3]}")
        out[tid] = hits[0]
    return out


# ── stores and graph addenda ─────────────────────────────────────────────────────────────────
FAULTED = f"{B}__faulted"


def uri_columns() -> dict[str, str]:
    """point uri -> EnergyPlus column. Taken from the faulted building, which the local simulation
    reproduces exactly (93 of 93 series, to the release's rounding); the clean building publishes
    the same 93 point uris and ids."""
    pts = {r["timeseries_id"]: r["point_uri"] for r in
           csv.DictReader((BATS_DIR / "faulted" / FAULTED / "points.csv").open(encoding="utf-8"))}
    cmap = column_map(BATS_DIR / "faulted" / FAULTED, BS_CORPUS / FAULTED / "ep",
                      graphfix._OUT / FAULTED / "kg_linked.ttl")
    return {pts[t]: c for t, c in cmap.items()}


def _tsid(building: str, point: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bats-v1.0-l3-supplement:{building}:{point}"))


def _stamps(pub_store: Path) -> list[str]:
    first = None
    out = []
    with (pub_store / "timeseries.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            first = first or r["timeseries_id"]
            if r["timeseries_id"] == first:
                out.append(r["timestamp"])
    return out


def _zone_ids(kg: Path) -> dict[str, str]:
    """EnergyPlus zone name (upper case) -> graph HVAC_Zone uri."""
    g = Graph().parse(str(kg), format="turtle")
    return {str(g.value(z, RDFS.label)).upper(): str(z) for z in g.subjects(RDF.type, BRICK.HVAC_Zone)
            if g.value(z, RDFS.label) is not None}


def extra_points(kg: Path, cols: dict, *, spc: dict[str, str] | None = None, act: bool = False) -> list[dict]:
    """New points: SpC for the zones in *spc* (zone name -> schedule column) and, with *act*, the
    VAV damper position of every terminal the graph shows feeding a zone. The scheduled setpoint is
    typed Occupied_Air_Temperature_Cooling_Setpoint, which the census rules read as SpC. The damper
    position takes the class the BATS graph declares on the VAV, Damper_Position_Setpoint; the
    diagnosis stores count it as ActP, the actuation response (bara.stores.rung_store)."""
    g = Graph().parse(str(kg), format="turtle")
    zones = _zone_ids(kg)
    out = []
    for zname, col in (spc or {}).items():
        z = zones[zname.upper()]
        out.append({"point": z + ".Occupied_Air_Temperature_Cooling_Setpoint",
                     "class": "Occupied_Air_Temperature_Cooling_Setpoint", "owner": z,
                     "label": f"{zname} scheduled cooling setpoint", "unit": "C", "column": col})
    if act:
        for vav in g.subjects(RDF.type, BRICK.VAV):
            for z in g.objects(vav, BRICK.feeds):
                name = str(g.value(z, RDFS.label) or "").upper()
                col = f"{name} VAV BOX COMPONENT:{DAMPER_VAR} [](Hourly)"
                if col not in cols:
                    continue
                declared = [p for p in g.objects(vav, BRICK.hasPoint)
                            if (p, RDF.type, BRICK.Damper_Position_Setpoint) in g]
                point = str(declared[0]) if declared else str(vav) + ".Damper_Position_Setpoint"
                out.append({"point": point, "class": "Damper_Position_Setpoint", "owner": str(vav),
                            "label": f"{name.title()} VAV damper position", "unit": "", "column": col,
                            "declared": bool(declared)})
    return out


def write_series(dest: Path, building: str, stamps: list[str], cols: dict, series: list[dict]) -> None:
    """points.csv + timeseries.csv for *series* ({tsid, point, class, unit, column}), rounded like BATS."""
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "points.csv").open("w", newline="", encoding="utf-8") as fp, \
         (dest / "timeseries.csv").open("w", newline="", encoding="utf-8") as fv:
        wp, wv = csv.writer(fp), csv.writer(fv)
        wp.writerow(["timeseries_id", "point_uri", "point_class", "unit", "quantity_kind", "building_id"])
        wv.writerow(["timeseries_id", "timestamp", "value"])
        for s in series:
            wp.writerow([s["tsid"], s["point"], s["class"], s["unit"], "", building])
            for t, v in zip(stamps, cols[s["column"]]):
                wv.writerow([s["tsid"], t, round(v, DECIMALS)])


def write_addendum(dest: Path, extras: list[dict]) -> None:
    """Graph addendum: the new points and their series references (the published graph is kept)."""
    g = Graph()
    g.bind("brick", BRICK), g.bind("ref", REF)
    for e in extras:
        p = URIRef(e["point"])
        if not e.get("declared"):
            g.add((p, RDF.type, BRICK[e["class"]]))
            g.add((p, BRICK.isPointOf, URIRef(e["owner"])))
            g.add((URIRef(e["owner"]), BRICK.hasPoint, p))
            g.add((p, RDFS.label, Literal(e["label"])))
        ref = URIRef(f"urn:bats-supplement:tsref:{e['tsid']}")
        g.add((p, REF.hasExternalReference, ref))
        g.add((ref, REF.hasTimeseriesId, Literal(e["tsid"])))
    g.serialize(str(dest / "addendum.ttl"), format="turtle")


def _fault_label(dest: Path, **row) -> None:
    keys = ["timeseries_id", "fault_type", "onset", "end", "magnitude", "unit", "params", "source"]
    with (dest / "faults.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerow({k: row.get(k, "") for k in keys})


# ── the four scenario buildings ──────────────────────────────────────────────────────────────
S1_ZONE, S3_ZONE = "Core_bottom", "Core_mid"
MANIFEST = ROOT / "scenarios_supplement.json"     # same content as results/faults/scenarios_supplement.json


def _full(dest: Path, building: str, out: Path, uri_col: dict, extras: list[dict]) -> None:
    """A complete store from one simulation: the 93 BATS points (their ids) plus *extras*."""
    stamps, cols = _columns(out)
    pub = BATS_DIR / "buildings" / B
    pts = list(csv.DictReader((pub / "points.csv").open(encoding="utf-8")))
    series = [{"tsid": p["timeseries_id"], "point": p["point_uri"], "class": p["point_class"],
               "unit": p["unit"], "column": uri_col[p["point_uri"]]} for p in pts]
    write_series(dest, building, _stamps(pub), cols, series + extras)


def _merge(dest: Path, base_store: Path, base_kg: Path, supp: Path) -> None:
    """Merged store = a BATS store + supplement series; merged graph = linked graph + addendum."""
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("points.csv", "timeseries.csv"):
        with (dest / fname).open("w", encoding="utf-8", newline="") as w:
            for i, src in enumerate((base_store / fname, supp / fname)):
                lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
                w.writelines(lines if i == 0 else lines[1:])
    g = Graph().parse(str(base_kg), format="turtle")
    g.parse(str(supp / "addendum.ttl"), format="turtle")
    g.serialize(str(dest / "kg.ttl"), format="turtle")


def build(s4_watts: float = S4_WATTS) -> dict:
    """Simulate (cached), write the Zenodo package and the merged stores, write the manifest."""
    faulted_out = BS_CORPUS / FAULTED / "ep"
    act_out = simulate("clean_act", _with_damper(_idf(B)))
    s1r_out = simulate("s1r", idf_s1r(_with_damper(_idf(B))))
    s4_out = simulate(f"s4_{int(s4_watts / 1000)}kW", idf_s4(_idf(B), s4_watts))
    uri_col = uri_columns()
    kg_clean, kg_faulted = graphfix._OUT / B / "kg_linked.ttl", graphfix._OUT / FAULTED / "kg_linked.ttl"
    PACKAGE.mkdir(parents=True, exist_ok=True)
    made = {}

    # s1: the published faulted building + its scheduled cooling setpoint (already simulated)
    _, fcols = _columns(faulted_out)
    ex = extra_points(kg_faulted, fcols, spc={S1_ZONE: "CLGSETP_SCH_YES_OPTIMUM:Schedule Value [](Hourly)"})
    for e in ex:
        e["tsid"] = _tsid(FAULTED, e["point"])
    d = PACKAGE / FAULTED
    write_series(d, FAULTED, _stamps(BATS_DIR / "faulted" / FAULTED), fcols, ex)
    write_addendum(d, ex)
    _merge(MERGED / FAULTED, BATS_DIR / "faulted" / FAULTED, kg_faulted, d)
    shutil.copyfile(BATS_DIR / "faulted" / FAULTED / "faults.csv", MERGED / FAULTED / "faults.csv")
    made["s1"] = FAULTED

    # clean building with the damper positions (the base of s3m)
    _, acols = _columns(act_out)
    ex = extra_points(kg_clean, acols, act=True)
    for e in ex:
        e["tsid"] = _tsid(B, e["point"])
    d = PACKAGE / f"{B}__act"
    _full(d, f"{B}__act", act_out, uri_col, ex)
    write_addendum(d, ex)
    made["act"] = f"{B}__act"

    # s1r: schedule change on Core_bottom (full store; SpC = Core_bottom's own cooling schedule)
    _, rcols = _columns(s1r_out)
    ex = extra_points(kg_clean, rcols, spc={S1_ZONE: "SUPP_S1R_CLG:Schedule Value [](Hourly)"})
    for e in ex:
        e["tsid"] = _tsid(f"{B}__s1r", e["point"])
    d = PACKAGE / f"{B}__s1r"
    _full(d, f"{B}__s1r", s1r_out, uri_col, ex)
    write_addendum(d, ex)
    _fault_label(d, timeseries_id=f"{S1_ZONE} Thermostat", fault_type="schedule_change",
                 onset="2018-06-15", end="2019-01-01T00:00:00", magnitude=S1R_DELTA_C, unit="C",
                 params=json.dumps({"zone": S1_ZONE, "schedules": ["SUPP_S1R_CLG", "SUPP_S1R_HTG"],
                                    "from": ["CLGSETP_SCH_YES_OPTIMUM", "HTGSETP_SCH_YES_OPTIMUM"]}),
                 source="zone-specific copy of the setpoint schedules, lowered by 1 C (EnergyPlus 22.1)")
    made["s1r"] = f"{B}__s1r"

    # s4: internal-load step in Core_mid (full store + damper positions)
    _, qcols = _columns(s4_out)
    ex = extra_points(kg_clean, qcols, act=True)
    for e in ex:
        e["tsid"] = _tsid(f"{B}__s4", e["point"])
    d = PACKAGE / f"{B}__s4"
    _full(d, f"{B}__s4", s4_out, uri_col, ex)
    write_addendum(d, ex)
    _fault_label(d, timeseries_id=f"{S3_ZONE}", fault_type="internal_load_step", onset="2018-07-01",
                 end="2019-01-01T00:00:00", magnitude=s4_watts, unit="W",
                 params=json.dumps({"zone": S3_ZONE, "object": "SUPP_S4_Core_mid_Added_Load",
                                    "schedule": "always on from 07/01"}),
                 source="added ElectricEquipment in the zone (EnergyPlus 22.1)")
    made["s4"] = f"{B}__s4"

    for key in ("act", "s1r", "s4"):          # merged = the package store + its graph
        name = made[key]
        src = PACKAGE / name
        m = MERGED / name
        m.mkdir(parents=True, exist_ok=True)
        for fname in ("points.csv", "timeseries.csv", "faults.csv"):
            if (src / fname).exists():
                shutil.copyfile(src / fname, m / fname)
        g = Graph().parse(str(kg_clean), format="turtle")
        g.parse(str(src / "addendum.ttl"), format="turtle")
        g.serialize(str(m / "kg.ttl"), format="turtle")
    made["s3m"] = derive_s3m(MERGED / made["act"])
    return made


def derive_s3m(act_store: Path, onset: str = "2018-07-01") -> str:
    """s3m = the clean building with dampers, Core_mid's reading drifted linearly to +1.0 C by year
    end (post hoc: the control loop never saw it, so the damper does not respond). The deposited
    series was written by BuildStream v1.0's labelled telemetry injector; bara.drift re-implements it
    and agrees on all 8,760 hours. The drifted series and the label go to the package; the store to
    merged/."""
    name = f"{B}__s3m"
    zid = _zone_ids(act_store / "kg.ttl")[S3_ZONE.upper()]
    point = zid + ".Zone_Air_Temperature_Sensor"
    rows = list(csv.DictReader((act_store / "points.csv").open(encoding="utf-8")))
    tsid = next(r["timeseries_id"] for r in rows if r["point_uri"] == point)
    with (act_store / "timeseries.csv").open(encoding="utf-8") as f:
        series = [(r["timestamp"], float(r["value"])) for r in csv.DictReader(f) if r["timeseries_id"] == tsid]
    drifted = dict(drift(series, onset, None, 1.0))
    dst = MERGED / name
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(act_store / "points.csv", dst / "points.csv")
    shutil.copyfile(act_store / "kg.ttl", dst / "kg.ttl")
    with (act_store / "timeseries.csv").open(encoding="utf-8", newline="") as fi, \
         (dst / "timeseries.csv").open("w", encoding="utf-8", newline="") as fo:
        rd = csv.DictReader(fi)
        wr = csv.DictWriter(fo, fieldnames=rd.fieldnames)
        wr.writeheader()
        for r in rd:
            if r["timeseries_id"] == tsid and r["timestamp"] in drifted:
                r["value"] = repr(round(drifted[r["timestamp"]], DECIMALS))
            wr.writerow(r)
    lab = label(tsid, onset, series[-1][0])
    for d in (dst, PACKAGE / name):
        d.mkdir(parents=True, exist_ok=True)
        _fault_label(d, **{**lab, "params": json.dumps(lab.get("params") or {})})
    write_series(PACKAGE / name, name, _stamps(act_store), {"drift": [drifted[t] for t in _stamps(act_store)]},
                 [{"tsid": tsid, "point": point, "class": "Zone_Air_Temperature_Sensor", "unit": "C",
                   "column": "drift"}])
    return name


# ── manifest and checks (the rung stores: bara.stores.rung_store) ────────────────────────────
_OBS = {
    "s1": "From mid-June 2018 the Core_bottom zone ({z}) has run about 1 C cooler during occupied hours "
          "than before, while the other core zones have not changed.",
    "s3m": "Since July 2018 the reported temperature of the Core_mid zone ({z}) has risen relative to "
           "the other zones.",
}


# The stream that separates the two causes of each pair: the scheduled setpoint for pair A (s1, s1r),
# the damper position (the actuation response) for pair B (s3m, s4).
SEPARATING = {"s1": ["SpC"], "s3m": ["ActP"]}


def write_manifest(made: dict) -> dict:
    """Four scenarios in two pairs; each pair shares one observation text, so wording names no cause.
    Written to MANIFEST (under ROOT)."""
    zones = _zone_ids(MERGED / made["s1r"] / "kg.ttl")
    z1, z3 = zones[S1_ZONE.upper()].split("#")[-1], zones[S3_ZONE.upper()].split("#")[-1]
    offset, sched = "local override or controller offset", "schedule change"
    sensor, load = "zone sensor fault", "local load change"
    sc = [
        ("s1", made["s1"], z1, "2018-06-15", "FaultModel:ThermostatOffset 1.0 C (published BATS fault)", offset, [sched], "s1"),
        ("s1r", made["s1r"], z1, "2018-06-15", "zone setpoint schedules lowered by 1.0 C", sched, [offset], "s1"),
        ("s3m", made["s3m"], z3, "2018-07-01", "post-hoc reading drift to +1.0 C (BuildStream v1.0 injector)", sensor, [load], "s3m"),
        ("s4", made["s4"], z3, "2018-07-01", f"added always-on equipment load, {S4_WATTS / 1000:.0f} kW", load, [sensor], "s3m"),
    ]
    zname = {z1: S1_ZONE, z3: S3_ZONE}
    m = {"source": "BATS v1.0 (Zenodo 10.5281/zenodo.20777376) and its L3 supplement (bara.supplement)",
         "scenarios": [{"id": i, "building": b, "domain": "thermal", "zone": f"{zname[z]} ({z})",
                        "onset": on, "magnitude": mag, "observation": _OBS[o].format(z=z),
                        "true_cause": t, "rival_causes": r, "base_streams": ["T", "Sp"],
                        "separating_stream_in_store": True, "separating_streams": SEPARATING[o]}
                       for i, b, z, on, mag, t, r, o in sc]}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return m


def _series(store: Path, point_suffix: str) -> dict[str, float]:
    tid = next(r["timeseries_id"] for r in csv.DictReader((store / "points.csv").open(encoding="utf-8"))
               if r["point_uri"].endswith(point_suffix))
    out = {}
    with (store / "timeseries.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["timeseries_id"] == tid:
                out[r["timestamp"]] = float(r["value"])
    return out


def _occ_mean(s: dict[str, float], a: str, b: str) -> float:
    v = [x for t, x in s.items() if a <= t[:10] <= b and 9 <= int(t[11:13]) <= 17 and
         datetime.date.fromisoformat(t[:10]).weekday() < 5]
    return sum(v) / len(v)


def checks(made: dict) -> list[str]:
    """Look-alike (base streams move alike) and separation (the separating stream differs) per pair.
    Each change is scenario minus the clean building (with dampers), occupied weekday hours."""
    base = MERGED / made["act"]
    zones = _zone_ids(base / "kg.ttl")
    z1 = zones[S1_ZONE.upper()].split("#")[-1]
    z3 = zones[S3_ZONE.upper()].split("#")[-1]
    peer = zones["CORE_TOP"].split("#")[-1]
    w1, w3 = ("2018-06-16", "2018-06-29"), ("2018-10-01", "2018-12-31")
    d = lambda st, pt, w: _occ_mean(_series(MERGED / st, pt), *w) - _occ_mean(_series(base, pt), *w)
    L = []
    for sc in ("s1", "s1r"):
        st = made[sc]
        L.append(f"{sc}: T {d(st, z1 + '.Zone_Air_Temperature_Sensor', w1):+.2f} C, setpoint in effect "
                 f"{d(st, z1 + '.Zone_Air_Cooling_Temperature_Setpoint', w1):+.2f} C, peer Core_top T "
                 f"{d(st, peer + '.Zone_Air_Temperature_Sensor', w1):+.2f} C; scheduled setpoint (SpC) "
                 f"{_spc_change(made, sc, w1):+.2f} C")
    vav3 = [r["point_uri"] for r in csv.DictReader((MERGED / made["s4"] / "points.csv").open(encoding="utf-8"))
            if r["point_class"] == "Damper_Position_Setpoint" and "VAV_F3_Z01" in r["point_uri"]][0].split("#")[-1]
    for sc in ("s3m", "s4"):
        st = made[sc]
        L.append(f"{sc}: reported T {d(st, z3 + '.Zone_Air_Temperature_Sensor', w3):+.2f} C, setpoint in effect "
                 f"{d(st, z3 + '.Zone_Air_Cooling_Temperature_Setpoint', w3):+.2f} C, peer Core_top T "
                 f"{d(st, peer + '.Zone_Air_Temperature_Sensor', w3):+.2f} C; damper position (ActP) "
                 f"{d(st, vav3, w3):+.3f}")
    return L


def _spc_change(made: dict, sc: str, w) -> float:
    """The scenario's scheduled cooling setpoint against the clean building's (the shared schedule)."""
    s = _series(MERGED / made[sc], "Occupied_Air_Temperature_Cooling_Setpoint")
    _, cols = _columns(WORK / "clean_act" / "out")
    clean = dict(zip(_stamps(BATS_DIR / "buildings" / B), cols["CLGSETP_SCH_YES_OPTIMUM:Schedule Value [](Hourly)"]))
    return _occ_mean(s, *w) - _occ_mean(clean, *w)


if __name__ == "__main__":
    import sys
    made = build()
    write_manifest(made)
    print(json.dumps(made, indent=1))
    if "checks" in sys.argv:
        print("\n".join(checks(made)))
