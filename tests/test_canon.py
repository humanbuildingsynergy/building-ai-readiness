"""The canon: caps, profiles, L3 rows and monotonicity."""
import random

import pytest

from bara.canon import CANONS, CAUSES, DOMAINS, END_USE, PROFILES, ceiling, end_use_streams, weighted_score

# The stream classes of the large office's published store: zone T, Sp and Occ, the whole-building
# meter, zone lighting power, equipment power and the boiler's delivered heat (Load).
LARGE_OFFICE = {"T", "Sp", "Occ", "Whole", "Lgt", "Pwr", "Load"}
RETAIL = {"T", "Sp", "Occ", "Whole", "Lgt"}


def restricted(store: set[str], profile: str | None = None) -> set[str]:
    """The classes a store exposes under a profile, with the end-use classes they derive."""
    have = store & PROFILES[profile] if profile else set(store)
    return have | end_use_streams({END_USE[s] for s in have if s in END_USE})


def test_caps():
    c = CANONS["v2"]
    assert c.total == 76
    row_sums = {d: sum(c.cap_matrix()[d].values()) for d in DOMAINS}
    assert row_sums == {"thermal": 16, "energy": 12, "airquality": 16, "equipment": 16,
                        "occupancy": 8, "lighting": 8}
    assert c.cap("lighting", "status") == 2 and c.cap("energy", "verification") == 0


def test_profiles():
    metered = {"T", "Sp", "Occ", "Whole", "Lgt", "Pwr", "Sub", "Sub2", "OAT"}
    rich = metered | {"SpC", "ActC", "ActP", "Run", "Load", "SAT"}
    got = [ceiling(s).achieved for s in ({"T"}, {"T", "Sp"}, {"T", "Sp", "Occ"}, metered, rich,
                                         rich | {"CO2", "OAF"})]
    assert got == [7, 12, 20, 52, 60, 76]


def test_l3_needs_the_separating_streams():
    c = CANONS["v2"]
    assert c.achieved_level("equipment", "diagnosis", {"Pwr"}) == 2
    assert c.achieved_level("equipment", "diagnosis", {"Pwr", "Run", "Load"}) == 3
    assert c.achieved_level("thermal", "diagnosis", {"T", "Sp", "ActC", "ActP"}) == 2
    assert c.achieved_level("thermal", "diagnosis", {"T", "Sp", "SpC", "ActC", "ActP"}) == 2   # no SAT
    assert c.achieved_level("energy", "diagnosis", {"Whole", "Sub", "Sub2"}) == 2      # no OAT
    assert c.achieved_level("thermal", "verification", {"T", "Sp", "ActC", "ActP"}) == 3
    assert c.achieved_level("thermal", "verification", {"T", "Sp", "ActC"}) == 2     # command without position
    assert c.achieved_level("thermal", "comparison", {"T", "ActC", "ActP"}) == 2     # comparison L3 needs Sp
    assert c.achieved_level("energy", "diagnosis", {"Whole", "Sub"}) == 2
    assert c.achieved_level("energy", "diagnosis", {"Whole", "Sub", "Sub2", "OAT"}) == 3


def test_l3_rows_follow_from_the_declared_causes():
    separators = {d: set() for d in DOMAINS}
    for domain, _cause, _shows, streams in CAUSES:
        separators[domain] |= {s for s in streams if s != "T(peers)"}
    for (domain, intent), rungs in CANONS["v2"].rungs.items():
        if len(rungs) < 3:
            continue
        added = rungs[2] - rungs[1] - {"Sp"}     # thermal comparison L3 also needs Sp (a setpoint difference)
        assert added <= separators[domain], (domain, intent)
        if intent in ("diagnosis", "explanation"):
            assert added == separators[domain] - rungs[1], (domain, intent)


def test_profiles_are_nested_and_restrict_a_store():
    names = list(PROFILES)
    assert all(PROFILES[a] < PROFILES[b] for a, b in zip(names, names[1:]))
    got = [ceiling(restricted(LARGE_OFFICE, p)).achieved for p in names]
    # rich == metered here: the store has no ActC, ActP, Run, SpC, SAT, OAT, CO2 or OAF series
    assert got == [7, 12, 20, 49, 49]
    assert ceiling(restricted(RETAIL, "metered")).achieved == 37


def test_end_use_classes_follow_the_metered_groups():
    assert {"Sub", "Sub2", "Pwr", "Lgt"} <= restricted(LARGE_OFFICE)
    retail = restricted(RETAIL)
    assert "Sub" in retail and "Sub2" not in retail and "Pwr" not in retail


def test_adding_a_stream_class_never_lowers_a_cell():
    rng = random.Random(1)
    vocab = sorted(set().union(*(r for rungs in CANONS["v2"].rungs.values() for r in rungs)))
    for _ in range(300):
        small = {s for s in vocab if rng.random() < 0.4}
        big = small | {s for s in vocab if rng.random() < 0.3}
        a, b = ceiling(small), ceiling(big)
        assert all(a.per_cell[cell] <= b.per_cell[cell] for cell in a.per_cell)
        # nested profiles keep their order under any positive domain weights
        w = {d: rng.expovariate(1.0) + 1e-9 for d in DOMAINS}
        assert weighted_score(a.by_domain, w) <= weighted_score(b.by_domain, w) + 1e-12


def test_equal_weights_give_the_plain_score():
    c = ceiling({"T", "Sp", "Occ", "Whole"})
    assert weighted_score(c.by_domain, dict.fromkeys(DOMAINS, 1.0)) == pytest.approx(c.score)
