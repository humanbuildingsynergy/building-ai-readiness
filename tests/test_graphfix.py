"""add_inverses completes hasPoint / isPointOf in both directions and matches nothing by name."""
from rdflib import Graph

from bara.graphfix import BRICK, add_inverses

TTL = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix : <urn:t#> .
:fan a brick:Supply_Fan ; brick:hasPoint :fan_p .
:fan_p a brick:Electric_Power_Sensor .
:zt a brick:Air_Temperature_Sensor ; brick:isPointOf :zone .
:zone a brick:HVAC_Zone .
:both a brick:Air_Temperature_Sensor ; brick:isPointOf :zone .
:zone brick:hasPoint :both .
:Chiller01_Electric_Power_Sensor a brick:Electric_Power_Sensor .
:Chiller01 a brick:Chiller .
"""


def test_inverses_both_ways_and_no_name_matching(tmp_path):
    src, out = tmp_path / "kg.ttl", tmp_path / "linked" / "kg_linked.ttl"
    src.write_text(TTL, encoding="utf-8")
    r = add_inverses(src, out)
    assert (r["isPointOf_added"], r["hasPoint_added"]) == (1, 1)   # :both already had both
    g = Graph().parse(str(out), format="turtle")
    t = lambda s: __import__("rdflib").URIRef("urn:t#" + s)
    assert (t("fan_p"), BRICK.isPointOf, t("fan")) in g
    assert (t("zone"), BRICK.hasPoint, t("zt")) in g
    # a point linked to nothing stays unlinked, even when its name matches an equipment item
    assert g.value(t("Chiller01_Electric_Power_Sensor"), BRICK.isPointOf) is None
    assert r["triples_out"] == r["triples_in"] + 2
    assert src.read_text(encoding="utf-8") == TTL                  # the input is untouched
