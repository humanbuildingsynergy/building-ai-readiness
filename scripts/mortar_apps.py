"""Criterion validity: can the Mortar analytics applications run on each graph?

    python scripts/mortar_apps.py          # -> results/census/mortar_apps.{md,json}

Another revision of the graphs, e.g. the June 2026 one (scripts/fetch_data.py --mortar-june),
written under the derived folder: its census first, then the applications.

    python -m bara.census --graphs $MORTAR_DIR/graphs_june2026 --out $DERIVED_DIR/census_june2026
    python scripts/mortar_apps.py --graphs $MORTAR_DIR/graphs_june2026 \\
        --census $DERIVED_DIR/census_june2026/census_v2.json \\
        --out $DERIVED_DIR/census_june2026/mortar_apps_june2026.md --revision "87c3d309, June 2026"

For every application of SoftwareDefinedBuildings/mortar-analytics (commit df48efc) that computes
something, its own qualify-stage Brick queries are run against each census graph with linked series
(Mortar and BTS Site B). A site qualifies when every query of the application returns a row, and an
application that joins a sensor to its setpoint on the same equipment (compare_sensors_against_setpoints,
rogue_zone_airflow) also needs one joined pair. Only linked points count: every point a row binds
must carry a time-series reference. available_brick_points (it lists points, computes nothing) is left out.

The queries are written in Brick 1.0. They run here unchanged except for the vocabulary:
- `brick:` and `bf:` resolve to the current Brick namespace, and a class matches with its
  subclasses (the queries' own rdf:type/rdfs:subClassOf* path over the Brick 1.4.4 hierarchy, with
  the supertypes materialized once per graph);
- a deprecated class also matches its Brick replacement (bara/brick/replacements.json), as in the
  census;
- classes Brick later removed, which the August 2026 graphs no longer use, take their current names:
  Building_Electric_Meter and Green_Button_Meter -> Building_Electrical_Meter,
  Weather_Temperature_Sensor -> Outside_Air_Temperature_Sensor; Cooling_Valve_Command and
  Heating_Valve_Command -> a Valve_Command on a cooling (chilled-water) or heating (hot-water) valve
  that the air handler has as a part, or the old class itself;
- the inverse of hasPoint/isPointOf, hasPart/isPartOf, hasLocation/isLocationOf is added (the
  reasoning step the Mortar server applied).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdflib import RDF, Graph, Namespace, RDFS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import BRICK_TTL, RESULTS_DIR, census  # noqa: E402

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
SENAPS = Namespace("http://senaps.io/schema/1.0/senaps#")
REPL = json.loads((Path(census.__file__).parent / "brick" / "replacements.json").read_text(encoding="utf-8"))
RENAMED = {"Building_Electric_Meter": ["Building_Electrical_Meter"], "Green_Button_Meter": ["Building_Electrical_Meter"],
           "Weather_Temperature_Sensor": ["Outside_Air_Temperature_Sensor"]}
PREFIX = ("PREFIX brick: <https://brickschema.org/schema/Brick#>\nPREFIX bf: <https://brickschema.org/schema/Brick#>\n"
          "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
          "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n")


def cls(name: str) -> str:
    """VALUES list: the class, its current name and its Brick replacements (the queries add subclasses)."""
    names, stack = set(), [name] + RENAMED.get(name, [])
    while stack:
        n = stack.pop()
        if n not in names:
            names.add(n)
            stack.extend(REPL.get(n, ()))
    return " ".join(f"<{BRICK}{n}>" for n in sorted(names))      # full IRIs: rdflib cannot resolve
                                                                   # prefixed names inside VALUES


def typed(var: str, name: str) -> str:
    return f"VALUES ?_{var} {{ {cls(name)} }} ?{var} rdf:type ?_{var} ."   # VALUES first: rdflib joins in order


def valve(var: str, cmd: str, valves: tuple[str, ...]) -> str:
    """The Brick 1.0 valve command, or its Brick 1.4 form: a valve command on such a valve."""
    vs = " ".join(f"<{BRICK}{v}>" for v in valves)
    return (f"{{ {typed(var, cmd)} ?ahu bf:hasPoint ?{var} . }} UNION "
            f"{{ ?{var} rdf:type <{BRICK}Valve_Command> . ?{var} bf:isPointOf ?v_{var} . "
            f"VALUES ?vc_{var} {{ {vs} }} ?v_{var} rdf:type ?vc_{var} . ?ahu bf:hasPart ?v_{var} . }}")


# application -> list of (query body, point variables); every query must return a linked row
APPS = {
    "zone_comfort_evaluation": [(typed("sensor", "Zone_Air_Temperature_Sensor"), ["sensor"])],
    "compare_sensors_against_setpoints": [(
        typed("sensor", "Zone_Air_Temperature_Sensor") + " ?sensor bf:isPointOf ?equip . "
        + typed("sp", "Zone_Air_Temperature_Setpoint") + " ?sp bf:isPointOf ?equip .", ["sensor", "sp"])],
    "rogue_zone_airflow": [(
        typed("sensor", "Air_Flow_Sensor") + " ?sensor bf:isPointOf ?equip . "
        + typed("sp", "Air_Flow_Setpoint") + " ?sp bf:isPointOf ?equip .", ["sensor", "sp"])],
    "simultaneous_heating_cooling_ahus": [(
        valve("cooling_point", "Cooling_Valve_Command", ("Chilled_Water_Valve", "Cooling_Valve")) + " "
        + valve("heating_point", "Heating_Valve_Command", ("Hot_Water_Valve", "Heating_Valve")),
        ["cooling_point", "heating_point"])],
    "possibly_inefficient_zones": [(
        typed("tstat", "Thermostat")                     # the same pattern, most selective part first
        + " ?tstat bf:hasLocation ?room . ?zone bf:hasPart ?room . ?tstat bf:hasPoint ?state . "
        "?tstat bf:hasPoint ?temp . ?tstat bf:hasPoint ?hsp . ?tstat bf:hasPoint ?csp . "
        + typed("zone", "Zone") + typed("state", "Thermostat_Status")
        + typed("temp", "Temperature_Sensor") + typed("hsp", "Supply_Air_Temperature_Heating_Setpoint")
        + typed("csp", "Supply_Air_Temperature_Cooling_Setpoint"), ["state", "temp", "hsp", "csp"])],
    "energy_consumption_baseline": [(typed("meter", "Green_Button_Meter"), ["meter"]),
                                    (typed("t", "Weather_Temperature_Sensor"), ["t"])],
    "dr_evaluation": [(typed("t", "Weather_Temperature_Sensor"), ["t"]),
                      (typed("meter", "Green_Button_Meter"), ["meter"])],
    "weekday_mean_energy": [(typed("meter", "Building_Electric_Meter"), ["meter"])],
    "meter_data_example": [(typed("meter", "Building_Electric_Meter"), ["meter"])],
    "occupancy_energy_correlation": [(typed("meter", "Green_Button_Meter"), ["meter"]),
                                     (typed("point", "Occupancy_Sensor"), ["point"])],
}
INVERSES = [(BRICK.hasPoint, BRICK.isPointOf), (BRICK.hasPart, BRICK.isPartOf),
            (BRICK.hasLocation, BRICK.isLocationOf)]


def load(path: Path, parents: dict) -> tuple[Graph, set]:
    """The graph with inverse relations and every Brick supertype of each type materialized: the same
    inference as the queries' subclass path, computed once instead of per query."""
    g = Graph().parse(str(path), format="turtle")
    for x, t in list(g.subject_objects(RDF.type)):
        stack, seen = [t], set()
        while stack:
            c = stack.pop()
            for sup in parents.get(c, ()):
                if sup not in seen:
                    seen.add(sup)
                    stack.append(sup)
                    g.add((x, RDF.type, sup))
    for a, b in INVERSES:
        for s, o in list(g.subject_objects(a)):
            g.add((o, b, s))
        for s, o in list(g.subject_objects(b)):
            g.add((o, a, s))
    linked = {s for s in g.subjects(SENAPS.stream_id, None)}
    for s, ext in g.subject_objects(REF.hasExternalReference):
        if (ext, REF.hasTimeseriesId, None) in g:
            linked.add(s)
    return g, linked


