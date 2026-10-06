"""Local open-weight models under the agent protocol, through Ollama.

``OllamaClient`` is the client ``bara.agent.run_episode`` calls: it takes the episode's request
(system prompt, tools, message history), sends it to Ollama's chat endpoint, and hands back a
response in the shape run_episode reads. Prompt, tools, turn limit and grader are therefore the same
for every model; only the model behind the client changes. Pin a model by its Ollama digest
(``ollama show <model>``).
"""
from __future__ import annotations

import json
import urllib.request
from types import SimpleNamespace as NS

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"


def to_chat_messages(system: str, messages: list) -> list[dict]:
    """The episode history (content blocks) -> chat-endpoint messages (tool calls and results included)."""
    out = [{"role": "system", "content": system}]
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
        elif m["role"] == "assistant":
            text = "".join(b.text for b in m["content"] if b.type == "text")
            calls = [{"id": b.id, "type": "function",
                      "function": {"name": b.name, "arguments": json.dumps(b.input)}}
                     for b in m["content"] if b.type == "tool_use"]
            out.append({"role": "assistant", "content": text, **({"tool_calls": calls} if calls else {})})
        else:  # a user turn made of tool results
            out += [{"role": "tool", "tool_call_id": r["tool_use_id"], "content": r["content"]}
                    for r in m["content"]]
    return out


def to_chat_tools(tools: list) -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in tools]


def _block(**kw):
    return NS(model_dump=lambda: dict(kw), **kw)


def from_chat_response(data: dict):
    """A chat-endpoint completion -> the response shape run_episode reads."""
    msg = data["choices"][0]["message"]
    blocks = [_block(type="text", text=msg["content"])] if msg.get("content") else []
    for call in msg.get("tool_calls") or []:
        try:
            args = json.loads(call["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}                         # malformed arguments: the tool call fails, visibly
        blocks.append(_block(type="tool_use", id=call.get("id") or f"call_{len(blocks)}",
                             name=call["function"]["name"], input=args))
    usage = data.get("usage") or {}
    return NS(model=data.get("model", ""), content=blocks,
              stop_reason="tool_use" if msg.get("tool_calls") else "end_turn",
              usage=NS(input_tokens=usage.get("prompt_tokens", 0),
                       output_tokens=usage.get("completion_tokens", 0)))


class OllamaClient:
    def __init__(self, url: str = OLLAMA_URL, timeout_s: int = 900):
        self.url, self.timeout_s = url, timeout_s
        self.messages = NS(create=self._create)

    def _create(self, *, model, system, tools, messages, max_tokens, **_dropped):
        body = {"model": model, "messages": to_chat_messages(system, messages),
                "tools": to_chat_tools(tools), "max_tokens": max_tokens}
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return from_chat_response(json.load(resp))
