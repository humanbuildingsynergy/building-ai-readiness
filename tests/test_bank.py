"""The question bank on a small synthetic building (two zones, one air handler, two fans)."""
import math

import pytest

from bara.bank import BANK, build_bank, grade

PFX = """@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix : <urn:b#> .
"""
ZONE_ROLES = {"T": "Zone_Air_Temperature_Sensor", "SpC": "Zone_Air_Cooling_Temperature_Setpoint",
              "SpH": "Zone_Air_Heating_Temperature_Setpoint", "Occ": "Occupancy_Count_Sensor",
              "Lgt": "Electric_Power_Sensor", "Dmp": "Damper_Position_Sensor", "CO2": "CO2_Sensor",
              "OAF": "Outside_Air_Flow_Sensor", "DmpC": "Damper_Position_Command",
              "ZFlow": "Supply_Air_Flow_Sensor", "ZFlowSp": "Supply_Air_Flow_Setpoint"}
FAN_ROLES = {"Pwr": "Electric_Power_Sensor", "Run": "On_Off_Status", "Flow": "Supply_Air_Flow_Sensor",
             "FlowSp": "Supply_Air_Flow_Setpoint"}
AHU_ROLES = {"HeatV": "Heating_Valve_Command", "CoolV": "Cooling_Valve_Command",
             "OAT": "Outside_Air_Temperature_Sensor",
             # simultaneous heating/cooling is equipment L3 (Pwr + Run + Load): the valve unit needs
             # its own power and flow for q_verification_3_simul to instantiate
             "Pwr": "Electric_Power_Sensor", "Flow": "Supply_Air_Flow_Sensor"}


def _value(role, zi, h, doy):
    occupied = 8 <= h <= 18
    return {"T": 22 + zi + 2 * math.sin(h / 24 * 6.28) + (3 if doy % 7 == 0 and h == 15 else 0),
            "SpC": 24.0, "SpH": 20.0, "Occ": (5 + zi) if occupied else 0,
            "Lgt": (400 + 100 * zi) if (occupied or h == 20) else 0, "Dmp": 0.3 + 0.02 * h + 0.1 * zi,
            "CO2": 420 + (450 if occupied else 0) + 30 * zi, "OAF": 0.5 if occupied else 0.1,
            "Pwr": (3000 + 900 * zi) * (1 + 0.05 * ((doy + zi) % 5)) if occupied else 0, "Run": 1 if occupied else 0,
            "Flow": (4.0 + zi) if occupied else 0.0, "FlowSp": 4.0 if occupied else 0.0,
            "DmpC": 0.3 + 0.02 * h + 0.1 * zi, "ZFlow": (1.0 + 0.2 * zi) if occupied else 0.0,
            "ZFlowSp": 1.0 if occupied else 0.0,
            "HeatV": 0.4 if h in (7, 8) else 0.0, "CoolV": 0.6 if 8 <= h <= 16 else 0.0,
            "OAT": 10 + (doy % 90) / 3 + 5 * math.sin(h / 24 * 6.28)}[role]


