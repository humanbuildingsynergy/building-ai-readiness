"""Stream-class rules of the census, on a small hand-made Brick graph."""
import pytest

from bara import census

pytestmark = pytest.mark.skipif(not census._ONTOLOGY.exists(),
                                reason="Brick ontology (bara/brick/Brick.ttl) missing")

TTL = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix : <urn:t#> .
:zone a brick:HVAC_Zone .
:vav a brick:VAV ; brick:hasPoint :zt, :sp_eff, :sp_occ .
:dmp a brick:Damper ; brick:isPartOf :vav ; brick:hasPoint :dpos .
:ahu a brick:Air_Handler_Unit ; brick:hasPoint :ahu_t, :fan_status, :saf, :sat .
:sat a brick:Supply_Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "11" ] .
:zt a brick:Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "1" ] .
:ahu_t a brick:Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "2" ] .
:sp_eff a brick:Effective_Air_Temperature_Cooling_Setpoint ;
    ref:hasExternalReference [ ref:hasTimeseriesId "3" ] .
:sp_occ a brick:Occupied_Air_Temperature_Cooling_Setpoint ;
    ref:hasExternalReference [ ref:hasTimeseriesId "4" ] .
:dpos a brick:Damper_Position_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "5" ] .
:fan_status a brick:On_Off_Status ; ref:hasExternalReference [ ref:hasTimeseriesId "6" ] .
:saf a brick:Supply_Air_Flow_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "7" ] .
:bm a brick:Building_Electrical_Meter ; brick:hasPoint :bm_p .
:bm_p a brick:Electric_Power_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "8" ] .
:sm a brick:Electrical_Meter ; brick:feeds :ahu ; brick:hasPoint :sm_p .
:sm_p a brick:Electric_Power_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "9" ] .
:lm a brick:Electrical_Meter ; brick:hasPoint :lm_p .
:lm_p a brick:Electric_Power_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "10" ] .
:co2 a brick:CO2_Sensor ; brick:isPointOf :zone .
"""


@pytest.fixture(scope="module")
def clf():
    return census._Classifier(census.Ontology())


@pytest.fixture()
def graph(tmp_path):
    path = tmp_path / "b.ttl"
    path.write_text(TTL, encoding="utf-8")
    return path


def test_rule_class_names_exist_in_brick():
    assert census.unknown_rule_classes() == set()


def test_linked_stream_classes(graph, clf):
    have, _, n = census.stream_classes(graph, clf, linked_only=True)
    assert n == 11
    # generic temperature sensor counts on the terminal unit, not on the air handler;
    # a damper position counts because its damper is part of the VAV;
    # scheduled + in-effect setpoints give SpC; one HVAC submeter + one unknown give Sub2.
    assert have == {"T", "Sp", "SpC", "ActP", "SAT", "Run", "Load", "Whole", "Sub", "Sub2"}


def test_declared_adds_the_unlinked_sensor(graph, clf):
    declared, _, _ = census.stream_classes(graph, clf, linked_only=False)
    linked, _, _ = census.stream_classes(graph, clf, linked_only=True)
    assert declared - linked == {"CO2"}


def test_a_deprecated_class_counts_with_its_brick_replacement(tmp_path):
    # the August 2026 Mortar graphs replaced Zone_Air_Temperature_Setpoint (deprecated since Brick
    # 1.3) by Target_Zone_Air_Temperature_Setpoint and Speed_Status by Speed_Mode_Status
    ttl = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix : <urn:t#> .
:vav a brick:VAV ; brick:hasPoint :sp .
:sp a brick:Target_Zone_Air_Temperature_Setpoint ; ref:hasExternalReference [ ref:hasTimeseriesId "1" ] .
:ch a brick:Chiller ; brick:hasPoint :spd .
:spd a brick:Speed_Mode_Status ; ref:hasExternalReference [ ref:hasTimeseriesId "2" ] .
"""
    path = tmp_path / "r.ttl"
    path.write_text(ttl, encoding="utf-8")
    with_repl = census._Classifier(census.Ontology(replacements=True))
    without = census._Classifier(census.Ontology(replacements=False))
    assert {"Sp", "Run"} <= census.stream_classes(path, with_repl, linked_only=True)[0]
    assert not {"Sp", "Run"} & census.stream_classes(path, without, linked_only=True)[0]


def test_an_unattached_meter_point_counts_as_no_stream_class(tmp_path, clf):
    # the August 2026 Mortar graphs retyped the building-demand series as an Electric_Energy_Sensor
    # with no parent and no feeds: it says nothing about what it meters
    ttl = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix : <urn:t#> .
:e a brick:Electric_Energy_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "1" ] .
"""
    path = tmp_path / "u.ttl"
    path.write_text(ttl, encoding="utf-8")
    assert census.stream_classes(path, clf, linked_only=True)[0] == set()
