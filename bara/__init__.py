"""bara: the readiness decomposition of a building, from its metadata graph and its time series.

Where the data live (downloaded by ``scripts/fetch_data.py``; nothing is redistributed here):

  BARA_DATA            default <repository>/data
  BATS_DIR             default $BARA_DATA/bats_v1.0      BATS v1.0 (Zenodo 10.5281/zenodo.20777376)
  MORTAR_DIR           default $BARA_DATA/mortar         Mortar graphs and series (Hugging Face)
  BTS_DIR              default $BARA_DATA/bts            BTS Site B graph (figshare 10.6084/m9.figshare.28705559)
  DERIVED_DIR          default $BARA_DATA/derived        stores and graphs this package writes
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BARA_DATA", REPO / "data"))
BATS_DIR = Path(os.environ.get("BATS_DIR", DATA_DIR / "bats_v1.0"))
MORTAR_DIR = Path(os.environ.get("MORTAR_DIR", DATA_DIR / "mortar"))
BTS_DIR = Path(os.environ.get("BTS_DIR", DATA_DIR / "bts"))
DERIVED_DIR = Path(os.environ.get("DERIVED_DIR", DATA_DIR / "derived"))
RESULTS_DIR = REPO / "results"
SUPPLEMENT_DIR = REPO / "supplement"
BRICK_TTL = Path(__file__).resolve().parent / "brick" / "Brick.ttl"   # Brick 1.4, BSD-3-Clause
