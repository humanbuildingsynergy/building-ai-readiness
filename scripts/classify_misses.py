"""Classify every wrong answer of the reference model by stated rules (the miss analysis).

    python scripts/classify_misses.py      -> results/final/misses_reference.csv

Rules, in order: an HTTP error is infrastructure; no submit_answer is an agent error; an abstention
is question ambiguity when the question names a label several graph entities share, else an agent
error (the bank only asks about stored series); a wrong entity whose name (with a number, e.g.
RM1150) overlaps an accepted alias is grader strictness; a value put outside the 'answer' object is
an agent error, noted right or wrong; sign flips, unit slips and near misses are agent errors, named.
The three classes re-run after a correction to how their questions name locations
(bara.run.RERUN_CLASSES) are read from their re-run labels (final8c, final8c_rich), as in the
tables. Reads the deposited transcripts and BATS v1.0 (scripts/fetch_data.py --bats). The Mortar
rows (final5, final5sp, final5r) are carried over from the deposited file with their category only:
Mortar transcripts are not deposited, and the detail column would quote Mortar entity names.
"""
import collections, csv, glob, json, re, sys
from pathlib import Path
from rdflib import Graph, RDFS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import bank, BATS_DIR, RESULTS_DIR, canon
from bara.run import REF as MODEL, SWEEP
from bara.stores import bank_paths, restrict
from bara.tables import _first_classes, _rows

RUNS = RESULTS_DIR / "agent_runs"
OUT = RESULTS_DIR / "final" / "misses_reference.csv"

def blocks():
    g = bank_paths(SWEEP, "linked")[0]
    for prof in ("minimal", "comfort", "standard", "rich"):
        st = restrict(SWEEP, canon.PROFILES[prof], prof)
        yield f"final1_{prof}", SWEEP, g, st, None, "final8c_rich" if prof == "rich" else "_none"
        yield f"final8_{prof}", SWEEP, g, st, None, None
    for b in sorted(p.name for p in (BATS_DIR / "buildings").iterdir() if p.name != SWEEP):
        g, s = bank_paths(b, "linked")
        yield "final2", b, g, s, None, "final8c"
        yield "final8b", b, g, s, None, None
    g_pub, s_t = bank_paths(SWEEP, "kg.ttl")
    g_lin = bank_paths(SWEEP, "linked")[0]
    yield "final6_published", SWEEP, g_lin, s_t, None, None     # bank built on the linked graph
    yield "final6_linked", SWEEP, g_lin, s_t, None, None

def collisions(g_path):
    g = Graph().parse(str(g_path), format="turtle")
    by = collections.defaultdict(set)
    for s, o in g.subject_objects(RDFS.label):
        by[str(o)].add(s)
    return {l for l, ss in by.items() if len(ss) > 1 and len(l) > 3}

def transcript(label, building, row):
    # a row merged into a summary from a re-run block (final8c, final8c_rich) keeps its transcript in
    # that block's folder, so every final* label is searched; turns and seconds pin the one episode
    fs = glob.glob(str(RUNS / "final*" / MODEL / f"{building}__full__{row['instance']}__r{row['repeat']}_*.json"))
    eps = [json.loads(Path(f).read_text(encoding="utf-8")) for f in fs]
    match = [e for e in eps if e["turns"] == row["turns"] and abs(e["seconds"] - row["seconds"]) < 0.2]
    return (match or eps or [None])[0]

