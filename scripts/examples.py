"""Examples for readers, from the archived sweep episodes (BATS only; no agent runs).

    python scripts/examples.py      # -> examples/*.md, examples/question_bank_examples.csv

example_episode.md          one episode of the reference agent, every tool call and (cut) result
worked_examples.md          one instance per kind of question, with the agent's answer per repeat
question_bank_examples.*    one BATS instance of every class of the bank (the templates of the
                            classes that do not instantiate on the sweep building)

The questions are rebuilt with the sweep's bank (seed 0, 3 instances per class) on the sweep
building's store at the rich profile; the episodes are the deposited ones of final1_rich and
final8_rich, matched to their summary rows by id and duration.
"""
from __future__ import annotations

import ast
import csv
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bara import RESULTS_DIR, bank, canon  # noqa: E402
from bara.stores import bank_paths, restrict  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "examples"
SWEEP, REF = "large_office__2a_tampa", "qwen3.8-27b-128k"
RUNS = RESULTS_DIR / "agent_runs"
EPISODE = ("final1_rich", "t_summary_1#1", 1)            # a zone's daily mean: 5 turns, graph + Python, correct
# classes whose truths vary across instances, so that no fixed answer passes them all
WORKED = [("an L1 number", "t_status_1"), ("an L2 difference", "t_comparison_2"),
          ("a yes/no verification", "t_verification_2"), ("an entity answer (lighting)", "l_comparison_2"),
          ("a class that spans two KG hops", "t_comparison_2hop"), ("an energy number", "e_summary_1"),
          ("an equipment number", "q_summary_1"), ("an occupancy number", "o_status_1"), ("an L3 class", None)]
MISS = ("a typical miss", "t_verification_1#2")
CUT = 6                                                   # lines kept of each tool result


def classes() -> dict:
    return {q.cid: q for q, _ in bank.BANK}


def grader(qc) -> str:
    if qc.answer_type == bank.E:
        return "entity: the name, or any name the graph ties to the entity (case and punctuation ignored)"
    if qc.answer_type == bank.B:
        return "yes/no: exact"
    tol = []
    if qc.tol_abs:
        tol.append(f"±{qc.tol_abs:g}")
    if qc.tol_rel:
        tol.append(f"±{qc.tol_rel * 100:g}%")
    return "number within " + (" or ".join(tol) + " (the larger)" if len(tol) > 1 else tol[0] if tol else "exact")


def rich_bank() -> dict:
    g = bank_paths(SWEEP, "linked")[0]
    st = restrict(SWEEP, canon.PROFILES["rich"], "rich")
    return {q["question_id"]: q for q in bank.build_bank(g, st, n=3, seed=0)}


def episodes(label: str) -> tuple[list, dict]:
    s = json.loads((RUNS / label / REF / f"summary_{SWEEP}.json").read_text(encoding="utf-8"))
    tr = {}
    for f in (RUNS / label / REF).glob("*__*.json"):
        if not f.name.startswith("summary_"):
            e = json.loads(f.read_text(encoding="utf-8"))
            tr.setdefault(e["question_id"], []).append(e)
    return s["rows"], tr


def find(inst: str, rep: int):
    for label in ("final1_rich", "final8_rich", "final8c_rich"):
        rows, tr = episodes(label)
        r = next((r for r in rows if r["instance"] == inst and r["repeat"] == rep), None)
        if r:
            src = r.get("merged_from", label)
            if src != label:
                rows, tr = episodes(src)
            e = next(e for e in tr[f"{SWEEP}__full__{inst}__r{rep}"] if abs(e["seconds"] - r["seconds"]) < 0.2)
            return r, e
    return None, None


def cut(text: str) -> str:
    lines = str(text).splitlines()
    return "\n".join(lines[:CUT] + ([f"[… {len(lines) - CUT} more lines]"] if len(lines) > CUT else []))


