"""The reproduction repository's own parts: drift, the deposit scrub, level 1, the supplement files."""
import csv
import filecmp
import gzip
import hashlib
import importlib.util
import json
import re
from pathlib import Path

from bara import RESULTS_DIR, SUPPLEMENT_DIR
from bara.drift import drift, label

REPO = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_drift_is_linear_from_onset_to_the_last_reading():
    series = [(f"2018-12-{d:02d}T00:00:00", 20.0) for d in range(1, 11)]
    out = dict(drift(series, "2018-12-06", None, 1.0))
    assert out["2018-12-05T00:00:00"] == 20.0                     # before onset: unchanged
    assert out["2018-12-06T00:00:00"] == 20.0                     # ramp starts at zero
    assert abs(out["2018-12-10T00:00:00"] - 21.0) < 1e-9          # full magnitude at the last reading
    vals = [out[t] for t, _ in series[5:]]
    steps = {round(b - a, 9) for a, b in zip(vals, vals[1:])}
    assert len(steps) == 1                                         # linear
    lab = label("ts1", "2018-12-06", "2018-12-10T00:00:00")
    assert lab["fault_type"] == "drift" and lab["timeseries_id"] == "ts1"


def _csv_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_drift_reproduces_the_deposited_s3m_series():
    """drift() on Core_mid's reading in the supplement's __act store gives the deposited s3m series."""
    s3m = _csv_gz(SUPPLEMENT_DIR / "large_office__2a_tampa__s3m" / "timeseries.csv.gz")
    (tsid,) = {r["timeseries_id"] for r in s3m}
    act = [(r["timestamp"], float(r["value"])) for r in
           _csv_gz(SUPPLEMENT_DIR / "large_office__2a_tampa__act" / "timeseries.csv.gz")
           if r["timeseries_id"] == tsid]
    with (SUPPLEMENT_DIR / "large_office__2a_tampa__s3m" / "faults.csv").open(encoding="utf-8") as f:
        fault = next(csv.DictReader(f))
    assert fault["timeseries_id"] == tsid and fault["end"] == act[-1][0]
    out = drift(act, fault["onset"], None, float(fault["magnitude"]))
    assert len(out) == len(s3m) == 8760
    assert all(t == r["timestamp"] and abs(v - float(r["value"])) < 1e-9 for (t, v), r in zip(out, s3m))


def test_scrub_replaces_paths_and_environment_listings_and_keeps_json_valid(tmp_path):
    scrub = _load(REPO / "scripts" / "scrub_paths.py", "scrub_paths")
    env = "environ({'USERNAME': 'x', 'PATH': 'y', 'SOME_TOKEN': 'z', 'HOME': 'h'})"
    short_env = "environ({'CATALOG_CSV': 'a', 'PATH': 'b', 'SYSTEMROOT': 'C:\\\\WINDOWS'})"
    doc = {"transcript": [{"content": r"open C:\\Users\\me\\data\\bats_v1.0\\buildings\\b\\kg.ttl"},
                          {"content": env}, {"content": short_env},
                          {"content": r"Invalid argument: ':\\\\Users\\\\me\\\\data\\\\bats_v1.0\\\\b'"}]}
    (tmp_path / "ep.json").write_text(json.dumps(doc), encoding="utf-8")
    scrub.scrub(tmp_path, [(r"C:\Users\me\data\bats_v1.0", "<BATS_DIR>")])
    out = json.loads((tmp_path / "ep.json").read_text(encoding="utf-8"))
    assert "<BATS_DIR>" in out["transcript"][0]["content"] and "Users" not in out["transcript"][0]["content"]
    assert out["transcript"][1]["content"] == scrub.ENV_NOTE
    assert out["transcript"][2]["content"] == scrub.ENV_NOTE
    assert out["transcript"][3]["content"] == r"Invalid argument: '<BATS_DIR>\\\\b'"    # drive letter dropped


def test_level1_tables_reproduce_the_deposit(tmp_path):
    from bara.tables import build_all
    names = build_all(out=tmp_path)
    assert len(names) == 8
    for n in names:
        assert filecmp.cmp(tmp_path / n, RESULTS_DIR / "final" / n, shallow=False), n


def test_supplement_files_match_their_checksums():
    lines = (SUPPLEMENT_DIR / "SHA256SUMS").read_text(encoding="utf-8").split("\n")
    entries = [ln.split(" *", 1) for ln in lines if ln.strip()]
    assert len(entries) >= 20
    for digest, rel in entries:
        assert hashlib.sha256((SUPPLEMENT_DIR / rel).read_bytes()).hexdigest() == digest, rel


# A drive-letter path: a letter, a colon, a separator and a named folder followed by another
# separator ("C:\\Users\\", "D:/data/"). URLs ("http://") and escapes in agent code ("f:\\n") do
# not match. MACHINE also catches a user folder whose drive letter was cut off (":\\Users\\").
DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:(?:\\{1,4}|/(?!/))[A-Za-z][\w.$~-]+(?:\\|/)")
MACHINE = re.compile(r"<HOME>|Documents\\|environ\(\{|SYSTEMROOT|'USERNAME'\s*:|TOKEN'\s*:\s*'|"
                     r":(?:\\|/)+Users(?:\\|/)")


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _strings(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from _strings(x)


def test_deposit_names_no_machine_path_or_environment():
    """No home folder, user folder, environment listing or drive-letter path anywhere in results/.
    JSON files are checked string by string, as decoded, so JSON escapes cannot hide a path."""
    for p in RESULTS_DIR.rglob("*"):
        if p.suffix in (".json", ".md", ".csv"):
            text = p.read_text(encoding="utf-8")
            for s in (_strings(json.loads(text)) if p.suffix == ".json" else [text]):
                hit = MACHINE.search(s) or DRIVE_PATH.search(s)
                assert not hit, f"{p}: {s[max(0, hit.start() - 40):hit.end() + 40]!r}"