def classify(q, ep, row, coll):
    out = row["outcome"]
    if out == "error":
        h = [t for t in ep["transcript"] if t["role"] == "harness"] if ep else []
        return "infrastructure", (h[0]["error"][:60] if h else "error")
    if out == "no_answer":
        return "agent error", "no submit_answer (turn limit or stopped)"
    hit = next((l for l in coll if l in q["text"]), None)
    if out == "abstained":
        return ("question ambiguity", f"label '{hit}' names several entities") if hit else \
               ("agent error", "abstained although the store holds the data")
    qc = next(c for c, _ in bank.BANK if c.cid == q["class"])
    ans, truth = ep["answer"] if ep else None, q["gold"]
    if not isinstance(ans, dict):
        subs = [x["input"] for t in (ep or {}).get("transcript", []) if t["role"] == "assistant"
                for x in t["content"] if x["type"] == "tool_use" and x["name"] == "submit_answer"]
        top = subs[-1] if subs else {}
        v = top.get("value", top.get("entity"))
        if v is None:
            return "agent error", "no answer object in submit_answer"
        fake = {"class": q["class"], "gold": truth, "aliases": q.get("aliases", [])}
        shape = {"entity": v} if qc.answer_type == bank.E else {"value": v}
        if qc.answer_type == bank.B and isinstance(v, str):
            shape = {"value": v.strip().lower() == "true"}
        right = bank.grade(fake, shape) == 1.0
        return "agent error", f"answer outside the 'answer' object (value {'right' if right else 'wrong'})"
    if qc.answer_type == bank.E:
        n = lambda s: "".join(ch for ch in str(s).lower() if ch.isalnum())
        a, al = n(ans.get("entity")), {n(truth)} | {n(x) for x in q.get("aliases", [])}
        if hit:
            return "question ambiguity", f"label '{hit}' names several entities"
        # only for entity names with a number (RM1150 / VAVRM1150); category answers such as
        # occupied / unoccupied must not match by substring
        if a and any(ch.isdigit() for ch in a) and any(a in x or x in a for x in al if x):
            return "grader strictness", f"name '{ans.get('entity')}' overlaps an accepted alias"
        return "agent error", f"wrong entity '{ans.get('entity')}' (ground truth '{truth}')"
    got = ans.get("value")
    if qc.answer_type == bank.B:
        if not isinstance(got, bool) and str(got).strip().lower() in ("true", "false", "1", "0") and \
                (str(got).strip().lower() in ("true", "1")) == truth:
            return "grader strictness", f"right boolean as {type(got).__name__} {got!r}"
        return "agent error", f"wrong boolean {got!r} (ground truth {truth})"
    try:
        v = float(got)
    except (TypeError, ValueError):
        return "agent error", f"non-numeric value {got!r}"
    tol = max(qc.tol_abs, qc.tol_rel * abs(truth))
    if truth and abs(v + truth) <= tol:
        return "agent error", "sign flipped"
    for f, name in ((3600, "x3600 (W vs J)"), (1 / 3600, "/3600 (J vs W)"), (1000, "x1000"), (0.001, "/1000"), (24, "x24"), (1/24, "/24")):
        if truth and abs(v - truth * f) <= max(tol, 0.02 * abs(truth * f)):
            return "agent error", f"unit or scale slip, {name}"
    if abs(v - truth) <= 2 * tol:
        return "agent error", "near miss (within 2x tolerance)"
    if hit:
        return "question ambiguity", f"label '{hit}' names several entities"
    return "agent error", f"wrong value {v:g} (ground truth {truth:g})"

mortar_rows = ([r for r in csv.DictReader(OUT.open(encoding="utf-8")) if r["run"].startswith("final5")]
               if OUT.exists() else [])
rows_out = []
for label, b, g, s, zt, rerun in blocks():
    # rows as the tables assemble them: the re-run classes come from their re-run label (*rerun*)
    rows = _first_classes(RUNS, label, b, rerun) if rerun else _rows(RUNS, label, b)
    misses = [r for r in rows if r["score"] < 1]
    if not misses:
        continue
    qs = {q["question_id"]: q for q in bank.build_bank(g, s, n=3, seed=0, zone_types=zt)}
    coll = collisions(g)
    for r in misses:
        if r["instance"] not in qs:
            cat, why = "unresolved", "instance not rebuilt by the current bank"
        else:
            cat, why = classify(qs[r["instance"]], transcript(label, b, r), r, coll)
        rows_out.append({"run": label.split("_")[0], "label": label, "building": b, "class": r["question"],
                         "instance": r["instance"], "repeat": r["repeat"], "outcome": r["outcome"],
                         "category": cat, "detail": why})

rows_out += [dict(r, detail="") for r in mortar_rows]
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
    w.writeheader(); w.writerows(rows_out)
by = collections.Counter((r["run"], r["category"]) for r in rows_out)
for k, v in sorted(by.items()):
    print(k, v)
print("total", len(rows_out))
det = collections.Counter((r["category"], re.sub(r"'.*?'|\(ground truth.*|\d[\d.e+-]*", "…", r["detail"])) for r in rows_out)
for k, v in det.most_common(25):
    print(v, k)
