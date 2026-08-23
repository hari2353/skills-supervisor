def test_chat_endpoint_runs_supervisor_with_injected_llm(client):
    body = client.post("/chat", json={"message": "What skills does this JD need: Python platform engineer?"}).json()
    assert "Python" in body["reply"]
    assert body["tool_trace"][0]["tool"] == "ask_skills_agent"


def test_a2a_tasks_endpoint(client):
    resp = client.post(
        "/a2a/skills-agent/tasks",
        json={"skill": "infer_skills", "params": {"text": "Python and Kubernetes", "context_type": "job_description"}},
    ).json()
    assert resp["status"] == "completed"
    assert resp["task_id"]
    names = {s["canonical_name"] for s in resp["artifact"]["skills"]}
    assert names == {"Python", "Kubernetes"}


def test_a2a_tasks_rejects_bad_skill(client):
    assert client.post("/a2a/skills-agent/tasks", json={"skill": "nope", "params": {}}).status_code == 422


def test_wellknown_cards_exposed(client):
    a = client.get("/.well-known/skills-agent.json").json()
    s = client.get("/.well-known/supervisor.json").json()
    assert a["name"] == "skills-agent" and s["name"] == "skills-supervisor"


def test_screen_candidate_workflow_end_to_end(client):
    body = client.post(
        "/workflows/screen-candidate",
        json={"jd_text": "Need Python on Kubernetes", "resume_text": "my resume has Python"},
    ).json()
    assert body["matched"] == ["Python"]
    assert body["gaps"] == ["Kubernetes"]
    assert body["verdict"] == "partial_match"
    calls = [c for c in client.app.routes]
    assert calls


def test_mcp_servers_listing_and_registration(client, tmp_path):
    servers = client.get("/mcp/servers").json()
    assert any(s["name"] == "skills-engine-tools" for s in servers)
    ok = client.post("/mcp/servers", json={"name": "extra", "transport": "stdio", "endpoint": "x"})
    assert ok.status_code == 200
    bad = client.post("/mcp/servers", json={"name": ""})
    assert bad.status_code == 422
    health = client.post("/mcp/health").json()
    assert all(v is True for v in health.values())