@pytest.fixture(scope="module")
def building(tmp_path_factory):
    d = tmp_path_factory.mktemp("bldg")
    ttl, cat, val = [PFX, ":ahu a brick:Air_Handler_Unit ; rdfs:label \"AHU1\" ; brick:feeds :z0, :z1, :z2 ."], [], []
    def point(owner, name, cls, role, zi):
        ttl.append(f":{name} a brick:{cls} ; brick:isPointOf :{owner} ; "
                   f"ref:hasExternalReference [ ref:hasTimeseriesId \"{name}\" ] .")
        cat.append(f"{name},urn:b#{name},{cls},,,b")
        for month in (1, 4, 7, 10):
            for dom in range(1, 29):
                for h in range(24):
                    val.append(f"{name},2018-{month:02d}-{dom:02d}T{h:02d}:00:00,"
                               f"{_value(role, zi, h, month * 31 + dom)}")
    ttl.append(":floor a brick:Floor ; rdfs:label \"Floor1\" ; brick:isPartOf :bldg .")
    ttl.append(":bldg a brick:Building ; rdfs:label \"B1\" .")
    for zi in (0, 1, 2):
        ttl.append(f":z{zi} a brick:HVAC_Zone ; rdfs:label \"Zone{zi}\" ; brick:isPartOf :floor .")
        for role, cls in ZONE_ROLES.items():
            point(f"z{zi}", f"z{zi}_{role}", cls, role, zi)
        ttl.append(f":fan{zi} a brick:Supply_Fan ; rdfs:label \"Fan{zi}\" .")
        for role, cls in FAN_ROLES.items():
            point(f"fan{zi}", f"fan{zi}_{role}", cls, role, zi)
    for role, cls in AHU_ROLES.items():
        point("ahu", f"ahu_{role}", cls, role, 0)
    ttl.append(":meter a brick:Building_Electrical_Meter ; "
               "ref:hasExternalReference [ ref:hasTimeseriesId \"meter\" ] .")
    cat.append("meter,urn:b#meter,Building_Electrical_Meter,,,b")
    for month in (1, 4, 7, 10):
        for dom in range(1, 29):
            for h in range(24):
                watts = sum(_value("Lgt", z, h, 0) + _value("Pwr", z, h, month * 31 + dom) for z in (0, 1, 2)) + 2000 + 50 * month
                val.append(f"meter,2018-{month:02d}-{dom:02d}T{h:02d}:00:00,{watts * 3600}")
    (d / "kg.ttl").write_text("\n".join(ttl), encoding="utf-8")
    (d / "catalog.csv").write_text("timeseries_id,point_uri,point_class,unit,quantity_kind,building_id\n"
                                   + "\n".join(cat), encoding="utf-8")
    (d / "values.csv").write_text("timeseries_id,timestamp,value\n" + "\n".join(val), encoding="utf-8")
    return d


def test_every_class_instantiates_and_is_deterministic(building):
    bank = build_bank(building / "kg.ttl", building, n=3, seed=1)
    made = {q["class"] for q in bank}
    assert made == {qc.cid for qc, _ in BANK}, {qc.cid for qc, _ in BANK} - made
    assert bank == build_bank(building / "kg.ttl", building, n=3, seed=1)
    assert len({q["text"] for q in bank}) == len(bank)


def test_ground_truth_grades_itself_and_tolerance_holds(building):
    for q in build_bank(building / "kg.ttl", building, n=2, seed=2):
        key = "entity" if q["answer_type"] == "entity" else "value"
        assert grade(q, {key: q["gold"]}) == 1.0, q["question_id"]
        assert grade(q, None) == 0.0
        if q["answer_type"] == "number":
            assert grade(q, {"value": q["gold"] * 3 + 100}) == 0.0, q["question_id"]


def test_spot_ground_truth_values(building):
    bank = {q["question_id"]: q for q in build_bank(building / "kg.ttl", building, n=5, seed=3)}
    q = next(v for v in bank.values() if v["class"] == "o_summary_2")
    assert q["gold"] in (5.0, 6.0, 7.0)                      # occupied 08..18 inclusive at 5 or 6 people
    q = next(v for v in bank.values() if v["class"] == "l_diagnosis_2")
    assert q["gold"] == 1                               # lights on at 20:00 with nobody there
    q = next(v for v in bank.values() if v["class"] == "q_verification_3")
    assert q["gold"] == 0
    q = next(v for v in bank.values() if v["class"] == "q_verification_3_simul")
    assert q["gold"] == 1                               # valves overlap only at 08:00
    q = next(v for v in bank.values() if v["class"] == "t_verification_3_flow")
    assert q["gold"] in (0, 11)                         # Fan0 tracks its setpoint; Fan1 runs 25% high
    q = next(v for v in bank.values() if v["class"] == "t_comparison_2hop")
    assert q["gold"] == "Zone2"                         # the warmer of the two zones the AHU serves


def test_entity_answers_accept_any_name_the_graph_ties_to_the_entity(building):
    bank = build_bank(building / "kg.ttl", building, n=5, seed=3)
    q = next(v for v in bank if v["class"] == "t_comparison_2hop")
    assert q["gold"] == "Zone2" and "z2" in q["aliases"]          # label and graph id
    assert grade(q, {"entity": "z2"}) == 1.0 and grade(q, {"entity": "Zone 2"}) == 1.0
    assert grade(q, {"entity": "Zone1"}) == 0.0
    q = next(v for v in bank if v["class"] == "q_comparison_2")
    assert grade(q, {"entity": q["aliases"][0]}) == 1.0


