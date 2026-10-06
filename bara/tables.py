"""Level 1: every result table, from the deposited run summaries alone (CPU, no data download).

    python -m bara.tables                      # writes results/final/*.md from results/agent_runs
    python -m bara.tables --runs <dir> --out <dir>    # e.g. a re-run under $DERIVED_DIR/agent_runs

Inputs: the per-building summaries and diagnosis rows under the runs folder, the ceilings in
results/ceilings.json and the Mortar usability counts in results/mortar/usability.json (level 2
recomputes both from the public data). The rows of the bank's first 35 classes come from
final1_<profile> (sweep building) and final2 (other buildings). The three classes re-run after a
correction to how their questions name locations (bara.run.RERUN_CLASSES) take their rows from the
re-run blocks final8c_rich and final8c. The file names (run8.md and so on) are the run labels; each
table's heading names the manuscript item it supports.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from bara import RESULTS_DIR, bank, canon, decompose
from bara.run import ADDED_CLASSES, COMPARE, MORTAR, REF, RERUN_CLASSES, SWEEP, SWEEP_PROFILES
from bara.stores import deposited_ceiling

RUNS = RESULTS_DIR / "agent_runs"
OUT = RESULTS_DIR / "final"
OTHERS = ["large_office__4a_newyork", "large_office__5a_buffalo", "medium_office__2a_tampa",
          "medium_office__4a_newyork", "medium_office__5a_buffalo", "small_office__2a_tampa",
          "small_office__4a_newyork", "small_office__5a_buffalo"]


# ── reading ──────────────────────────────────────────────────────────────────────────────────
def _rows(runs: Path, label: str, building: str, model: str = REF) -> list[dict]:
    p = runs / label / model.replace(":", "_") / f"summary_{building}.json"
    return json.loads(p.read_text(encoding="utf-8"))["rows"] if p.exists() else []


def _plain(rows: list[dict]) -> list[dict]:
    """Rows without the merged_from marker (a summary row copied in from a re-run block)."""
    return [{k: v for k, v in r.items() if k != "merged_from"} for r in rows]


def _first_classes(runs: Path, label: str, building: str, rerun: str, model: str = REF) -> list[dict]:
    """Rows of the bank's first 35 classes: the block's rows without the re-run classes, then the
    re-run classes from their own block (*rerun*)."""
    keep = [r for r in _rows(runs, label, building, model) if r["question"] not in RERUN_CLASSES]
    return _plain(keep) + _plain(_rows(runs, rerun, building, model))


N_FIRST, N_ADDED = len(bank.BANK) - len(ADDED_CLASSES), len(ADDED_CLASSES)
RERUN_TEXT = (f"Three classes ({', '.join(RERUN_CLASSES)}) carry their rows from a re-run after a "
              "correction to how their questions name locations.")


def _acc(rows: list[dict]) -> float:
    return sum(r["score"] for r in rows) / len(rows)


def _fmt(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def class_spread(rows: list[dict]) -> dict[str, tuple[float, float, float]]:
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["question"]][r["repeat"]].append(r["score"])
    out = {}
    for c, reps in sorted(per.items()):
        means = [sum(v) / len(v) for v in reps.values()]
        out[c] = (st.mean(means), min(means), max(means))
    return out


def names_true_cause(named: str | None, true_cause: str) -> bool:
    """The named cause is the true one: the whole label, or one alternative an "or" label joins."""
    if not named:
        return False
    norm = lambda s: " ".join(s.lower().split())
    return norm(named) in {norm(true_cause), *(norm(a) for a in true_cause.split(" or "))}


def _write(out: Path, name: str, lines: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _domains(rows):
    dom = defaultdict(list)
    for r in rows:
        dom[r["domain"]].append(r["score"])
    return lambda k: f"{sum(dom[k]) / len(dom[k]):.2f} ({len(dom[k])})" if dom[k] else "—"


# ── the tables ───────────────────────────────────────────────────────────────────────────────
def mean_rung(d) -> float:
    """A: the mean of the per-rung accuracies over the probed rungs (decompose's per_rung; None =
    unprobed). A_r = C_ans(I) * A exactly when every credited rung is probed."""
    vals = [a for a in d.per_rung.values() if a is not None]
    return sum(vals) / len(vals)


def _a_check(c, d) -> str:
    a = mean_rung(d)
    if d.unprobed > 0:
        return f"C_ans x A = {c.score * a:.3f} (A_r = {d.realized:.3f}; not equal, {d.unprobed:.3f} of the canon unprobed)"
    ok = abs(c.score * a - d.realized) < 5e-4
    return f"C_ans x A = {c.score * a:.3f}, A_r = {d.realized:.3f}: {'equal to the third decimal' if ok else 'NOT EQUAL'}"


def per_repeat(c, rows) -> list[tuple[int, int, float, float, float]]:
    """(repeat, episodes, pooled accuracy, A, A_r) of each repeat of a sweep block."""
    out = []
    for rep in sorted({r["repeat"] for r in rows}):
        rr = [r for r in rows if r["repeat"] == rep]
        d = decompose.decompose(c, decompose.rung_accuracy(rr))
        out.append((rep, len(rr), sum(r["score"] for r in rr) / len(rr), mean_rung(d), d.realized))
    return out


def per_repeat_lines(blocks) -> list[str]:
    L = ["", "## Per repeat (run-to-run variance)", "",
         "| profile | repeat | episodes | accuracy (episodes) | A (mean rung) | realized |",
         "|---|---:|---:|---:|---:|---:|"]
    spread = []
    for prof, reps in blocks:
        for rep, n, acc, a, ar in reps:
            L.append(f"| {prof} | {rep} | {n} | {acc:.3f} | {a:.3f} | {ar:.3f} |")
        rng = lambda i: f"{min(x[i] for x in reps):.3f}–{max(x[i] for x in reps):.3f}"
        spread.append(f"- {prof}: accuracy {rng(2)}, A {rng(3)}, realized {rng(4)}")
    return L + ["", "Range across the three repeats:", ""] + spread


def sweep(runs: Path, out: Path) -> None:
    """run8.md: the readiness decomposition of the sweep building by profile, all 64 classes."""
    L = ["# Instrumentation sweep (Table 8, Figure 7)", "",
         f"Readiness decomposition of `{SWEEP}` by profile. Linked graph, the bank's {N_FIRST + N_ADDED} "
         f"classes (its first {N_FIRST} and the {N_ADDED} added for the remaining rungs), bank seed 0,",
         f"3 instances per class, 3 repeats, {REF}.",
         "Metered and rich are identical on published BATS (no ActC, ActP, CO2, OAF, SAT, Run or SpC",
         "series), so rich is run once and reported for both. " + RERUN_TEXT,
         "The 95% interval is a bootstrap clustered by question instance: instances are resampled within",
         "each rung and all repeats of an instance stay together (2,000 draws, seed 0).", "",
         "| profile | ceiling | episodes | accuracy (episodes) | A (mean rung) | realized | AI failure | unprobed "
         "| data limit | realized 95% CI |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    detail, episode_ci, checks, reps = [], [], [], []
    bank_classes = {q.cid: q for q, _ in bank.BANK}
    for prof in SWEEP_PROFILES:
        c = deposited_ceiling(SWEEP, prof)
        rows = _first_classes(runs, f"final1_{prof}", SWEEP, "final8c_rich" if prof == "rich" else "_none")
        rows = rows + _rows(runs, f"final8_{prof}", SWEEP)
        d = decompose.decompose(c, decompose.rung_accuracy(rows))
        elo, ehi = decompose.bootstrap_interval(c, rows)
        lo, hi = decompose.bootstrap_interval(c, rows, cluster="instance")
        episode_ci.append(f"- {prof}: {elo:.3f}–{ehi:.3f} (episode-level) against {lo:.3f}–{hi:.3f} "
                          f"(clustered by instance)")
        checks.append(f"- {'metered = rich' if prof == 'rich' else prof}: {_a_check(c, d)}")
        reps.append(("metered = rich" if prof == "rich" else prof, per_repeat(c, rows)))
        L.append(f"| {'metered = rich' if prof == 'rich' else prof} | {c.achieved}/{c.total} | {len(rows)} | "
                 f"{_acc(rows):.3f} | {mean_rung(d):.3f} | {d.realized:.3f} | {d.ai_failure:.3f} | {d.unprobed:.3f} | "
                 f"{d.data_limitation:.3f} | {lo:.3f}–{hi:.3f} |")
        detail += ["", f"## {prof}: per-rung accuracy (achieved rungs; — = unprobed)", "",
                   "| rung | accuracy |", "|---|---:|"]
        detail += [f"| {dm} {it} L{lv} | {_fmt(a)} |" for (dm, it, lv), a in sorted(d.per_rung.items())]
        detail += ["", f"### {prof}: per-class spread over 3 repeats (mean, min, max)", "",
                   "| class | mean | min | max |", "|---|---:|---:|---:|"]
        detail += [f"| {k} | {m:.2f} | {a:.2f} | {b:.2f} |" for k, (m, a, b) in class_spread(rows).items()]
        made = {r["question"] for r in _rows(runs, f"final8_{prof}", SWEEP)}
        have = set(json.loads((RESULTS_DIR / "ceilings.json").read_text(encoding="utf-8"))
                   [SWEEP][prof]["store_streams"])
        empty = []
        for k in ADDED_CLASSES:
            if k in made:
                continue
            miss = [x for x in bank_classes[k].requires if x not in have]
            empty.append(f"{k} (needs {', '.join(miss)})" if miss else f"{k} (no fair instance in 40 draws)")
        detail += ["", f"Added classes with no instance at {prof}: " + ("; ".join(empty) or "none")]
    L += ["", "accuracy (episodes) = share of graded episodes answered correctly, pooled over rungs; A = mean",
          "of the per-rung accuracies over the probed rungs (the manuscript's A).", ""] + checks
    L += per_repeat_lines(reps)
    L += ["", "For comparison, the interval that resamples single episodes:", ""] + episode_ci
    _write(out, "run8", L + detail)


def other_buildings(runs: Path, out: Path) -> None:
    """run8b.md: all 64 classes on the other eight BATS buildings."""
    L = ["# Other eight buildings of the corpus (Table 10)", "",
         f"All {N_FIRST + N_ADDED} classes of the bank, full store, linked graph, bank seed 0, 3 instances "
         f"per class, 1 repeat, {REF}.",
         "Cells: accuracy (episodes). " + RERUN_TEXT, "",
         "| building | ceiling | episodes | accuracy (episodes) | A (mean rung) | thermal | energy | equipment "
         "| occupancy | lighting |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    a_all = []
    for b in OTHERS:
        rows = _first_classes(runs, "final2", b, "final8c") + _rows(runs, "final8b", b)
        f = _domains(rows)
        c = deposited_ceiling(b, None)
        a_b = mean_rung(decompose.decompose(c, decompose.rung_accuracy(rows)))
        a_all.append(a_b)
        L.append(f"| {b} | {c.achieved}/{c.total} | {len(rows)} | {_acc(rows):.3f} | {a_b:.3f} | {f('thermal')} | "
                 f"{f('energy')} | {f('equipment')} | {f('occupancy')} | {f('lighting')} |")
    L += ["", "accuracy (episodes) = share of graded episodes answered correctly, pooled; A = mean of the",
          f"per-rung accuracies over the probed rungs. A across the eight: {min(a_all):.3f} to {max(a_all):.3f}."]
    _write(out, "run8b", L)


def agents(runs: Path, out: Path) -> None:
    """run3.md: AI failure by model on the sweep building."""
    L = ["# Comparison models (Figure 8)", "",
         f"AI failure by model. `{SWEEP}`, full store, linked graph, the bank's first {N_FIRST} classes "
         "(seed 0, 3 instances), 1 repeat.",
         f"Three classes ({', '.join(RERUN_CLASSES)}) were re-run for every model after a correction to",
         f"how their questions name locations. The reference row is `{REF}` from the sweep at the rich",
         "profile, first repeat only.", "",
         "| model | episodes | accuracy | answered | abstained | no_answer | error | mean s |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    ref = [r for r in _first_classes(runs, "final1_rich", SWEEP, "final8c_rich") if r["repeat"] == 0]
    rows_by = {REF: ref} | {m: _plain(_rows(runs, "final3", SWEEP, m)) for m in COMPARE}
    errs = {}
    for m, rows in rows_by.items():
        oc = Counter(r["outcome"] for r in rows)
        L.append(f"| {m}{' (reference)' if m == REF else ''} | {len(rows)} | {_acc(rows):.3f} | {oc['answered']} | "
                 f"{oc['abstained']} | {oc['no_answer']} | {oc['error']} | "
                 f"{st.mean(r['seconds'] for r in rows):.0f} |")
        if oc["error"] and m != REF:
            for f in sorted(glob.glob(str(runs / "final3" / m.replace(":", "_") / "*__*.json"))):
                h = [t for t in json.loads(Path(f).read_text(encoding="utf-8"))["transcript"]
                     if t["role"] == "harness"]
                if h:
                    errs[m] = h[0]["error"][:240]
                    break
    L += ["", "Harness errors, first per model:", ""] + [f"- `{m}`: {e}" for m, e in errs.items()]
    _write(out, "run3", L)


def mortar_rows(runs: Path, b: str) -> list[dict]:
    """Rows of one Mortar building: final5 plus the setpoint classes (final5sp), or the full re-run
    (final5r) of a building whose data year moved with the zone setpoints, without the excluded
    questions. A fresh `python -m bara.run mortar` writes the whole bank as final5, which this reads
    as is."""
    rows = _rows(runs, "final5r", b) or _rows(runs, "final5", b) + _rows(runs, "final5sp", b)
    excluded = excluded_questions().get(b, {})
    return [r for r in rows if r["instance"] not in excluded]


def excluded_questions() -> dict:
    """Mortar questions the actuation rule excludes (results/mortar/run5_excluded.json): the thermal
    L3 classes need T, Sp, the actuation command (ActC) and the actuation response (ActP) on one
    zone. Building -> {instance: reason}."""
    f = RESULTS_DIR / "mortar" / "run5_excluded.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def mortar(runs: Path, out: Path) -> None:
    use = json.loads((RESULTS_DIR / "mortar" / "usability.json").read_text(encoding="utf-8"))
    L = ["# Real buildings (Section 5.6)", "",
         "Mortar buildings, accuracy with spread. "
         f"Published graphs (gtfierro/mortargraphs @ 8844574c), bank seed 0, 3 instances, zone types "
         f"VAV/RVAV, {REF}. 3 repeats on bldg40 and bldg15, 1 on the rest. Stores and bank follow",
         "brick:isReplacedBy, so the zone setpoints (Target_Zone_Air_Temperature_Setpoint) are in. Rows:",
         "final5 plus the setpoint classes (final5sp); bldg11 and bldg4 re-run in full (final5r), their",
         "data year having moved with the setpoints. The thermal L3 classes need T, Sp, the actuation command",
         "and the actuation response on one zone; the questions that rule excludes (results/mortar/",
         "run5_excluded.json) are left out.", "",
         "| building | year | usable / declared | episodes | accuracy | repeat min–max |",
         "|---|---:|---|---:|---:|---|"]
    by_cls, tot = defaultdict(list), []
    for b in MORTAR:
        rows = mortar_rows(runs, b)
        per_rep = defaultdict(list)
        for r in rows:
            per_rep[r["repeat"]].append(r["score"])
            by_cls[r["question"]].append(r["score"])
        tot += rows
        accs = [sum(v) / len(v) for v in per_rep.values()]
        spread = f"{min(accs):.3f}–{max(accs):.3f}" if len(accs) > 1 else "—"
        L.append(f"| {b} | {use[b]['year']} | {use[b]['usable']} / {use[b]['linked_wanted']} | {len(rows)} | "
                 f"{_acc(rows):.3f} | {spread} |")
    L += ["", f"All: {sum(r['score'] for r in tot):.0f} of {len(tot)} "
              f"({sum(r['score'] for r in tot) / len(tot):.3f}).", "", "| class | correct |", "|---|---:|"]
    L += [f"| {c} | {sum(v):.0f}/{len(v)} |" for c, v in sorted(by_cls.items())]
    _write(out, "run5", L)


def graphs(runs: Path, out: Path) -> None:
    """run6.md: the published graph against the linked graph."""
    L = ["# Original and linked graph (Section 5.1)", "",
         "Graph heterogeneity: the published kg.ttl against kg_linked.ttl (bara.graphfix). "
         f"`{SWEEP}`, equipment and energy-comparison classes, bank seed 0 (built on the linked graph,",
         f"so both runs get the same questions), 3 instances, 3 repeats each, {REF}.", "",
         "| graph | episodes | accuracy | per-repeat accuracy |", "|---|---:|---:|---|"]
    res = {}
    for lab in ("published", "linked"):
        rows = _rows(runs, f"final6_{lab}", SWEEP)
        per = defaultdict(list)
        for r in rows:
            per[r["repeat"]].append(r["score"])
        res[lab] = [sum(v) / len(v) for _, v in sorted(per.items())]
        L.append(f"| {lab} | {len(rows)} | {_acc(rows):.3f} | {', '.join(f'{a:.3f}' for a in res[lab])} |")
    diffs = [a - b for a, b in zip(res["linked"], res["published"])]
    L += ["", f"Linked minus published, per repeat: {', '.join(f'{d:+.3f}' for d in diffs)}; mean "
              f"{st.mean(diffs):+.3f}, range {min(diffs):+.3f} to {max(diffs):+.3f}."]
    _write(out, "run6", L)


# ── unanswerable questions: the classes a profile cannot support (final9) ───────────────────────────────────────────
# Words that show an abstention names a stream class (lower case; a prefix matches longer words).
_ACTUATION_WORDS = ["damper", "valve", "actuat", "reheat", "terminal", "airflow", "air flow"]
NAMES = {"T": ["zone_air_temperature_sensor", "temperature sensor"], "Sp": ["setpoint", "set point"],
         "SpC": ["schedul", "occupied_"], "ActC": _ACTUATION_WORDS, "ActP": _ACTUATION_WORDS,
         "SAT": ["supply_air_temp", "supply air temp", "discharge"], "OAT": ["outside_air_temp", "outside air temp", "outdoor", "weather", "dry-bulb", "dry bulb"],
         "Occ": ["occupan", "presence", "people"], "CO2": ["co2", "carbon dioxide"], "OAF": ["outdoor air flow", "outside air flow", "outside_air_flow", "ventilation"],
         "Whole": ["meter", "whole-building", "whole building", "building-level", "building level"],
         "Sub": ["submeter", "sub-meter", "end-use", "end use", "lighting", "plug", "power"], "Sub2": ["submeter", "end-use", "end use", "lighting", "plug", "power"],
         "Pwr": ["power", "electric", "energy"], "Run": ["status", "run", "on/off", "command", "start"],
         "Load": ["flow", "load", "heating rate", "cooling rate", "thermal"],
         "Lgt": ["lighting", "light", "illuminance", "electric_power_sensor", "electric power"]}   # BATS lighting = zone power


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def unanswerable(rows: list[dict]) -> list[str]:
    """run9.md: per profile, the overclaim rate (Wilson 95%), abstentions naming a stream the class
    lacks, and the classes that drew answers (with whether the answer happened to be right)."""
    L = ["# Unanswerable questions (Section 5.1)", "",
         "The data limitation tested on the sweep building. "
         f"`large_office__2a_tampa`, linked graph, the store restricted to the profile as in the sweep, {REF}.",
         "Every class the profile cannot support but the full store can (question and ground truth from the",
         "full store), 1 instance, 3 repeats. The right outcome is an abstention; any answer is an overclaim,",
         "right or wrong. Errors (failed requests to the model) are left out of the rate.", "",
         "| profile | classes | episodes | abstained | answered (overclaim) | no answer | error | overclaim rate | 95% CI (Wilson) | abstentions naming a lacking stream |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    detail = []
    for prof in ("minimal", "comfort", "standard"):
        R = [r for r in rows if r["profile"] == prof]
        oc = Counter(r["outcome"] for r in R)
        n = len(R) - oc["error"]
        k = sum(r["overclaim"] for r in R)
        lo, hi = wilson(k, n)
        have = set(canon.PROFILES[prof])
        ab = [r for r in R if r["outcome"] == "abstained"]
        named = sum(any(w in r["needed_streams"].lower() for s in r["requires"] if s not in have
                        for w in NAMES.get(s, [s.lower()])) for r in ab)
        L.append(f"| {prof} | {len({r['class'] for r in R})} | {len(R)} | {oc['abstained']} | {oc['answered']} | "
                 f"{oc['no_answer']} | {oc['error']} | {k / n:.3f} | {lo:.3f}–{hi:.3f} | {named} / {len(ab)} |")
        by = Counter((r["class"], r["answer_right"]) for r in R if r["overclaim"])
        if by:
            detail.append(f"- {prof}: " + ", ".join(f"{c} {v}× ({'right' if ok else 'wrong'})"
                                                    for (c, ok), v in sorted(by.items(), key=lambda x: -x[1])))
    L += ["", "Classes that drew answers:"] + (detail or ["- none"])
    return L


def unanswerable_table(runs: Path, out: Path) -> None:
    f = runs / "final9" / "rows.json"
    if f.exists():
        _write(out, "run9", unanswerable(json.loads(f.read_text(encoding="utf-8"))))


# ── the paired diagnosis at 20 repeats (final4s + final4s_more) ──────────────────────────────
def fisher(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """Fisher's exact test on [[a, b], [c, d]] (row 1 = with the separating stream, column 1 = true
    cause named): (one-sided p that row 1 names it more often, two-sided p)."""
    r1, c1, n = a + b, a + c, a + b + c + d
    pmf = lambda x: math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)
    xs = range(max(0, r1 - (n - c1)), min(r1, c1) + 1)
    p0 = pmf(a)
    return (sum(pmf(x) for x in xs if x >= a),
            min(1.0, sum(pmf(x) for x in xs if pmf(x) <= p0 * (1 + 1e-9))))


def pairs20(rows: list[dict], source: str = "the 5 of final4s plus 15 of final4s_more") -> list[str]:
    """run4s20.md: the four paired scenarios, counts with Wilson intervals and Fisher tests. *source*
    names the run labels the rows come from."""
    def kind(r):
        if r["outcome"] != "answered":
            return "abstained" if r["outcome"] == "abstained" else "no answer"
        if not r["answerable"]:
            return "overclaimed"
        return "correct cause" if names_true_cause(r["named"], r["true_cause"]) else "wrong cause"
    true = lambda r: r["outcome"] == "answered" and names_true_cause(r["named"], r["true_cause"])
    grp = defaultdict(list)
    for r in rows:
        grp[(r["scenario"], r["rung"])].append(r)
    n_rep = max(len(v) for v in grp.values())
    L = ["# Paired diagnosis, 20 repeats (Figure 9)", "",
         f"Four scenarios in two look-alike pairs (`results/faults/scenarios_supplement.json`). Rung 0 holds T and "
         f"Sp only, so the right answer is an abstention; rung 1 adds the separating stream (SpC for s1/s1r, ActP, "
         f"the damper position, for s3m/s4), so the right answer is the true cause. {n_rep} repeats per scenario and rung "
         f"({source}), {REF}.",
         "Counts with Wilson 95% intervals. \"true cause named\" counts an answer naming the true cause",
         "at either rung (at rung 0 it is also an overclaim).", "",
         "| scenario | rung | n | abstained | overclaimed | correct cause | wrong cause | no answer | true cause named |",
         "|---|---|---:|---|---|---|---|---:|---|"]
    ci = lambda k, n: f"{k} ({wilson(k, n)[0]:.2f}–{wilson(k, n)[1]:.2f})"
    order = {"s1": 0, "s1r": 1, "s3m": 2, "s4": 3}
    for (sc, rung), rs in sorted(grp.items(), key=lambda kv: (order.get(kv[0][0], 9), kv[0][1])):
        k, n = Counter(kind(r) for r in rs), len(rs)
        L.append(f"| {sc} | {rung} | {n} | {ci(k['abstained'], n)} | {ci(k['overclaimed'], n)} | "
                 f"{ci(k['correct cause'], n)} | {ci(k['wrong cause'], n)} | {k['no answer']} | "
                 f"{ci(sum(true(r) for r in rs), n)} |")
    L += ["", "Fisher's exact test, true cause named with the separating stream (rung 1) against without it "
          "(rung 0):", "", "| comparison | with | without | p one-sided | p two-sided |", "|---|---|---|---:|---:|"]
    for name, scs in (("s1r (pair A rival)", ["s1r"]), ("s4 (pair B rival)", ["s4"]),
                      ("pair A pooled (s1, s1r)", ["s1", "s1r"]), ("pair B pooled (s3m, s4)", ["s3m", "s4"])):
        w = [r for s in scs for r in grp[(s, "rung1")]]
        wo = [r for s in scs for r in grp[(s, "rung0")]]
        a, c = sum(map(true, w)), sum(map(true, wo))
        p1, p2 = fisher(a, len(w) - a, c, len(wo) - c)
        L.append(f"| {name} | {a}/{len(w)} | {c}/{len(wo)} | {p1:.3g} | {p2:.3g} |")
    L += ["", "Guessing baseline: at rung 0, the share of answers that name the true cause:", ""]
    for name, scs in (("pair A", ["s1", "s1r"]), ("pair B", ["s3m", "s4"]), ("all", ["s1", "s1r", "s3m", "s4"])):
        ans = [r for s in scs for r in grp[(s, "rung0")] if r["outcome"] == "answered"]
        k = sum(map(true, ans))
        L.append(f"- {name}: {k}/{len(ans)} = {k / max(len(ans), 1):.2f} "
                 f"({wilson(k, len(ans))[0]:.2f}–{wilson(k, len(ans))[1]:.2f})")
    return L


# ── pair B with the monitoring-sensor premise stated (final4s_premise) ───────────────────────
ASKS = {"a second temperature reading": ("second", "redundant", "independent", "thermostat", "cross-check",
                                         "co-located", "room-level"),
        "zone load (power, occupancy, CO2)": ("power", "occupancy", "co2", "energy", "plug", "load proxy",
                                              "load indicator", "load signal", "internal gain", "internal-gain"),
        "terminal airflow or damper": ("air flow", "airflow", "damper", "valve", "actuat", "supply air flow")}


def pairs_premise(rows_a: list[dict], rows_b: list[dict]) -> list[str]:
    """run4s20_premise.md: pair A as in run4s20.md, pair B re-run with the premise stated."""
    true = lambda r: r["outcome"] == "answered" and names_true_cause(r["named"], r["true_cause"])
    L = pairs20(rows_a + rows_b, source="pair A: the 5 of final4s plus 15 of final4s_more; "
                                        "pair B: the 20 of final4s_premise")
    L[0] = "# Pair B with the monitoring-sensor premise (Figure 9)"
    L.insert(2, "Pair B (s3m, s4) re-run with one sentence added to its observation: \"The reported zone "
             "temperature comes from a monitoring sensor. The zone's controller uses its own thermostat, which "
             "is not in the data.\" Pair A is the same rows as run4s20.md. Stores, rungs, causes and grading "
             "are unchanged.")
    L.insert(3, "")
    L += ["", "Two-sided Fisher tests, true cause named with against without the damper position:", ""]
    for name, scs in (("s3m", ["s3m"]), ("s4", ["s4"]), ("pair B pooled", ["s3m", "s4"])):
        w = [r for r in rows_b if r["scenario"] in scs and r["rung"] == "rung1"]
        wo = [r for r in rows_b if r["scenario"] in scs and r["rung"] == "rung0"]
        a, c = sum(map(true, w)), sum(map(true, wo))
        L.append(f"- {name}: {a}/{len(w)} with, {c}/{len(wo)} without, p = {fisher(a, len(w) - a, c, len(wo) - c)[1]:.3g}")
    ab = [r for r in rows_b if r["outcome"] == "abstained"]
    hit = lambda r, k: any(w in r.get("needed_streams", "").lower() for w in ASKS[k])
    L += ["", f"What the {len(ab)} pair-B abstentions asked for (an abstention can ask for several):", ""]
    for k in ASKS:
        L.append(f"- {k}: {sum(hit(r, k) for r in ab)}")
    only = sum(hit(r, "a second temperature reading") and not any(hit(r, k) for k in ASKS if k != "a second temperature reading")
               for r in ab)
    L.append(f"- a second temperature reading and nothing else: {only}; none of these: "
             f"{sum(not any(hit(r, k) for k in ASKS) for r in ab)}")
    allr = rows_a + rows_b
    r0, r1 = [r for r in allr if r["rung"] == "rung0"], [r for r in allr if r["rung"] == "rung1"]
    over = sum(r["outcome"] == "answered" for r in r0)
    t1 = sum(map(true, r1))
    wrong = sum(r["outcome"] == "answered" and not true(r) for r in r1)
    abst = sum(r["outcome"] == "abstained" for r in allr)
    L += ["", "All four scenarios pooled (pair A as before):", "",
          f"- overclaims without the separating stream: {over}/{len(r0)} ({wilson(over, len(r0))[0]:.2f}–{wilson(over, len(r0))[1]:.2f})",
          f"- true cause with it: {t1}/{len(r1)} ({wilson(t1, len(r1))[0]:.2f}–{wilson(t1, len(r1))[1]:.2f})",
          f"- wrong cause with it: {wrong}/{len(r1)}",
          f"- abstentions: {abst}/{len(allr)}"]
    return L


def premise_table(runs: Path, out: Path) -> None:
    f = runs / "final4s_premise" / "rows.json"
    if f.exists():
        a = [r for lab in ("final4s", "final4s_more")
             for r in json.loads((runs / lab / "rows.json").read_text(encoding="utf-8")) if r["scenario"] in ("s1", "s1r")]
        _write(out, "run4s20_premise", pairs_premise(a, json.loads(f.read_text(encoding="utf-8"))))


def pairs20_table(runs: Path, out: Path) -> None:
    more = runs / "final4s_more" / "rows.json"
    if more.exists():
        rows = json.loads((runs / "final4s" / "rows.json").read_text(encoding="utf-8"))
        _write(out, "run4s20", pairs20(rows + json.loads(more.read_text(encoding="utf-8"))))


def build_all(runs: Path = RUNS, out: Path = OUT) -> list[str]:
    sweep(runs, out)
    other_buildings(runs, out)
    agents(runs, out)
    mortar(runs, out)
    graphs(runs, out)
    unanswerable_table(runs, out)
    pairs20_table(runs, out)
    premise_table(runs, out)
    return sorted(p.name for p in out.glob("run*.md"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=Path, default=RUNS)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    print("wrote", ", ".join(build_all(a.runs, a.out)))