def example_episode(qs: dict) -> list[str]:
    label, inst, rep = EPISODE
    q, qc = qs[inst], classes()[inst.split("#")[0]]
    r, e = find(inst, rep)
    L = ["# One episode of the reference agent", "",
         f"`{SWEEP}`, rich profile, run `{label}`, instance `{inst}`, repeat {rep}, {REF}: {e['turns']} turns, "
         f"{e['tool_calls']} tool calls, {e['seconds']:.0f} s.", "",
         f"**Question** ({qc.cid}: {qc.domain} / {qc.intent}, L{qc.level}; requires {', '.join(qc.requires)}):", "",
         f"> {q['text']}", ">", f"> Answer shape: `{q['schema']}`", ""]
    results = {}
    for t in e["transcript"]:
        if t["role"] == "user" and isinstance(t["content"], list):
            for c in t["content"]:
                if c.get("type") == "tool_result":
                    results[c["tool_use_id"]] = c["content"]
    n = 0
    for t in e["transcript"]:
        if t["role"] != "assistant":
            continue
        for c in t["content"]:
            if c.get("type") != "tool_use":
                continue
            n += 1
            if c["name"] == "query_graph":
                L += [f"**{n}. query_graph**", "", "```sparql", c["input"].get("sparql", "").strip(), "```"]
            elif c["name"] == "run_python":
                L += [f"**{n}. run_python**", "", "```python", c["input"].get("code", "").strip(), "```"]
            else:
                L += [f"**{n}. submit_answer**", "", "```json", json.dumps(c["input"]), "```"]
                continue
            L += ["", "Result (first lines):", "", "```", cut(results.get(c["id"], "")), "```", ""]
    L += ["", f"**Submitted** {json.dumps(e['answer'])}; **ground truth** {q['gold']}; "
          f"**grader** {grader(qc)}; **grade** {bank.grade(q, e['answer']):.0f}."]
    return L


def worked(qs: dict) -> list[str]:
    cl = classes()
    rows = episodes("final1_rich")[0] + episodes("final8_rich")[0]
    L = ["# Worked examples of the question bank", "",
         f"`{SWEEP}`, rich profile (the sweep's bank, seed 0), {REF}, 3 repeats each. The instance of each",
         "class is the first one the agent answered correctly in every repeat; the last is a typical miss.", ""]
    picks, no_l3 = [], []
    for kind, cid in WORKED:
        if cid is None:
            l3 = [c for c in cl.values() if c.level == 3 and any(q["class"] == c.cid for q in qs.values())]
            if not l3:
                no_l3 = [f"## {kind}", "", "No L3 class instantiates on the published BATS building (it has no "
                         "ActC, ActP, SAT, SpC, Run, Load, CO2 or OAF series).", ""]
                continue
            cid = l3[0].cid
        ok = [k for k in sorted(qs) if k.split("#")[0] == cid
              and (rr := [r for r in rows if r["instance"] == k]) and all(r["score"] == 1 for r in rr)]
        # a number far enough from zero that the example cannot pass for a guess
        good = [k for k in ok if not isinstance(qs[k]["gold"], float) or abs(qs[k]["gold"]) >= 0.1] or ok
        if good:
            picks.append((kind, good[0]))
    picks.append(MISS)
    for kind, inst in picks:
        q, qc = qs[inst], cl[inst.split("#")[0]]
        L += [f"## {kind}: `{qc.cid}` ({qc.domain} / {qc.intent}, L{qc.level}{', two hops' if qc.hops == 2 else ''})", "",
              f"> {q['text']}", ">", f"> Answer shape: `{q['schema']}`", "",
              f"- Requires: {', '.join(qc.requires)}. Ground truth: `{q['gold']}`. Grader: {grader(qc)}.",
              "- Truths of the class's three instances: " + ", ".join(
                  f"`{qs[k]['gold']}`" for k in sorted(qs) if k.split("#")[0] == qc.cid) + "."]
        for rep in range(3):
            r, e = find(inst, rep)
            if r is None:
                continue
            ans = json.dumps(e["answer"]) if e and e["answer"] is not None else "—"
            L.append(f"- Repeat {rep}: {r['outcome']}, answer {ans}, grade {r['score']:.0f}.")
        L.append("")
    return L + no_l3


