import json

from bara.faultbank import ladder, questions, separators


def test_separators_come_from_the_cause_table():
    assert separators("thermal", "local override or controller offset", ["schedule change"]) == {"SpC"}
    assert separators("thermal", "zone sensor fault",
                      ["supply-side capacity loss", "local load change"]) == {"ActC", "ActP", "SAT"}


def test_ladder_and_answerability(tmp_path):
    assert ladder({"T", "Sp"}, {"SpC"}) == [{"T", "Sp"}, {"T", "Sp", "SpC"}]
    m = tmp_path / "scenarios.json"
    m.write_text(json.dumps({"scenarios": [{
        "id": "s2", "building": "large_office__tucson__s2", "domain": "thermal",
        "observation": "Zone X has needed more cooling air than its neighbours since 2018-07-01.",
        "true_cause": "zone sensor fault",
        "rival_causes": ["local load change", "supply-side capacity loss"],
        "base_streams": ["T", "Sp"]}]}))
    qs = questions(m)
    assert [q["answerable"] for q in qs] == [False, False, False, True]
    assert qs[-1]["streams_in_scope"] == ["ActC", "ActP", "SAT", "Sp", "T"]
    assert len({q["text"] for q in qs}) == 1 and "zone sensor fault" in qs[0]["text"]
