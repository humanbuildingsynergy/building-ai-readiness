"""The scripted reference agent: one fixed, archived protocol for every model under test.

The prompt, the tool interface and the grading are fixed, so run-to-run variance can be measured
and every model sees the same protocol. An episode gives the model one question, the building's Brick
graph and the instrumentation-restricted store, and three tools:

  query_graph    run a SPARQL query over the graph (resolve: entity -> point -> series id)
  run_python     run standard-library Python with GRAPH_TTL / CATALOG_CSV / VALUES_CSV set
                 (fetch + compute; the store holds only the streams the profile exposes)
  submit_answer  hand in the final answer as JSON, or abstain when the data cannot determine it

Protocol choices that make a run a measurement:
  - tool choice is always automatic (the model decides when to call a tool; one protocol for all
    models)
  - no fallback model: a response whose stop reason is "refusal" ends the episode with the outcome
    "refused" and is never sent to another model. The Ollama client (bara.agent_local) never reports
    one; the outcome is kept for clients that report refusals.
  - the ground truth is never passed to the model. run_python runs the agent's code in a separate
    interpreter (python -I -S) in a temporary folder, with a minimal environment (the three data
    paths, sandbox_env), so the project is not importable and the harness's environment is not
    visible. It is not a file-system sandbox: the code runs with the user's file permissions.
  - every request and response of an episode is archived as one JSON file under
    $DERIVED_DIR/agent_runs/<label>/<model>/ (the deposited runs are in results/agent_runs)

Sampling is not seeded, so run-to-run variance is measured by repeating episodes. The model id that
Ollama reports is stored with every episode.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from bara import DERIVED_DIR

_OUT = DERIVED_DIR / "agent_runs"      # new runs; the deposited runs are under results/agent_runs
MAX_TURNS = 25
MAX_TOOL_CHARS = 12_000      # a tool result longer than this is cut, and the cut is stated
PYTHON_TIMEOUT_S = 120

SYSTEM = """You answer one operational question about one building, using only its data.

You have the building's Brick metadata graph and a time-series store. The store is two CSV files:
CATALOG_CSV (timeseries_id, point_uri, point_class, unit, quantity_kind, building_id) and VALUES_CSV
(timeseries_id, timestamp, value; hourly). A point in the graph links to its series through
ref:hasExternalReference / ref:hasTimeseriesId. The store holds only the streams this building
exposes, so a point in the graph may have no series.

Work in three steps. Resolve the entities the question names to their series ids with query_graph.
Fetch and compute with run_python, which runs standard-library Python with the variables GRAPH_TTL,
CATALOG_CSV and VALUES_CSV already defined as file paths. Only the standard library is installed, and
each call is a fresh process, so nothing carries over between calls. Do the arithmetic in code, not
in your head.
Then call submit_answer once, with the answer in the JSON shape the question gives.