_PLACEHOLDERS = {"d": "date", "d1": "first date", "d2": "second date", "h": "hour", "m": "month",
                 "b.year": "year"}


def template_text(fn) -> str:
    """The question a template asks, as a plain-text pattern: the text of its returned tuple's first
    element, with each inserted value shown as a placeholder ({zone A}, {date}, {hour})."""
    src = textwrap.dedent(inspect.getsource(fn))
    kind = "zone" if "b.zone_types" in src else "equipment" if "equipment_with" in src else "unit"
    letters = {"a": " A", "c": " B"}

    def placeholder(expr) -> str:
        if (isinstance(expr, ast.Call) and ast.unparse(expr.func) == "b.named"
                and isinstance(expr.args[0], ast.Name)):
            return "{" + kind + letters.get(expr.args[0].id, "") + "}"
        if isinstance(expr, ast.Name) and isinstance(getattr(bank, expr.id, None), str):
            return getattr(bank, expr.id)                      # a stated rule, e.g. LIGHTING_RULE
        name = ast.unparse(expr)
        return "{" + _PLACEHOLDERS.get(name, name) + "}"

    def text(node) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.JoinedStr):
            return "".join(text(v) for v in node.values)
        if isinstance(node, ast.FormattedValue):
            return placeholder(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return text(node.left) + text(node.right)
        return "{" + ast.unparse(node) + "}"

    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Tuple) and node.elts and isinstance(node.elts[0], (ast.JoinedStr, ast.Constant, ast.BinOp)):
            out = " ".join(text(node.elts[0]).split())
            if "?" in out or "Answer" in out or "What" in out or "Did" in out or "Which" in out:
                return re.sub(r"\b(zone|unit|equipment) \{\1", r"{\1", out)    # "zone {zone A}" -> "{zone A}"
    return "(template in bara/bank.py: " + fn.__name__ + ")"


def full_set(qs: dict) -> list[dict]:
    first = {}
    for k in sorted(qs, key=lambda k: (k.split("#")[0], int(k.split("#")[1]))):
        first.setdefault(qs[k]["class"], qs[k])
    out = []
    for qc, template in bank.BANK:
        base = {"class": qc.cid, "domain": qc.domain, "intent": qc.intent, "level": qc.level,
                "requires": "+".join(qc.requires), "hops": qc.hops, "answer_type": qc.answer_type,
                "grader": grader(qc)}
        q = first.get(qc.cid)
        if q:
            out.append({**base, "instantiates_on_bats": "yes", "question": q["text"], "ground_truth": q["gold"]})
        else:
            out.append({**base, "instantiates_on_bats": "no (template shown)",
                        "question": template_text(template), "ground_truth": ""})
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    qs = rich_bank()
    (OUT / "example_episode.md").write_text("\n".join(example_episode(qs)) + "\n", encoding="utf-8", newline="\n")
    (OUT / "worked_examples.md").write_text("\n".join(worked(qs)) + "\n", encoding="utf-8", newline="\n")
    rows = full_set(qs)
    with (OUT / "question_bank_examples.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    L = ["# The question bank: one BATS instance of every class", "",
         f"`{SWEEP}`, rich profile, the sweep's bank (seed 0). {sum(r['instantiates_on_bats'] == 'yes' for r in rows)} "
         f"of {len(rows)} classes instantiate there; the others show their template.", "",
         "| class | cell, level | requires | answer | question as posed | ground truth | grader |",
         "|---|---|---|---|---|---|---|"]
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    L += [f"| {r['class']} | {r['domain']} / {r['intent']}, L{r['level']} | {r['requires']} | {r['answer_type']} | "
          f"{esc(r['question'])}{'' if r['instantiates_on_bats'] == 'yes' else ' *(template; not on BATS)*'} | "
          f"{esc(r['ground_truth'])} | {r['grader']} |" for r in rows]
    (OUT / "question_bank_examples.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: example_episode.md, worked_examples.md, question_bank_examples.csv/.md ({len(rows)} classes)")


if __name__ == "__main__":
    main()
