"""Market-steal additions (2026-11-18): bounded conversation memory,
trace enrichment, workflow input validation.

Compared products treat these as baseline: agent SDKs window conversation
state without orphaning tool results; tracing records per-tool latency and
error text; workflows reject bad inputs before paying for downstream calls.
"""

from __future__ import annotations

import json

from skills_supervisor.a2a import A2AClient
from skills_supervisor.mcp_registry import McpRegistry
from skills_supervisor.supervisor import SupervisorChatAgent
from skills_supervisor.workflows import (
    MAX_WORKFLOW_CHARS,
    screen_candidate,
    talent_brief,
)


def _final(text):
    def step(messages, tools=None):
        return {"content": text, "tool_calls": [], "raw_tool_calls": []}

    return step


def _tool_call(name, arguments, call_id="t1"):
    def step(messages, tools=None):
        return {
            "content": None,
            "tool_calls": [{"id": call_id, "name": name, "arguments": arguments}],
            "raw_tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        }

    return step


def make_supervisor(script, **kwargs):
    def chat(messages, tools=None):
        return script.pop(0)(messages)

    transport = lambda method, url, payload: {
        "status": "completed",
        "artifact": {"skills": [{"canonical_name": "Python"}]},
    }
    skills_client = A2AClient("http://a2a", transport=transport)
    registry = type("R", (), {"find_by_skill": staticmethod(lambda s: [])})()
    return SupervisorChatAgent(
        chat, skills_client, registry, McpRegistry(persistence_path=None), **kwargs
    )


def _assert_no_orphan_tools(messages):
    seen_call = False
    for msg in messages[1:]:  # skip system
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            seen_call = True
        elif msg["role"] == "assistant":
            seen_call = False
        elif msg["role"] == "tool":
            assert seen_call, "orphaned tool message without its parent tool_calls"


# ── bounded conversation memory ─────────────────────────────────────────────
class TestBoundedMemory:
    def test_long_conversation_is_trimmed_with_system_pinned(self) -> None:
        script = [_final(f"answer {i}") for i in range(40)]
        agent = make_supervisor(script, max_messages=10)
        for i in range(40):
            out = agent.chat(f"question {i}")
            assert out["reply"] == f"answer {i}"
            assert agent.messages[0]["role"] == "system"
            assert len(agent.messages) <= 11  # system + max_messages
            _assert_no_orphan_tools(agent.messages)

    def test_trimming_never_orphans_tool_results(self) -> None:
        script = []
        for i in range(12):
            script.append(_tool_call("list_mcp_servers", {}, call_id=f"t{i}"))
            script.append(_final(f"done {i}"))
        agent = make_supervisor(script, max_messages=4)
        for i in range(12):
            agent.chat(f"q{i}")
            _assert_no_orphan_tools(agent.messages)
            assert len(agent.messages) <= 5

    def test_under_cap_nothing_dropped(self) -> None:
        agent = make_supervisor([_final("hi")], max_messages=24)
        agent.chat("hello")
        assert [m["role"] for m in agent.messages] == ["system", "user", "assistant"]

    def test_zero_cap_is_clamped_not_unbounded(self) -> None:
        script = [_final(f"a{i}") for i in range(5)]
        agent = make_supervisor(script, max_messages=0)
        for i in range(5):
            agent.chat(f"q{i}")
        assert (
            len(agent.messages) <= 2
        )  # at least the newest non-system message survives
        assert agent.messages[0]["role"] == "system"


# ── trace enrichment ────────────────────────────────────────────────────────
class TestTraceEnrichment:
    def test_trace_has_duration(self) -> None:
        agent = make_supervisor([_tool_call("list_mcp_servers", {}), _final("ok")])
        out = agent.chat("list servers")
        entry = out["tool_trace"][0]
        assert entry["tool"] == "list_mcp_servers" and entry["ok"] is True
        assert isinstance(entry["duration_ms"], float) and entry["duration_ms"] >= 0.0

    def test_trace_carries_error_text_on_failure(self) -> None:
        def exploding_transport(method, url, payload):
            raise ConnectionError("a2a down")

        client = A2AClient("http://a2a", transport=exploding_transport)
        registry = type("R", (), {"find_by_skill": staticmethod(lambda s: [])})()
        script = [
            _tool_call(
                "ask_skills_agent", {"skill": "infer_skills", "params": {"text": "x"}}
            ),
            _final("gave up"),
        ]

        def llm(messages, tools=None):
            return script.pop(0)(messages)

        agent = SupervisorChatAgent(
            llm, client, registry, McpRegistry(persistence_path=None)
        )
        out = agent.chat("try")
        entry = out["tool_trace"][0]
        assert entry["ok"] is False
        assert "a2a down" in entry["error"]


# ── workflow input validation ───────────────────────────────────────────────
class TestWorkflowValidation:
    def test_empty_and_oversized_inputs_fail_before_transport(self) -> None:
        calls = []

        def transport(method, url, payload):
            calls.append(1)
            return {
                "status": "completed",
                "artifact": {"skills": [{"canonical_name": "Python"}]},
            }

        client = A2AClient("http://a2a", transport=transport)
        assert screen_candidate(client, " ", "resume")["status"] == "failed"
        assert (
            screen_candidate(client, "jd", "x" * (MAX_WORKFLOW_CHARS + 1))["status"]
            == "failed"
        )
        assert talent_brief(client, lambda s: [], "")["status"] == "failed"
        assert calls == []  # nothing paid for downstream

    def test_jd_with_no_skills_fails_with_clear_error(self) -> None:
        def transport(method, url, payload):
            if payload["params"]["context_type"] == "job_description":
                return {"status": "completed", "artifact": {"skills": []}}
            return {
                "status": "completed",
                "artifact": {"skills": [{"canonical_name": "Python"}]},
            }

        client = A2AClient("http://a2a", transport=transport)
        out = screen_candidate(client, "unparseable jd text", "Python dev")
        assert out["status"] == "failed"
        assert "no skills" in out["error"]

    def test_valid_inputs_still_work(self) -> None:
        def transport(method, url, payload):
            skills = (
                [{"canonical_name": "Python"}, {"canonical_name": "SQL"}]
                if payload["params"]["context_type"] == "job_description"
                else [{"canonical_name": "Python"}]
            )
            return {"status": "completed", "artifact": {"skills": skills}}

        client = A2AClient("http://a2a", transport=transport)
        out = screen_candidate(client, "Python and SQL", "Python dev")
        assert out["status"] == "completed"
        assert out["matched"] == ["Python"] and out["gaps"] == ["SQL"]
        assert out["coverage"] == 0.5
