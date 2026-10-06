"""Download the public data the reproduction levels read (into $BARA_DATA, default ./data).

    python scripts/fetch_data.py                 # level 2: BATS v1.0, Mortar graphs, BTS Site B graph
    python scripts/fetch_data.py --bats          # only BATS v1.0 (enough for the level-3 smoke run)
    python scripts/fetch_data.py --mortar-series # also the Mortar series of the 8 real buildings
                                                 # (3.8 GB; level 3 only; needs huggingface_hub)
    python scripts/fetch_data.py --mortar-june   # also the June 2026 revision of the Mortar graphs
                                                 # (results/census/mortar_apps_june2026.md)

Sources (none is redistributed in this repository):
  BATS v1.0   Zenodo 10.5281/zenodo.20777376, bats_v1.0.zip (CC BY-NC 4.0)
  Mortar      Hugging Face datasets gtfierro/mortargraphs and gtfierro/mortar, pinned revisions (no
              license stated on the cards); the graphs at the Brick 1.5 update of August 2026.
  BTS         figshare 10.6084/m9.figshare.28705559, Site_B.ttl only (CC BY 4.0)

Every file is checked against the digest its host publishes (MD5 for Zenodo and figshare, the
pinned dataset revision for Hugging Face). A file already present with the right digest is kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import BATS_DIR, BTS_DIR, DATA_DIR, MORTAR_DIR  # noqa: E402

BATS_ZIP = ("https://zenodo.org/api/records/20777376/files/bats_v1.0.zip/content",
            "5fa2b37941becf60cee0eef6c01e9d1e")
BTS_SITE_B = ("https://ndownloader.figshare.com/files/53352155", "404ffc8a5261ed7ee2c9a049c54bdf25")
HF = "https://huggingface.co"
GRAPHS_REPO = "gtfierro/mortargraphs"
GRAPHS_REV = {"graphs": "8844574c5ba0f18a77e0e383b5d1e4484262a61e"}   # 2026-08-11 (census and runs)
JUNE_REV = {"graphs_june2026": "87c3d30983d75adbc4479cd66dd6dcb0b26ffb2b"}  # 2026-06-09, before the Brick 1.5 update
SERIES_REPO, SERIES_REV = "gtfierro/mortar", "453e17bf8bb245f3c050ae8fcb7233eecc6e3cec"
MORTAR_BUILDINGS = ["bldg40", "bldg15", "bldg11", "bldg13", "bldg34", "bldg32", "bldg4", "bldg5"]


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _get(url: str, dest: Path, md5: str | None = None, tries: int = 3) -> Path:
    if dest.exists() and (md5 is None or _md5(dest) == md5):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bara-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, part.open("wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            if md5 and _md5(part) != md5:
                raise IOError(f"MD5 mismatch for {url}")
            part.replace(dest)
            return dest
        except Exception as e:                  # noqa: BLE001 - retry any network error
            print(f"  {dest.name}: {e} (try {i + 1}/{tries})", flush=True)
            time.sleep(5)
    raise SystemExit(f"could not download {url}")


def bats() -> None:
    if (BATS_DIR / "buildings").is_dir() and (BATS_DIR / "faulted").is_dir():
        print(f"BATS v1.0: present at {BATS_DIR}")
        return
    z = _get(BATS_ZIP[0], DATA_DIR / "downloads" / "bats_v1.0.zip", BATS_ZIP[1])
    tmp = DATA_DIR / "downloads" / "bats_extract"
    with zipfile.ZipFile(z) as zf:                  # one top folder, synthetic_kg_building_testbed_corpus/
        zf.extractall(tmp)
    (top,) = [p for p in tmp.iterdir() if p.is_dir()]
    BATS_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(top), str(BATS_DIR))
    shutil.rmtree(tmp)
    print(f"BATS v1.0: {BATS_DIR}")


def bts() -> None:
    _get(BTS_SITE_B[0], BTS_DIR / "Site_B.ttl", BTS_SITE_B[1])
    print(f"BTS Site B graph: {BTS_DIR / 'Site_B.ttl'}")


def mortar_graphs(revs: dict = GRAPHS_REV) -> None:
    for folder, rev in revs.items():
        with urllib.request.urlopen(f"{HF}/api/datasets/{GRAPHS_REPO}/revision/{rev}", timeout=60) as r:
            files = [s["rfilename"] for s in json.load(r)["siblings"] if s["rfilename"].endswith(".ttl")]
        for f in files:
            _get(f"{HF}/datasets/{GRAPHS_REPO}/resolve/{rev}/{f}", MORTAR_DIR / folder / f)
        print(f"Mortar graphs: {len(files)} files in {MORTAR_DIR / folder} (revision {rev[:10]})")


def mortar_series() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit("the Mortar series need huggingface_hub: pip install -e .[level3]")
    for b in MORTAR_BUILDINGS:
        snapshot_download(SERIES_REPO, repo_type="dataset", revision=SERIES_REV,
                          allow_patterns=[f"collection={b}/*"], local_dir=MORTAR_DIR / "series")
        print(f"Mortar series: {b}", flush=True)
    from bara import mortar
    for b in MORTAR_BUILDINGS:
        r = mortar.convert(b, MORTAR_DIR / "graphs" / f"{b}.ttl", MORTAR_DIR / "series",
                           MORTAR_DIR / "stores" / b)
        print(f"Mortar store {b}: year {r['year']}, usable {r['usable']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bats", action="store_true", help="only BATS v1.0")
    ap.add_argument("--mortar-series", action="store_true", help="also the 8 buildings' series (3.8 GB)")
    ap.add_argument("--mortar-june", action="store_true", help="also the June 2026 revision of the Mortar graphs")
    a = ap.parse_args()
    bats()
    if not a.bats:
        mortar_graphs()
        bts()
    if a.mortar_june:
        mortar_graphs(JUNE_REV)
    if a.mortar_series:
        mortar_series()
