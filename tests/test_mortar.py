import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from bara.bank import build_bank
from bara.mortar import convert

TTL = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix : <urn:m#> .
:vav1 a brick:VAV ; brick:hasPoint :t1, :sp1, :dead, :gone .
:vav2 a brick:VAV ; brick:hasPoint :t2 .
:t1 a brick:Zone_Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "t1" ] .
:t2 a brick:Zone_Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "t2" ] .
:sp1 a brick:Zone_Air_Temperature_Setpoint ; ref:hasExternalReference [ ref:hasTimeseriesId "sp1" ] .
:dead a brick:Supply_Air_Flow_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "dead" ] .
:gone a brick:Occupancy_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "gone" ] .
"""


def _write(root, tsid, values_by_15min):
    d = root / "collection=bx" / f"uuid={tsid}"
    d.mkdir(parents=True)
    idx = pd.date_range("2016-01-01", periods=len(values_by_15min), freq="15min", tz="UTC", name="time")
    pd.DataFrame({"value": values_by_15min, "label": "x", "uri": "u"}, index=idx).to_parquet(d / "a.parquet")


def test_convert_classifies_and_the_bank_reads_the_store(tmp_path):
    (tmp_path / "bx.ttl").write_text(TTL, encoding="utf-8")
    n = 366 * 96
    _write(tmp_path / "pq", "t1", [21 + (i % 96) / 48 for i in range(n)])
    _write(tmp_path / "pq", "t2", [22 + (i % 96) / 40 for i in range(n)])
    _write(tmp_path / "pq", "sp1", [23 + (i // 96 % 3) for i in range(n)])
    _write(tmp_path / "pq", "dead", [0.0] * n)                       # held, but constant
    r = convert("bx", tmp_path / "bx.ttl", tmp_path / "pq", tmp_path / "store")
    assert (r["year"], r["usable"], r["unusable"], r["absent"]) == (2016, 3, 1, 1)
    assert r["by_class"]["Supply_Air_Flow_Sensor"] == {"unusable": 1}
    bank = build_bank(tmp_path / "bx.ttl", tmp_path / "store", n=2, zone_types={"VAV"})
    assert {"t_status_1", "t_comparison_2"} <= {q["class"] for q in bank}
    q = next(q for q in bank if q["class"] == "t_summary_1")
    assert 21 < q["gold"] < 24                                      # hourly means of the 15-min data


def test_fahrenheit_temperatures_are_converted(tmp_path):
    (tmp_path / "bx.ttl").write_text(TTL, encoding="utf-8")
    n = 366 * 96
    _write(tmp_path / "pq", "t1", [70 + (i % 96) / 48 for i in range(n)])   # degF
    _write(tmp_path / "pq", "t2", [22 + (i % 96) / 40 for i in range(n)])   # degC
    r = convert("bx", tmp_path / "bx.ttl", tmp_path / "pq", tmp_path / "store")
    assert r["converted_from_degF"] == 1
    bank = build_bank(tmp_path / "bx.ttl", tmp_path / "store", n=5, zone_types={"VAV"})
    truths = [q["gold"] for q in bank if q["class"] == "t_summary_1"]
    assert truths and all(15 < g < 30 for g in truths)                      # all in degC after conversion


def test_points_of_a_part_count_for_its_whole(tmp_path):
    """The damper signal hangs on a Damper that isPartOf the VAV; the bank must see it on the VAV."""
    ttl = TTL + """
:dmp1 a brick:Damper ; brick:isPartOf :vav1 ; brick:hasPoint :d1 .
:d1 a brick:Damper_Position_Setpoint ; ref:hasExternalReference [ ref:hasTimeseriesId "d1" ] .
"""
    (tmp_path / "bx.ttl").write_text(ttl, encoding="utf-8")
    n = 366 * 96
    _write(tmp_path / "pq", "t1", [21 + (i % 96) / 48 for i in range(n)])
    _write(tmp_path / "pq", "d1", [20 + (i % 96) for i in range(n)])
    convert("bx", tmp_path / "bx.ttl", tmp_path / "pq", tmp_path / "store")
    from bara.bank import Building
    b = Building(tmp_path / "bx.ttl", tmp_path / "store", {"VAV"})
    assert [b.label(z) for z in b.with_roles({"VAV"}, "T", "ActC")] == ["vav1"]


def test_fed_room_is_an_alias_only_when_one_terminal_feeds_it(tmp_path):
    """RM1 is fed only by vav1, so it names vav1; RM2 is fed by vav2 and vav3, so it names neither."""
    ttl = TTL + """
:vav3 a brick:VAV .
:rm1 a brick:HVACZone ; rdfs:label "RM1" .
:rm2 a brick:HVACZone ; rdfs:label "RM2" .
:vav1 brick:feeds :rm1 .
:vav2 brick:feeds :rm2 .
:vav3 brick:feeds :rm2 .
"""
    ttl = "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" + ttl
    (tmp_path / "bx.ttl").write_text(ttl, encoding="utf-8")
    n = 366 * 96
    _write(tmp_path / "pq", "t1", [21 + (i % 96) / 48 for i in range(n)])
    convert("bx", tmp_path / "bx.ttl", tmp_path / "pq", tmp_path / "store")
    from rdflib import URIRef
    from bara.bank import Building
    b = Building(tmp_path / "bx.ttl", tmp_path / "store", {"VAV"})
    assert "RM1" in b.aliases(URIRef("urn:m#vav1"))
    assert "RM2" not in b.aliases(URIRef("urn:m#vav2")) and "RM2" not in b.aliases(URIRef("urn:m#vav3"))


def test_energy_level3_classes_need_outside_air_temperature():
    """Both energy/comparison L3 classes carry the canon's full requirement (Whole, Sub2, OAT)."""
    from bara.bank import BANK
    req = {q.cid: set(q.requires) for q, _ in BANK}
    assert req["e_comparison_3"] == req["e_comparison_3_weather"] == {"Whole", "Sub2", "OAT"}
