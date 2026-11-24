import json

from skills_supervisor.a2a import A2AClient
from skills_supervisor.mcp_registry import McpRegistry
from skills_supervisor.skills_agent import SkillsAgent
from skills_supervisor.supervisor import TOOLS, SupervisorChatAgent


def fake_llm_script(script):
    calls = []

    def chat(messages, tools=None):
        calls.append([m["role"] for m in messages])
        step = script.pop(0)
        return step(messages)

    chat.calls = calls
    return chat


def make_supervisor(llm):
    transport = lambda method, url, payload: {
        "status": "completed",
        "artifact": {"skills": [{"canonical_name": "Python"}]},
    }
    skills_client = A2AClient("http://a2a", transport=transport)
    registry = type("R", (), {"find_by_skill": staticmethod(lambda s: [])})()
    return SupervisorChatAgent(
        llm, skills_client, registry, McpRegistry(persistence_path=None)
    )


def test_tool_manifest_is_valid_function_calling_schema():
    for tool in TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["parameters"]["type"] == "object"


def test_supervisor_delegates_to_subagent_and_closes_loop():
    def step_one(messages, tools=None):
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": "t1",
                    "name": "ask_skills_agent",
                    "arguments": {
                        "skill": "infer_skills",
                        "params": {"text": "Python dev"},
                    },
                }
            ],
            "raw_tool_calls": [],
        }

    def step_two(messages, tools=None):
        tool_msg = [m for m in messages if m["role"] == "tool"][0]
        payload = json.loads(tool_msg["content"])
        return {
            "content": f"found {payload['artifact']['skills'][0]['canonical_name']}",
            "tool_calls": [],
            "raw_tool_calls": [],
        }

    supervisor = make_supervisor(fake_llm_script([step_one, step_two]))
    out = supervisor.chat("what skills are in this JD?")
    assert "Python" in out["reply"]
    assert (
        out["tool_trace"][0]["tool"] == "ask_skills_agent"
        and out["tool_trace"][0]["ok"] is True
    )
    roles = supervisor.messages[0]["role"], supervisor.messages[1]["role"]
    assert roles == ("system", "user")


def test_dispatch_reports_errors_without_raising():
    def failing_llm(messages, tools=None):
        return {
            "content": None,
            "tool_calls": [{"id": "x", "name": "nope", "arguments": {}}],
            "raw_tool_calls": [],
        }

    def final(messages, tools=None):
        return {
            "content": "handled failure gracefully",
            "tool_calls": [],
            "raw_tool_calls": [],
        }

    supervisor = make_supervisor(fake_llm_script([failing_llm, final]))
    out = supervisor.chat("hi")
    assert out["reply"] == "handled failure gracefully"
    assert out["tool_trace"][0]["ok"] is False
