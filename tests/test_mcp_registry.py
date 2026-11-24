from skills_supervisor.mcp_registry import McpRegistry


def test_default_registry_ships_fastmcp_skills_tools():
    reg = McpRegistry(persistence_path=None)
    servers = reg.list_servers()
    entry = next(s for s in servers if s["name"] == "skills-engine-tools")
    assert entry["framework"] == "fastmcp"
    assert "infer_skills" in entry["tools"]


def test_register_validates_required_fields(tmp_path):
    reg = McpRegistry(persistence_path=tmp_path / "mcp.json")
    try:
        reg.register({"name": ""})
        raised = False
    except ValueError:
        raised = True
    assert raised
    try:
        reg.register({"name": "x"})
        raised = False
    except ValueError:
        raised = True
    assert raised

    saved = reg.register(
        {"name": "docs-tools", "transport": "stdio", "endpoint": "python docs_mcp.py"}
    )
    assert saved["framework"] == "fastmcp"

    reg2 = McpRegistry(persistence_path=tmp_path / "mcp.json")
    assert reg2.get("docs-tools") is not None
    names = [s["name"] for s in reg2.list_servers()]
    assert {"skills-engine-tools", "docs-tools"} <= set(names)


def test_deregister_and_health_probing():
    reg = McpRegistry(persistence_path=None)
    reg.check_health(prober=lambda entry: entry["name"] != "dead")
    reg._servers["dead"] = {"name": "dead", "transport": "stdio", "endpoint": "x"}
    health = reg.check_health(prober=lambda entry: entry["name"] != "dead")
    assert health["dead"] is False
    listing = {s["name"]: s for s in reg.list_servers()}
    assert listing["dead"]["healthy"] is False
    assert listing["skills-engine-tools"]["healthy"] is True
    assert reg.deregister("dead") is True
    assert reg.get("dead") is None
