import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest


@pytest.fixture()
def engine_transport():
    calls = []

    def transport(method: str, url: str, payload) -> dict:
        calls.append({"method": method, "url": url, "payload": payload})
        if url.endswith("/v1/skills/infer"):
            text = payload.get("text", "")
            skills = []
            if "Python" in text:
                skills.append({"canonical_name": "Python", "skill_id": "esco__007", "tier": "master", "confidence": 1.0, "method": "exact", "explanation": "exact name match in master tier"})
            if "Kubernetes" in text:
                skills.append({"canonical_name": "Kubernetes", "skill_id": "cus__3003", "tier": "custom", "confidence": 1.0, "method": "exact", "explanation": "exact name match in custom tier"})
            return {"skills": skills, "unresolved": [], "context_type": payload.get("context_type", "job_description")}
        if url.endswith("/v1/lifecycle/report"):
            return {"actions": [{"action": "flag_declining", "target": "esco__014"}]}
        raise AssertionError(url)

    transport.calls = calls
    return transport


@pytest.fixture()
def client(engine_transport):
    from fastapi.testclient import TestClient

    from skills_supervisor.app import create_app
    from skills_supervisor.mcp_registry import McpRegistry
    from skills_supervisor.skills_agent import SkillsAgent

    agent = SkillsAgent("http://engine.local", engine_transport=engine_transport)
    mcp = McpRegistry(persistence_path=None)

    class FakeRegistry:
        def find_by_skill(self, skill_name: str):
            class A:
                card = type("C", (), {"name": "resume-screener", "url": "http://screener.local"})()

            return [A()] if skill_name == "Python" else []

    def fake_llm(messages, tools=None):
        last = messages[-1]["content"]
        if len(messages) == 2:
            return {
                "content": None,
                "tool_calls": [{"id": "t1", "name": "ask_skills_agent", "arguments": {"skill": "infer_skills", "params": {"text": last, "context_type": "job_description"}}}],
                "raw_tool_calls": [],
            }
        return {"content": "Delegated to skills-agent; Python found.", "tool_calls": [], "raw_tool_calls": []}

    return TestClient(create_app(skills_agent=agent, registry=FakeRegistry(), mcp_registry=mcp, llm_chat=fake_llm))
