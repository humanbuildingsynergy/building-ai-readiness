"""Real buildings into the bank's store format: Mortar graphs plus their Hugging Face series.

For one Mortar building: read the series ids of the points the question bank can use from the
published Brick graph, load those series from the ``gtfierro/mortar`` parquet files
(``collection=<building>/uuid=<id>/``), resample them to hourly means, and write a store the bank
reads (``points.csv`` and ``timeseries.csv``, same columns as BATS). The published graph is used
as it is; nothing is added to it.

A declared stream is not always a usable one. Each series is classed against the chosen year:

  absent      the graph links a series id the release does not hold
  unusable    held, but under COVERAGE of the year's hours, or constant (a stuck or dead point)
  usable      written to the store

So the data-limitation share of a real building splits into absent and present-but-unusable. The
year is the calendar year in which the most series reach the coverage bar.

Needs pandas and pyarrow, and the Mortar series (scripts/fetch_data.py --mortar-series).
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Namespace, RDF

from bara.bank import CLASSES, with_replacements

BRICK = Namespace("https://brickschema.org/schema/Brick#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
COVERAGE = 0.90          # share of the year's hours that must hold a value
MIN_DISTINCT = 3         # fewer distinct hourly values than this is a stuck or dead point
F_MEDIAN = 35.0          # a temperature series with a higher median is in degF (no graph unit)
_WANTED = set().union(*CLASSES.values()) | with_replacements({"Building_Electric_Meter",
                                                                  "Zone_Air_Temperature_Setpoint"})


def wanted_points(kg_ttl: Path) -> dict[str, tuple[str, str]]:
    """series id -> (point uri, Brick class) for every linked point of a class the bank uses."""
    g = Graph().parse(str(kg_ttl), format="turtle")
    out = {}
    for p, ext in g.subject_objects(REF.hasExternalReference):
        tsid = g.value(ext, REF.hasTimeseriesId)
        classes = {str(t).split("#")[-1] for t in g.objects(p, RDF.type)} & _WANTED
        if tsid is not None and classes:
            out[str(tsid)] = (str(p), sorted(classes)[0])
    return out


def hourly(frame):
    """Hourly mean of one raw series, as a Series indexed by naive UTC hours."""
    import pandas as pd
    if "time" in frame.columns:
        frame = frame.set_index("time")
    idx = pd.to_datetime(frame.index, utc=True).tz_convert(None)
    s = pd.Series(frame["value"].to_numpy(), index=idx).dropna()
    return s.resample("1h").mean().dropna()


def to_celsius(series, cls: str):
    """(series in degC, unit note) for a temperature class; other classes pass through.

    The Mortar graphs declare no unit on temperature points, so the unit is inferred: a median
    above F_MEDIAN is degF (indoor ~70 degF against ~22 degC; a degC median above 35 is implausible
    even outdoors) and is converted. The note goes into points.csv and usability.json."""
    if "Temperature" not in cls:
        return series, ""
    if series.median() > F_MEDIAN:
        return (series - 32.0) * 5.0 / 9.0, "degC (converted from degF, inferred)"
    return series, "degC (inferred)"


def classify(series, year: int) -> str:
    in_year = series[series.index.year == year]
    hours_in_year = 8784 if year % 4 == 0 else 8760
    if len(in_year) < COVERAGE * hours_in_year or in_year.round(6).nunique() < MIN_DISTINCT:
        return "unusable"
    return "usable"


def convert(building: str, kg_ttl: Path, parquet_root: Path, out_dir: Path) -> dict:
    import pandas as pd
    points = wanted_points(kg_ttl)
    series, absent, units = {}, [], {}
    for tsid in points:
        files = sorted((Path(parquet_root) / f"collection={building}" / f"uuid={tsid}").glob("*.parquet"))
        if not files:
            absent.append(tsid)
            continue
        series[tsid], units[tsid] = to_celsius(hourly(pd.concat(pd.read_parquet(f) for f in files)),
                                               points[tsid][1])
    years = Counter(y for s in series.values() for y in set(s.index.year)
                    if classify(s, y) == "usable")
    report = {"building": building, "linked_wanted": len(points), "absent": len(absent),
              "year": None, "usable": 0, "unusable": 0, "by_class": {}}
    if not years:
        report["unusable"] = len(series)
        return report
    year = years.most_common(1)[0][0]
    by_class: dict = defaultdict(Counter)
    for tsid in absent:
        by_class[points[tsid][1]]["absent"] += 1
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "points.csv").open("w", newline="", encoding="utf-8") as fp, \
         (out_dir / "timeseries.csv").open("w", newline="", encoding="utf-8") as fv:
        wp, wv = csv.writer(fp), csv.writer(fv)
        wp.writerow(["timeseries_id", "point_uri", "point_class", "unit", "quantity_kind", "building_id"])
        wv.writerow(["timeseries_id", "timestamp", "value"])
        for tsid, s in series.items():
            uri, cls = points[tsid]
            state = classify(s, year)
            by_class[cls][state] += 1
            if state != "usable":
                continue
            wp.writerow([tsid, uri, cls, units[tsid], "", building])
            for t, v in s[s.index.year == year].items():
                wv.writerow([tsid, t.strftime("%Y-%m-%dT%H:00:00"), round(float(v), 4)])
    report.update(year=int(year), usable=sum(c["usable"] for c in by_class.values()),
                  unusable=sum(c["unusable"] for c in by_class.values()),
                  converted_from_degF=sum("converted" in u for u in units.values()),
                  by_class={k: dict(v) for k, v in sorted(by_class.items())})
    (out_dir / "usability.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Convert Mortar buildings into bank-readable stores.")
    ap.add_argument("--graphs", required=True, help="folder of the mortargraphs .ttl files")
    ap.add_argument("--parquet", required=True, help="root of the gtfierro/mortar download")
    ap.add_argument("--out", required=True)
    ap.add_argument("buildings", nargs="+")
    a = ap.parse_args()
    for b in a.buildings:
        r = convert(b, Path(a.graphs) / f"{b}.ttl", Path(a.parquet), Path(a.out) / b)
        print(f"{b}: year {r['year']}, usable {r['usable']}, unusable {r['unusable']}, absent {r['absent']}")
