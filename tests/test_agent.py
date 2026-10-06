"""The agent harness, driven by a scripted fake model (no API calls)."""
from types import SimpleNamespace as NS

from bara.agent import Workspace, run_episode

TTL = """
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix : <urn:t#> .
:z a brick:HVAC_Zone ; brick:hasPoint :t .
:t a brick:Zone_Air_Temperature_Sensor ; ref:hasExternalReference [ ref:hasTimeseriesId "ts1" ] .
"""


def _block(**kw):
    return NS(model_dump=lambda: dict(kw), **kw)


class FakeClient:
    """Replays a list of assistant turns; records the requests it was sent."""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []
        self.messages = NS(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        stop, blocks = self.turns.pop(0)
        return NS(model="fake-1", stop_reason=stop, content=blocks,
                  usage=NS(input_tokens=10, output_tokens=5))


def _workspace(tmp_path):
    (tmp_path / "kg.ttl").write_text(TTL, encoding="utf-8")
    (tmp_path / "catalog.csv").write_text("timeseries_id,point_uri,point_class\nts1,urn:t#t,X\n")
    (tmp_path / "values.csv").write_text("timeseries_id,timestamp,value\nts1,2004-01-01T01,21.5\n")
    return Workspace(tmp_path / "kg.ttl", tmp_path)


def test_resolve_fetch_compute_submit(tmp_path):
    code = "import csv\nprint([r['value'] for r in csv.DictReader(open(VALUES_CSV))])"
    client = FakeClient([
        ("tool_use", [_block(type="tool_use", id="a", name="query_graph", input={
            "sparql": "SELECT ?id WHERE { ?p ref:hasExternalReference/ref:hasTimeseriesId ?id }"})]),
        ("tool_use", [_block(type="tool_use", id="b", name="run_python", input={"code": code})]),
        ("tool_use", [_block(type="tool_use", id="c", name="submit_answer",
                             input={"abstain": False, "answer": {"value": 21.5}})]),
    ])
    ep = run_episode(client, "fake", "q1", "Temperature?", '{"value": <number>}',
                     _workspace(tmp_path), archive=False)
    assert (ep.outcome, ep.answer, ep.turns, ep.tool_calls) == ("answered", {"value": 21.5}, 3, 3)
    assert ep.reported_model == "fake-1" and ep.input_tokens == 30
    assert ep.prompt_tokens_per_turn == [10, 10, 10]
    results = [m["content"][0]["content"] for m in ep.transcript if m["role"] == "user"]
    assert "ts1" in results[0] and "21.5" in results[1]
    assert all("tool_choice" not in r and "fallbacks" not in r for r in client.requests)


def test_abstention_refusal_and_tool_error(tmp_path):
    ws = _workspace(tmp_path)
    abstain = FakeClient([("tool_use", [_block(type="tool_use", id="a", name="submit_answer", input={
        "abstain": True, "needed_streams": "commanded setpoint"})])])
    ep = run_episode(abstain, "fake", "q", "Why?", "{}", ws, archive=False)
    assert (ep.outcome, ep.needed_streams) == ("abstained", "commanded setpoint")

    refuse = FakeClient([("refusal", [])])
    assert run_episode(refuse, "fake", "q", "Why?", "{}", ws, archive=False).outcome == "refused"

    broken = FakeClient([
        ("tool_use", [_block(type="tool_use", id="a", name="query_graph", input={"sparql": "nope"})]),
        ("end_turn", [_block(type="text", text="I give up")]),
    ])
    ep = run_episode(broken, "fake", "q", "Why?", "{}", ws, archive=False)
    assert ep.outcome == "no_answer" and ep.transcript[1]["content"][0]["is_error"] is True


def test_run_python_cannot_import_the_project(tmp_path):
    ws = _workspace(tmp_path)
    assert "ModuleNotFoundError" in ws.run_python("import bara")
    assert "ModuleNotFoundError" in ws.run_python("import rdflib")     # no site-packages either
    assert ws.run_python("import csv, statistics; print(statistics.mean([1, 3]))") == "2"


def test_run_python_sees_only_a_minimal_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("BARA_TEST_SECRET_TOKEN", "do-not-leak")
    ws = _workspace(tmp_path)
    keys = set(ws.run_python("import os; print(' '.join(sorted(os.environ)))").split())
    allowed = {"GRAPH_TTL", "CATALOG_CSV", "VALUES_CSV", "PATH", "TEMP", "TMP", "TMPDIR", "SYSTEMROOT"}
    assert {"GRAPH_TTL", "CATALOG_CSV", "VALUES_CSV", "PATH"} <= keys
    OS_ADDED = {"COMSPEC", "PATHEXT", "WINDIR",                 # Windows
                "__CF_USER_TEXT_ENCODING", "LC_CTYPE"}          # macOS; LC_CTYPE from PEP 538 locale coercion
    assert keys - allowed <= OS_ADDED                            # at most what the OS adds itself
    assert "do-not-leak" not in ws.run_python("import os; print(os.environ)")
    assert ws.run_python("import os; print(os.environ['VALUES_CSV'])") == str(tmp_path / "values.csv")