If the available streams cannot determine the answer, do not guess. Call submit_answer with
abstain set to true and name the streams you would need."""

TOOLS = [
    {"name": "query_graph",
     "description": "Run a SPARQL SELECT query over the building's Brick graph. Returns up to 200 "
                    "rows as JSON. Prefixes brick:, ref:, rdfs: and rdf: are predefined.",
     "input_schema": {"type": "object", "properties": {"sparql": {"type": "string"}},
                      "required": ["sparql"]}},
    {"name": "run_python",
     "description": "Run standard-library Python 3 in an isolated process. GRAPH_TTL, CATALOG_CSV "
                    "and VALUES_CSV are predefined file paths. Print what you need; stdout and "
                    "stderr are returned.",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}},
                      "required": ["code"]}},
    {"name": "submit_answer",
     "description": "Hand in the final answer. Call exactly once, as the last step.",
     "input_schema": {"type": "object", "properties": {
         "answer": {"type": "object", "description": "The answer in the JSON shape the question gives."},
         "abstain": {"type": "boolean",
                     "description": "True if the available data cannot determine the answer."},
         "needed_streams": {"type": "string",
                            "description": "When abstaining: the streams that would be needed."}},
         "required": ["abstain"]}},
]

_PREFIXES = ("PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
             "PREFIX ref: <https://brickschema.org/schema/Brick/ref#>\n"
             "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
             "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


@dataclass
class Episode:
    question_id: str
    model: str
    reported_model: str = ""
    outcome: str = "no_answer"   # answered | abstained | refused | no_answer | error
    answer: dict | None = None
    needed_streams: str = ""
    turns: int = 0
    tool_calls: int = 0
    input_tokens: int = 0            # prompt tokens, summed over the turns
    output_tokens: int = 0
    seconds: float = 0.0
    prompt_tokens_per_turn: list = field(default_factory=list)   # shows no turn hit the context limit
    transcript: list = field(default_factory=list)


def sandbox_env(tmp: str, graph: Path, catalog: Path, values: Path) -> dict[str, str]:
    """The whole environment of a run_python process: the three data paths, the interpreter's own
    folder as PATH, and on Windows SYSTEMROOT (which the C runtime needs). Nothing is inherited, so
    the agent's code cannot read the harness's environment (user and machine names, session tokens)."""
    env = {"GRAPH_TTL": str(graph), "CATALOG_CSV": str(catalog), "VALUES_CSV": str(values),
           "PATH": str(Path(sys.executable).parent), "TEMP": tmp, "TMP": tmp, "TMPDIR": tmp}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return env


class Workspace:
    """The graph and the restricted store of one episode, and the two data tools over them."""

    def __init__(self, kg_ttl: Path, store_dir: Path):
        self.kg_ttl, self.store_dir = Path(kg_ttl), Path(store_dir)
        self._graph = None

    def query_graph(self, sparql: str) -> str:
        if self._graph is None:
            from rdflib import Graph
            self._graph = Graph().parse(str(self.kg_ttl), format="turtle")
        rows = [[str(v) if v is not None else None for v in row]
                for row in itertools.islice(self._graph.query(_PREFIXES + sparql), 200)]
        return json.dumps(rows)

    def run_python(self, code: str) -> str:
        # BuildStream stores name the files catalog.csv / values.csv; published BATS uses
        # points.csv / timeseries.csv (same columns). The variable names the prompt gives stay.
        legacy = (self.store_dir / "catalog.csv").exists()
        catalog = self.store_dir / ("catalog.csv" if legacy else "points.csv")
        values = self.store_dir / ("values.csv" if legacy else "timeseries.csv")
        header = (f"GRAPH_TTL = {str(self.kg_ttl)!r}\n"
                  f"CATALOG_CSV = {str(catalog)!r}\n"
                  f"VALUES_CSV = {str(values)!r}\n")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "step.py"
            script.write_text(header + code, encoding="utf-8")
            env = sandbox_env(tmp, self.kg_ttl, catalog, values)
            try:  # -I -S: isolated, and no site-packages: the standard library is all there is
                out = subprocess.run([sys.executable, "-I", "-S", str(script)], cwd=tmp, text=True,
                                     capture_output=True, timeout=PYTHON_TIMEOUT_S, env=env)
            except subprocess.TimeoutExpired:
                return f"Error: the code ran longer than {PYTHON_TIMEOUT_S} s and was stopped."
        return (out.stdout + ("\n[stderr]\n" + out.stderr if out.stderr else "")).strip() or "(no output)"


def _clip(text: str) -> str:
    if len(text) <= MAX_TOOL_CHARS:
        return text
    return text[:MAX_TOOL_CHARS] + f"\n[cut: {len(text) - MAX_TOOL_CHARS} more characters not shown]"


def _request(model: str, messages: list) -> dict:
    return {"model": model, "max_tokens": 16000, "system": SYSTEM, "tools": TOOLS, "messages": messages}


def run_episode(client, model: str, question_id: str, question: str, schema: str,
                workspace: Workspace, *, archive: bool = True, run_label: str = "") -> Episode:
    """One question, one model, one restricted store. *client* is a bara.agent_local.OllamaClient."""
    ep = Episode(question_id, model)
    messages = [{"role": "user", "content": f"{question}\n\nAnswer shape: {schema}"}]
    start = time.time()
    try:
        for _ in range(MAX_TURNS):
            response = client.messages.create(**_request(model, messages))
            ep.turns += 1
            ep.reported_model = response.model
            ep.input_tokens += response.usage.input_tokens
            ep.prompt_tokens_per_turn.append(response.usage.input_tokens)
            ep.output_tokens += response.usage.output_tokens
            content = [b.model_dump() for b in response.content]
            ep.transcript.append({"role": "assistant", "stop_reason": response.stop_reason,
                                  "content": content})
            if response.stop_reason == "refusal":
                ep.outcome = "refused"
                break
            calls = [b for b in response.content if b.type == "tool_use"]
            if not calls:
                break                                   # ended its turn without submitting
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in calls:
                ep.tool_calls += 1
                if call.name == "submit_answer":
                    ep.outcome = "abstained" if call.input.get("abstain") else "answered"
                    ep.answer = call.input.get("answer")
                    ep.needed_streams = call.input.get("needed_streams", "")
                    results.append({"type": "tool_result", "tool_use_id": call.id,
                                    "content": "received"})
                    continue
                try:
                    tool = getattr(workspace, call.name)
                    text, failed = _clip(tool(**call.input)), False
                except Exception as exc:                # a bad query is the model's to repair
                    text, failed = f"Error: {type(exc).__name__}: {exc}", True
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": text,
                                "is_error": failed})
            ep.transcript.append({"role": "user", "content": results})
            if ep.outcome in ("answered", "abstained"):
                break
            messages.append({"role": "user", "content": results})
    except Exception as exc:                            # failed request: keep the turns so far
        ep.outcome = "error"
        ep.transcript.append({"role": "harness", "error": f"{type(exc).__name__}: {exc}"})
    ep.seconds = round(time.time() - start, 1)
    if archive:
        # a ":" in a model tag ("gemma2:9b") is not allowed in a Windows folder name
        out = _OUT / (run_label or "unlabelled") / model.replace(":", "_")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{question_id}_{int(start)}.json").write_text(
            json.dumps(asdict(ep), indent=1, default=str), encoding="utf-8")
    return ep
