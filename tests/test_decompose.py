import pytest

from bara.canon import ceiling
from bara.decompose import (bootstrap_interval, check_credited, decompose, diagnosis_outcome,
                            diagnosis_summary, rung_accuracy)
from bara.tables import names_true_cause


def _rows(spec):
    return [{"domain": d, "intent": i, "level": lv, "score": s} for d, i, lv, scores in spec for s in scores]


def test_four_shares_sum_to_one_and_unprobed_is_not_assumed_correct():
    c = ceiling({"T", "Sp"})                                   # 12 of 76 rungs achieved
    rows = _rows([("thermal", "status", 1, [1, 1]), ("thermal", "status", 2, [1, 0]),
                  ("thermal", "summary", 1, [0, 0])])
    d = decompose(c, rung_accuracy(rows))
    assert d.realized + d.ai_failure + d.unprobed + d.data_limitation == pytest.approx(1.0)
    assert d.realized == pytest.approx(1.5 / 76) and d.ai_failure == pytest.approx(1.5 / 76)
    assert d.unprobed == pytest.approx(9 / 76) and d.data_limitation == pytest.approx(64 / 76)
    assert d.ceiling == pytest.approx(c.score)
    assert d.per_rung[("thermal", "summary", 2)] is None


def test_accuracy_on_an_unreached_rung_earns_nothing():
    rows = _rows([("thermal", "status", 2, [1, 1, 1])])
    assert decompose(ceiling({"T"}), rung_accuracy(rows)).realized == 0.0


def test_bootstrap_brackets_the_point_estimate():
    c = ceiling({"T", "Sp"})
    rows = _rows([("thermal", "status", 1, [1, 1, 0, 1, 1]), ("thermal", "status", 2, [1, 0, 1, 0, 1])])
    lo, hi = bootstrap_interval(c, rows, draws=500)
    assert lo <= decompose(c, rung_accuracy(rows)).realized <= hi and lo < hi


def test_diagnosis_outcomes():
    f = diagnosis_outcome
    assert f(answerable=True, outcome="answered", named_cause="a", true_cause="a") == "correct"
    assert f(answerable=True, outcome="answered", named_cause="b", true_cause="a") == "ai_failure"
    assert f(answerable=True, outcome="abstained", named_cause=None, true_cause="a") == "ai_failure"
    assert f(answerable=False, outcome="abstained", named_cause=None, true_cause="a") == "correct_abstention"
    assert f(answerable=False, outcome="answered", named_cause="a", true_cause="a") == "overclaim"
    s = diagnosis_summary(["correct", "ai_failure", "correct_abstention", "overclaim", "overclaim"])
    assert s == {"answerable": 2, "accuracy": 0.5, "unanswerable": 3,
                 "overclaim_rate": pytest.approx(2 / 3)}


def test_check_credited_refuses_a_rung_the_ceiling_leaves_uncredited():
    c = ceiling({"T", "Sp", "Occ", "Whole", "Lgt", "Sub"})          # a small office: no Pwr
    ok = [{"class": "t_status_2", "domain": "thermal", "intent": "status", "level": 2}]
    check_credited(ok, c)
    bad = ok + [{"class": "q_status_1", "domain": "equipment", "intent": "status", "level": 1}]
    with pytest.raises(ValueError, match="q_status_1: equipment/status L1"):
        check_credited(bad, c)


def test_clustered_bootstrap_keeps_repeats_together():
    """Two instances on one rung, three repeats each: one always right, one always wrong. Resampling
    whole instances can only give 0, 1/2 or 1 of the rung; resampling episodes gives finer steps."""
    c = ceiling({"T"})
    rung = ("thermal", "status", 1)
    rows = [{"domain": rung[0], "intent": rung[1], "level": rung[2], "instance": inst, "repeat": k,
             "score": s} for inst, s in (("a", 1.0), ("b", 0.0)) for k in range(3)]
    lo, hi = bootstrap_interval(c, rows, draws=400, cluster="instance")
    # realized is this rung's accuracy over the canon total (76): whole instances allow 0, 1/2 or 1
    assert {round(lo * 76, 6), round(hi * 76, 6)} <= {0.0, 0.5, 1.0}, (lo, hi)
    lo_e, hi_e = bootstrap_interval(c, rows, draws=400)
    assert (hi_e - lo_e) <= (hi - lo)                      # clustering can only widen it here


def test_an_or_alternative_names_the_true_cause():
    t = "local override or controller offset"
    assert names_true_cause("controller offset", t) and names_true_cause("Local override", t)
    assert names_true_cause(t, t) and not names_true_cause("schedule change", t)
    assert names_true_cause("zone sensor fault", "zone sensor fault") and not names_true_cause(None, t)