def test_missing_streams_yield_no_questions(building, tmp_path):
    lean = tmp_path / "lean"
    lean.mkdir()
    keep = ("z0_T", "z1_T", "z2_T")
    rows = (building / "catalog.csv").read_text().splitlines()
    (lean / "catalog.csv").write_text("\n".join([rows[0]] + [r for r in rows[1:] if r.startswith(keep)]))
    vals = (building / "values.csv").read_text().splitlines()
    (lean / "values.csv").write_text("\n".join([vals[0]] + [r for r in vals[1:] if r.startswith(keep)]))
    classes = {q["class"] for q in build_bank(building / "kg.ttl", lean, n=2)}
    assert classes == {"t_status_1", "t_summary_1", "t_comparison_2", "t_comparison_2hop",
                       "t_comparison_1", "t_verification_1", "t_diagnosis_1", "t_explanation_1"}


def test_locations_that_contain_zones_are_not_equipment(building):
    from bara.bank import Building
    b = Building(building / "kg.ttl", building)
    names = {b.label(e) for e in b.equipment_with("Power")}
    assert names == {"AHU1", "Fan0", "Fan1", "Fan2"}, names   # real equipment only: no Building/Floor
    assert {b.label(z) for z in b.with_roles(b.zone_types, "Power")} == {"Zone0", "Zone1", "Zone2"}


def test_every_class_declares_its_canon_rung():
    """A class may ask for more streams than its canon rung but never fewer, so the guard and the
    ceiling can never disagree about a question."""
    from bara.bank import BANK
    from bara.canon import CANONS
    rungs = CANONS["v2"].rungs
    short = {q.cid: sorted(rungs[(q.domain, q.intent)][q.level - 1] - set(q.requires))
             for q, _ in BANK if rungs[(q.domain, q.intent)][q.level - 1] - set(q.requires)}
    assert not short, f"classes that declare less than their canon rung: {short}"


def test_roles_follow_brick_replacements():
    import json
    from pathlib import Path
    from rdflib import Graph, Namespace
    from bara import bank, census
    B = Namespace("https://brickschema.org/schema/Brick#")
    g = Graph().parse(str(census._ONTOLOGY), format="turtle")
    onto = {}
    for s, o in g.subject_objects(B.isReplacedBy):
        if str(s).startswith(str(B)) and str(o).startswith(str(B)):      # Brick classes only
            onto.setdefault(str(s).split("#")[-1], []).append(str(o).split("#")[-1])
    stored = json.loads((Path(bank.__file__).parent / "brick" / "replacements.json").read_text(encoding="utf-8"))
    assert stored == {k: sorted(v) for k, v in sorted(onto.items())}
    assert "Target_Zone_Air_Temperature_Setpoint" in bank.CLASSES["SpCool"]


def test_a_shared_label_names_the_entity_type(tmp_path):
    from rdflib import Graph, Literal, Namespace, RDF, RDFS
    from bara.bank import Building
    B, T = Namespace("https://brickschema.org/schema/Brick#"), Namespace("urn:t#")
    g = Graph()
    g.add((T.z, RDF.type, B.HVAC_Zone)); g.add((T.z, RDFS.label, Literal("DC_ZN_6")))
    g.add((T.r, RDF.type, B.Room)); g.add((T.r, RDFS.label, Literal("DC_ZN_6")))
    g.add((T.y, RDF.type, B.HVAC_Zone)); g.add((T.y, RDFS.label, Literal("Core_ZN")))
    g.serialize(str(tmp_path / "kg.ttl"), format="turtle")
    (tmp_path / "points.csv").write_text("timeseries_id,point_uri,point_class,unit\n", encoding="utf-8")
    (tmp_path / "timeseries.csv").write_text("timeseries_id,timestamp,value\n", encoding="utf-8")
    b = Building(tmp_path / "kg.ttl", tmp_path)
    assert b.named(T.z) == "DC_ZN_6 (the HVAC zone with this label, not the room that shares it)"
    assert b.label(T.z) == "DC_ZN_6" and b.named(T.y) == "Core_ZN"      # the ground truth keeps the bare label
