"""Make point linkage symmetric in a published graph, without guessing.

BATS links equipment to its power points with ``brick:hasPoint`` and zone points to their zone
with ``brick:isPointOf``. Both are valid Brick and they are inverses, but an agent that follows one
direction only misses the other half. ``add_inverses`` adds the
inverse of every ``hasPoint`` and ``isPointOf`` triple, the standard OWL-inverse inference step.
It matches nothing by name and never touches the published file.

    python -m bara.graphfix            # writes $DERIVED_DIR/bats_linked/<building>/kg_linked.ttl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace

from bara import BATS_DIR, DERIVED_DIR

BRICK = Namespace("https://brickschema.org/schema/Brick#")
_OUT = DERIVED_DIR / "bats_linked"


def add_inverses(kg_in: Path, kg_out: Path) -> dict:
    """Write *kg_in* plus the inverse of every hasPoint / isPointOf triple to *kg_out*."""
    g = Graph().parse(str(kg_in), format="turtle")
    before = len(g)
    add_ip = [(p, BRICK.isPointOf, e) for e, p in g.subject_objects(BRICK.hasPoint)
              if (p, BRICK.isPointOf, e) not in g]
    add_hp = [(e, BRICK.hasPoint, p) for p, e in g.subject_objects(BRICK.isPointOf)
              if (e, BRICK.hasPoint, p) not in g]
    for t in add_ip + add_hp:
        g.add(t)
    Path(kg_out).parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(kg_out), format="turtle")
    return {"triples_in": before, "isPointOf_added": len(add_ip), "hasPoint_added": len(add_hp),
            "triples_out": len(g)}


def link_bats(bats_dir: Path, out_dir: Path = _OUT) -> dict:
    """``add_inverses`` for every clean and faulted BATS building."""
    report = {}
    for sub in ("buildings", "faulted"):
        for b in sorted(p for p in (Path(bats_dir) / sub).iterdir() if (p / "kg.ttl").exists()):
            report[b.name] = add_inverses(b / "kg.ttl", out_dir / b.name / "kg_linked.ttl")
    return report


if __name__ == "__main__":
    print(json.dumps(link_bats(Path(sys.argv[1]) if len(sys.argv) > 1 else BATS_DIR), indent=1))
