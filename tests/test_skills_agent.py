from skills_supervisor.a2a import A2AClient, AGENT_CARD, SUPERVISOR_CARD
from skills_supervisor.skills_agent import SkillsAgent


def test_agent_card_declares_a2a_skills():
    names = {s["name"] for s in AGENT_CARD["skills"]}
    assert {
        "infer_skills",
        "normalize_skill",
        "search_taxonomy",
        "lifecycle_report",
    } <= names
    assert "a2a-tasks" in AGENT_CARD["capabilities"]
    assert SUPERVISOR_CARD["name"] == "skills-supervisor"


def test_skills_agent_infers_via_engine(engine_transport):
    agent = SkillsAgent("http://engine.local", engine_transport=engine_transport)
    result = agent.handle(
        "infer_skills",
        {"text": "Python and Kubernetes role", "context_type": "job_description"},
    )
    assert result["status"] == "completed"
    names = {s["canonical_name"] for s in result["artifact"]["skills"]}
    assert names == {"Python", "Kubernetes"}


def test_skills_agent_rejects_unknown_skill():
    agent = SkillsAgent("http://engine.local", engine_transport=lambda *a: {})
    result = agent.handle("brew_coffee", {})
    assert result["status"] == "failed"
    assert "unsupported skill" in result["error"]


def test_skills_agent_engine_outage_is_contained():
    def boom(method, url, payload):
        raise ConnectionError("down")

    agent = SkillsAgent("http://engine.local", engine_transport=boom)
    result = agent.handle("lifecycle_report", {})
    assert result["status"] == "failed"
    assert "unreachable" in result["error"]


def test_a2a_client_send_task_shape(engine_transport):
    client = A2AClient(
        "http://fake",
        transport=lambda m, p, pl: {"status": "completed", "artifact": {"ok": True}},
    )
    resp = client.send_task("search_taxonomy", {"query": "kafka"})
    assert A2AClient.artifact(resp) == {"ok": True}
