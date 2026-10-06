"""The largest single-turn prompt per reported run and per model, against the model's context window.

    python scripts/prompt_sizes.py        # -> results/final/prompt_sizes.md

Only the episodes the tables use count: each summary row (or rows.json row) is matched to its
transcript by episode id and duration. prompt_tokens_per_turn is the prompt size Ollama reports for
each request. The Mortar transcripts (final5, final5sp, final5r) are not in the public deposit: when
none of a run's transcripts are in its folder, the run's row is carried over from the existing
output file.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "agent_runs"
OUT = ROOT / "results" / "final" / "prompt_sizes.md"
WINDOW = {"qwen2.5-32b-32k": 32768, "gemma2_9b": 8192}          # the others: 131072
LABELS = ["final1_minimal", "final1_comfort", "final1_standard", "final1_rich", "final8_minimal",
          "final8_comfort", "final8_standard", "final8_rich", "final8c_rich", "final8c", "final2", "final8b",
          "final3", "final6_published", "final6_linked", "final5", "final5sp", "final5r",
          "final4s", "final4s_more", "final4s_premise", "final9"]


def transcripts(mdir: Path) -> dict:
    out = {}
    for f in mdir.glob("*__*.json"):
        if not f.name.startswith("summary_"):
            e = json.loads(f.read_text(encoding="utf-8"))
            out.setdefault(e["question_id"], []).append(e)
    return out


def matched(label: str, mdir: Path):
    """(rows, list of matched transcripts) of one run folder."""
    tr = transcripts(mdir)
    pick = lambda qid, sec: next((e for e in tr.get(qid, []) if abs(e["seconds"] - sec) < 0.2), None)
    rows_file = RUNS / label / "rows.json"
    if rows_file.exists():
        rows = json.loads(rows_file.read_text(encoding="utf-8"))
        eps = []
        for r in rows:
            if label == "final9":
                qid = f"large_office__2a_tampa__{r['profile']}__{r['instance']}__r{r['repeat']}"
            else:
                qid = next((q for q in tr if q.endswith(f"__{r['scenario']}#{r['rung']}__r{r['repeat']}")), "")
            eps.append(pick(qid, r["seconds"]))
        return rows, eps
    rows, eps = [], []
    for s in mdir.glob("summary_*.json"):
        b = s.stem[8:]
        for r in json.loads(s.read_text(encoding="utf-8"))["rows"]:
            if r.get("merged_from"):
                continue                       # counted under the label it was run in
            rows.append(r)
            eps.append(pick(f"{b}__full__{r['instance']}__r{r['repeat']}", r["seconds"]))
    return rows, eps


def deposited() -> dict:
    """(run, model) -> the cells of its row in the existing output file."""
    if not OUT.exists():
        return {}
    out = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] in LABELS:
            out[(cells[0], cells[1])] = cells
    return out


def main() -> None:
    L = ["# Largest single-turn prompt per run and per model", "",
         "Prompt tokens as Ollama reports them for each request, over the episodes the tables use.", "",
         "| run | model | episodes | covered | largest prompt | window | at or over the window | episode |",
         "|---|---|---:|---:|---:|---:|---:|---|"]
    per_model = {}
    kept = deposited()
    for label in LABELS:
        d = RUNS / label
        if not d.exists():
            continue
        for mdir in sorted(p for p in d.iterdir() if p.is_dir()):
            rows, eps = matched(label, mdir)
            win = WINDOW.get(mdir.name, 131072)
            got = [e for e in eps if e is not None]
            if rows and not got and (label, mdir.name) in kept:
                # transcripts not deposited: the row as computed when they were present
                cells = kept[(label, mdir.name)]
                n_got, big, over, ep_id = int(cells[3]), int(cells[4]), int(cells[6]), cells[7]
            else:
                mx = max(got, key=lambda e: max(e.get("prompt_tokens_per_turn") or [0]), default=None)
                big = max(mx.get("prompt_tokens_per_turn") or [0]) if mx else 0
                over = sum(max(e.get("prompt_tokens_per_turn") or [0]) >= win for e in got)
                n_got, ep_id = len(got), mx["question_id"] if mx and big else "—"
            L.append(f"| {label} | {mdir.name} | {len(rows)} | {n_got} | {big} | {win} | {over} | {ep_id} |")
            m = per_model.setdefault(mdir.name, [0, "", 0, 0, win])
            if big > m[0]:
                m[0], m[1] = big, f"{label} {ep_id}"
            m[2] += over
            m[3] += n_got
    L += ["", "## Per model", "", "| model | largest prompt | window | episodes at or over the window | episodes | episode |",
          "|---|---:|---:|---:|---:|---|"]
    L += [f"| {m} | {b} | {w} | {o} | {n} | {e or '—'} |" for m, (b, e, o, n, w) in per_model.items()]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