def runs(g: Graph, linked: set, app: str) -> bool:
    for body, points in APPS[app]:
        rows = g.query(PREFIX + "SELECT " + " ".join(f"?{v}" for v in points) + " WHERE { " + body + " }")
        if not any(all(r[i] in linked for i in range(len(points))) for r in rows):
            return False
    return True


def main(graphs: Path | None, out: Path, census_json: Path | None = None, revision: str = "") -> dict:
    parents: dict = {}
    for s, o in Graph().parse(str(BRICK_TTL), format="turtle").subject_objects(RDFS.subClassOf):
        parents.setdefault(s, set()).add(o)
    if graphs is not None:
        census.MORTAR_GRAPHS_DIR = graphs
    rep = json.loads((census_json or RESULTS_DIR / "census" / "census_v2.json").read_text(encoding="utf-8"))
    c_ans = {r["building"]: r["c_ans"] for r in rep["rows"] if r["linked_points"]}
    res = {}
    for source, name, path in census.sources():
        if name not in c_ans:
            continue
        g, linked = load(path, parents)
        res[name] = {a: runs(g, linked, a) for a in APPS}
        print(name, sum(res[name].values()), flush=True)
    ks = sorted(res)
    n = [sum(res[k].values()) for k in ks]
    c = [c_ans[k] for k in ks]
    rho = census._spearman(c, n)
    rc, rn = census._ranks(c), census._ranks(n)
    gap = sorted(((rc[i] - rn[i]) / len(ks), ks[i]) for i in range(len(ks)))
    per_app = {a: sum(res[k][a] for k in ks) for a in APPS}
    L = ["# Mortar applications on the census graphs" + (f" (gtfierro/mortargraphs @ {revision})" if revision else ""), "",
         f"{len(ks)} graphs with linked series; {len(APPS)} applications of mortar-analytics (df48efc) that "
         "compute something, each by its own qualify queries (vocabulary translated as in "
         "scripts/mortar_apps.py), linked points only.", "",
         f"- Spearman correlation of the number of applications that can run with the linked C_ans: "
         f"**{rho:.2f}** ({len(ks)} graphs).",
         "- Graphs that can run each application: "
         + ", ".join(f"{a} {v}" for a, v in sorted(per_app.items(), key=lambda x: -x[1])) + ".",
         "- Largest disagreements (rank of C_ans minus rank of the application count, as a share of "
         f"{len(ks)}): ceiling ranks higher: "
         + ", ".join(f"{k} ({d:+.2f})" for d, k in gap[::-1][:4])
         + "; applications rank higher: " + ", ".join(f"{k} ({d:+.2f})" for d, k in gap[:4]) + ".", "",
         "| graph | C_ans linked | applications | which |", "|---|---:|---:|---|"]
    for k in sorted(ks, key=lambda k: (-c_ans[k], k)):
        L.append(f"| {k} | {c_ans[k]:.3f} | {sum(res[k].values())} | "
                 f"{', '.join(a for a, v in res[k].items() if v) or '-'} |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".json").write_text(json.dumps({"rho": rho, "per_graph": res, "per_app": per_app},
                                                   indent=1) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L[:8]))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--graphs", type=Path, default=None, help="Mortar graphs folder (default: the census's)")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "census" / "mortar_apps.md",
                    help="Markdown output; a JSON file with the same name is written next to it")
    ap.add_argument("--census", type=Path, default=None, help="census JSON of those graphs (default: the deposit)")
    ap.add_argument("--revision", default="", help="graph revision, named in the title")
    a = ap.parse_args()
    main(a.graphs, a.out, a.census, a.revision)
