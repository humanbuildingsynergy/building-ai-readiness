"""bara.supplement without EnergyPlus or data files: the model edits on synthetic IDF text, and
the scenario manifest."""
import re

from bara import supplement as S

SCHED = """Schedule:Compact,
    CLGSETP_SCH_YES_OPTIMUM,  !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: Weekdays,            !- Field 2
    Until: 06:00,             !- Field 3
    26.7,                     !- Field 4
    Until: 22:00,             !- Field 5
    24.0,                     !- Field 6
    For: AllOtherDays,        !- Field 7
    Until: 24:00,             !- Field 8
    26.7;                     !- Field 9
"""
IDF = SCHED + SCHED.replace("CLGSETP", "HTGSETP").replace("26.7", "15.6").replace("24.0", "21.0") + """
ThermostatSetpoint:DualSetpoint,
    Core_bottom Dual SP Control,    !- Name
    HTGSETP_SCH_YES_OPTIMUM,    !- Heating Setpoint Temperature Schedule Name
    CLGSETP_SCH_YES_OPTIMUM;    !- Cooling Setpoint Temperature Schedule Name
"""


def test_shifted_schedule_keeps_times_and_shifts_values_after_the_cut():
    out = S._shifted_compact(S._compact(IDF, "CLGSETP_SCH_YES_OPTIMUM"), "CLGSETP_SCH_YES_OPTIMUM",
                             "NEW", ("06/14", "06/15"), -1.0)
    fields = [f.strip() for f in out.rstrip().rstrip(";").split(",")]
    assert fields[:4] == ["Schedule:Compact", "NEW", "Temperature", "Through: 06/14"]
    cut = fields.index("Through: 12/31")
    assert fields[4:cut] == ["For: Weekdays", "Until: 06:00", "26.7", "Until: 22:00", "24.0",
                             "For: AllOtherDays", "Until: 24:00", "26.7"]           # unchanged before
    assert fields[cut + 1:] == ["For: Weekdays", "Until: 06:00", "25.70", "Until: 22:00", "23.00",
                                "For: AllOtherDays", "Until: 24:00", "25.70"]       # 1 C lower after


def test_s1r_repoints_only_the_zone_thermostat():
    out = S.idf_s1r(IDF)
    dsp = re.search(r"ThermostatSetpoint:DualSetpoint,.*?;", out, re.S).group(0)
    assert "SUPP_S1R_HTG" in dsp and "SUPP_S1R_CLG" in dsp and "CLGSETP_SCH_YES_OPTIMUM" not in dsp
    assert out.count("Schedule:Compact,\n    CLGSETP_SCH_YES_OPTIMUM") == 1           # original kept
    assert "Output:Variable,SUPP_S1R_CLG,Schedule Value,Hourly;" in out


def test_s4_adds_one_load_from_its_onset_and_requests_the_damper():
    out = S.idf_s4(IDF, 40000)
    assert "SUPP_S4_Core_mid_Added_Load,\n    Core_mid," in out and "40000.0" in out
    sch = re.search(r"Schedule:Compact,\n    SUPP_S4_STEP,.*?;", out, re.S).group(0)
    assert "Through: 06/30" in sch and sch.rstrip().endswith("1;")
    assert f"Output:Variable,*,{S.DAMPER_VAR},Hourly;" in out


def test_manifest_reproduces_the_deposited_one_outside_results(tmp_path, monkeypatch):
    import json

    from bara import RESULTS_DIR
    zones = {"CORE_BOTTOM": "urn:g#Zone_F2_Z01", "CORE_MID": "urn:g#Zone_F3_Z01"}
    monkeypatch.setattr(S, "_zone_ids", lambda kg: zones)
    monkeypatch.setattr(S, "MANIFEST", tmp_path / "scenarios_supplement.json")
    made = {k: f"{S.B}__{k}" for k in ("s1r", "s3m", "s4")} | {"s1": S.FAULTED}
    S.write_manifest(made)
    deposited = json.loads((RESULTS_DIR / "faults" / "scenarios_supplement.json").read_text(encoding="utf-8"))
    assert json.loads(S.MANIFEST.read_text(encoding="utf-8")) == deposited
    assert not str(S.ROOT).startswith(str(RESULTS_DIR))
