"""Merge the BATS v1.0 L3 supplement with BATS v1.0 into complete building stores (standard library only).

    python merge_supplement.py --bats <path to BATS v1.0> --out <output folder>

Writes one folder per scenario building, each with kg.ttl, points.csv, timeseries.csv and, where the
building carries a fault, faults.csv:

  large_office__2a_tampa__faulted  BATS v1.0 faulted building + the scheduled cooling setpoint (SpC)
  large_office__2a_tampa__act      the supplement's clean re-simulation with VAV damper positions (ActP)
  large_office__2a_tampa__s1r      schedule-change scenario (full store from the supplement)
  large_office__2a_tampa__s4       internal-load-step scenario (full store from the supplement)
  large_office__2a_tampa__s3m      __act with Core_mid's reading drifted (the supplement's series)

The graph of each is the BATS v1.0 graph of its base building followed by the supplement's
addendum.ttl (both Turtle, so the concatenation is one valid graph). The supplement's
timeseries.csv files are stored gzipped (timeseries.csv.gz); the output is plain CSV.
"""
import argparse
import csv
import gzip
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "large_office__2a_tampa"


def _src(p):
    """*p*, or *p*.gz where the file is stored compressed."""
    p = Path(p)
    return p if p.exists() else p.with_name(p.name + ".gz")


def _open(p, newline=""):
    p = _src(p)
    if p.suffix == ".gz":
        return gzip.open(p, "rt", encoding="utf-8", newline=newline)
    return open(p, encoding="utf-8", newline=newline)


def _copy(src, dest):
    with _open(src) as r, open(dest, "w", encoding="utf-8", newline="") as w:
        shutil.copyfileobj(r, w)


def _cat(parts, dest):
    with open(dest, "w", encoding="utf-8", newline="") as w:
        for i, p in enumerate(parts):
            with _open(p, newline=None) as r:
                lines = r.read().splitlines(keepends=True)
            w.writelines(lines if i == 0 else lines[1:])


def _graph(bats_kg, addendum, dest):
    with open(dest, "w", encoding="utf-8") as w:
        w.write(Path(bats_kg).read_text(encoding="utf-8"))
        if addendum is not None and Path(addendum).exists():
            w.write("\n")
            w.write(Path(addendum).read_text(encoding="utf-8"))


def main(bats: Path, out: Path) -> None:
    clean_kg = bats / "buildings" / BASE / "kg.ttl"
    # faulted: BATS store + the SpC series
    f = f"{BASE}__faulted"
    d = out / f
    d.mkdir(parents=True, exist_ok=True)
    for name in ("points.csv", "timeseries.csv"):
        _cat([bats / "faulted" / f / name, HERE / f / name], d / name)
    shutil.copyfile(bats / "faulted" / f / "faults.csv", d / "faults.csv")
    _graph(bats / "faulted" / f / "kg.ttl", HERE / f / "addendum.ttl", d / "kg.ttl")
    # full stores from the supplement
    for s in ("act", "s1r", "s4"):
        name = f"{BASE}__{s}"
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for fn in ("points.csv", "timeseries.csv", "faults.csv"):
            if _src(HERE / name / fn).exists():
                _copy(HERE / name / fn, d / fn)
        _graph(clean_kg, HERE / name / "addendum.ttl", d / "kg.ttl")
    # s3m: __act with the drifted series in place of Core_mid's reading
    act, name = out / f"{BASE}__act", f"{BASE}__s3m"
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    drift = {}
    with _open(HERE / name / "timeseries.csv") as fh:
        for r in csv.DictReader(fh):
            drift[(r["timeseries_id"], r["timestamp"])] = r["value"]
    with open(act / "timeseries.csv", encoding="utf-8", newline="") as fi, \
         open(d / "timeseries.csv", "w", encoding="utf-8", newline="") as fo:
        rd = csv.DictReader(fi)
        wr = csv.DictWriter(fo, fieldnames=rd.fieldnames)
        wr.writeheader()
        for r in rd:
            r["value"] = drift.get((r["timeseries_id"], r["timestamp"]), r["value"])
            wr.writerow(r)
    shutil.copyfile(act / "points.csv", d / "points.csv")
    shutil.copyfile(act / "kg.ttl", d / "kg.ttl")
    shutil.copyfile(HERE / name / "faults.csv", d / "faults.csv")
    print("wrote", ", ".join(sorted(p.name for p in out.iterdir() if p.is_dir())))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bats", required=True, type=Path, help="unpacked BATS v1.0 (with buildings/ and faulted/)")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    main(a.bats, a.out)
