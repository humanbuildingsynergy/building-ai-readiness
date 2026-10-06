"""Sensitivity of the Mortar usability rule. No agent runs.

    python scripts/usability_sensitivity.py [--root $MORTAR_DIR]   (needs fetch_data.py --mortar-series)

The rule of bara.mortar: hourly means; a series is usable in the chosen year with at least COVERAGE
of the year's hours and at least MIN_DISTINCT distinct hourly values; the year is the one in which
the most series pass. Here the rule is re-applied on the same linked series (bank classes, the
eight Mortar buildings of the agent runs) under variants:

  fill      none = hourly means (the rule as used); ffill = change-of-value logging held: an hour
            with no sample takes the last value seen before it (only between a series' first and
            last sample);
            ffill24 = the same, but a value is held for at most 24 h (a longer gap stays a gap)
  coverage  0.80, 0.90, 0.95
  distinct  2, 3

For each variant the year is chosen again by the same rule. Also records why each series fails the
current rule (coverage or distinct values) and its median sampling interval, by class.
Writes results/mortar/usability_sensitivity.md (counts only, no data).
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import MORTAR_DIR, mortar  # noqa: E402

B = ["bldg40", "bldg15", "bldg11", "bldg13", "bldg34", "bldg32", "bldg4", "bldg5"]
OUT = Path(__file__).resolve().parent.parent / "results" / "mortar" / "usability_sensitivity.md"
FOCUS = ["Heating_Command", "Occupancy_Sensor", "Zone_Air_Temperature_Sensor",
         "Target_Zone_Air_Temperature_Setpoint", "Damper_Position_Setpoint", "Supply_Air_Flow_Sensor",
         "Cooling_Command", "Outside_Air_Temperature_Sensor"]


def load(root: Path, b: str):
    """tsid -> (class, raw series indexed by naive UTC time)."""
    out = {}
    for tsid, (_, cls) in mortar.wanted_points(root / "graphs" / f"{b}.ttl").items():
        files = sorted((root / "series" / f"collection={b}" / f"uuid={tsid}").glob("*.parquet"))
        if not files:
            continue
        f = pd.concat(pd.read_parquet(x) for x in files)
        if "time" in f.columns:
            f = f.set_index("time")
        idx = pd.to_datetime(f.index, utc=True).tz_convert(None)
        raw = pd.Series(f["value"].to_numpy(), index=idx).dropna().sort_index()
        raw = raw[~raw.index.duplicated(keep="last")]
        out[tsid] = (cls, raw)
    return out


def hourly(raw: pd.Series, cls: str, fill: str) -> pd.Series:
    h = raw.resample("1h").mean()
    if fill in ("ffill", "ffill24"):
        last = raw.resample("1h").last().ffill(limit=24 if fill == "ffill24" else None)
        h = h.fillna(last.shift(1))                      # an empty hour holds the previous value
    h = h.dropna()
    return mortar.to_celsius(h, cls)[0]


def classify(s: pd.Series, year: int, cov: float, distinct: int) -> str:
    y = s[s.index.year == year]
    hours = 8784 if year % 4 == 0 else 8760
    if len(y) < cov * hours:
        return "coverage"
    if y.round(6).nunique() < distinct:
        return "distinct"
    return "usable"


def apply(series: dict, cov: float, distinct: int):
    years = Counter(yr for cls, s in series.values() for yr in set(s.index.year)
                    if classify(s, yr, cov, distinct) == "usable")
    if not years:
        return None, {t: "coverage" for t in series}
    year = years.most_common(1)[0][0]
    return year, {t: classify(s, year, cov, distinct) for t, (cls, s) in series.items()}


def main(root: Path) -> None:
    grid = list(itertools.product(("none", "ffill", "ffill24"), (0.80, 0.90, 0.95), (2, 3)))
    tot = {g: Counter() for g in grid}
    by_cls = {g: defaultdict(Counter) for g in grid}
    years = {g: {} for g in grid}
    why = defaultdict(Counter)                 # class -> failure reason under the current rule
    gap = defaultdict(list)                    # class -> median sampling interval (minutes)
    for b in B:
        raw = load(root, b)
        for cls, r in raw.values():
            if len(r) > 1:
                gap[cls].append(r.index.to_series().diff().dt.total_seconds().median() / 60)
        for fill in ("none", "ffill", "ffill24"):
            hs = {t: (cls, hourly(r, cls, fill)) for t, (cls, r) in raw.items()}
            for cov, dis in itertools.product((0.80, 0.90, 0.95), (2, 3)):
                g = (fill, cov, dis)
                year, state = apply(hs, cov, dis)
                years[g][b] = year
                for t, st in state.items():
                    cls = hs[t][0]
                    tot[g]["linked"] += 1
                    tot[g]["usable"] += st == "usable"
                    by_cls[g][cls]["linked"] += 1
                    by_cls[g][cls]["usable"] += st == "usable"
                    if g == ("none", 0.90, 3):
                        why[cls][st] += 1
        print(b, "done", flush=True)
    cur = ("none", 0.90, 3)
    L = ["# Mortar usability rule: sensitivity", "",
         "Linked series of the bank's classes on the eight Mortar buildings of the agent runs (graphs @ 8844574c,",
         "classes following brick:isReplacedBy). Current rule: hourly means, 90% of the chosen year's",
         "hours, 3 distinct values. ffill holds the last value through hours without a sample (ffill24: for",
         "at most 24 h). The year",
         "is chosen again under each variant.", "",
         "## Usable / linked, all classes", "",
         "| fill | coverage | distinct | usable / linked | share | years (40,15,11,13,34,32,4,5) |",
         "|---|---:|---:|---|---:|---|"]
    for g in grid:
        t = tot[g]
        L.append(f"| {g[0]} | {g[1]:.2f} | {g[2]} | {t['usable']} / {t['linked']} | "
                 f"{t['usable'] / t['linked']:.3f} | {', '.join(str(years[g][b]) for b in B)} |")
    L += ["", "## By class: usable / linked", "", "| class | " + " | ".join(
        f"{f} {c:.2f}/{d}" for f, c, d in grid) + " |", "|---|" + "---:|" * len(grid)]
    for cls in sorted(by_cls[cur], key=lambda c: -by_cls[cur][c]["linked"]):
        L.append(f"| {cls} | " + " | ".join(f"{by_cls[g][cls]['usable']}/{by_cls[g][cls]['linked']}"
                                          for g in grid) + " |")
    L += ["", "## Why series fail the current rule, and how often they are sampled", "",
          "| class | usable | fail: coverage | fail: distinct values | median sampling interval (min) |",
          "|---|---:|---:|---:|---:|"]
    for cls in sorted(why, key=lambda c: -sum(why[c].values())):
        g_ = sorted(gap[cls])
        med = g_[len(g_) // 2] if g_ else float("nan")
        L.append(f"| {cls} | {why[cls]['usable']} | {why[cls]['coverage']} | {why[cls]['distinct']} | {med:.1f} |")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    (OUT.with_suffix(".json")).write_text(json.dumps(
        {"totals": {"|".join(map(str, g)): dict(tot[g]) for g in grid},
         "by_class": {"|".join(map(str, g)): {c: dict(v) for c, v in by_cls[g].items()} for g in grid},
         "years": {"|".join(map(str, g)): years[g] for g in grid},
         "why": {c: dict(v) for c, v in why.items()}}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MORTAR_DIR, type=Path)
    main(ap.parse_args().root)
