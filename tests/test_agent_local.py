"""The Ollama adapter: request and response translation (no server needed)."""
from types import SimpleNamespace as NS

from bara.agent import TOOLS
from bara.agent_local import from_chat_response, to_chat_messages, to_chat_tools


def test_history_round_trip():
    history = [
        {"role": "user", "content": "Q?"},
        {"role": "assistant", "content": [NS(type="text", text="looking"),
                                          NS(type="tool_use", id="a", name="run_python",
                                             input={"code": "print(1)"})]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": "1"}]},
    ]
    out = to_chat_messages("SYS", history)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool"]
    assert out[2]["tool_calls"][0]["function"] == {"name": "run_python",
                                                    "arguments": '{"code": "print(1)"}'}
    assert out[3] == {"role": "tool", "tool_call_id": "a", "content": "1"}


def test_tools_and_response():
    assert [t["function"]["name"] for t in to_chat_tools(TOOLS)] == [
        "query_graph", "run_python", "submit_answer"]
    resp = from_chat_response({"model": "m", "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                                 "choices": [{"message": {"content": "", "tool_calls": [
                                     {"id": "x", "function": {"name": "submit_answer",
                                                              "arguments": '{"abstain": true}'}}]}}]})
    assert resp.stop_reason == "tool_use" and resp.content[0].input == {"abstain": True}
    assert resp.usage.input_tokens == 7 and resp.content[0].model_dump()["name"] == "submit_answer"
    bad = from_chat_response({"choices": [{"message": {"content": "hi", "tool_calls": [
        {"function": {"name": "run_python", "arguments": "{not json"}}]}}]})
    assert bad.content[1].input == {} and bad.content[0].text == "hi"
