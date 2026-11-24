AGENT_CARD = {
    "name": "skills-agent",
    "description": "A2A subagent that performs skill inference, normalization, taxonomy search, and lifecycle reporting via skills-engine",
    "url": "/a2a/skills-agent",
    "version": "0.1.0",
    "skills": [
        {
            "name": "infer_skills",
            "description": "extract + resolve skills from text for a given context_type",
        },
        {
            "name": "normalize_skill",
            "description": "map a raw label to the three-tier taxonomy",
        },
        {"name": "search_taxonomy", "description": "semantic search across all tiers"},
        {
            "name": "lifecycle_report",
            "description": "proposed governance actions with reasons",
        },
    ],
    "capabilities": ["a2a-tasks", "structured-artifacts"],
}

SUPERVISOR_CARD = {
    "name": "skills-supervisor",
    "description": "Supervisor chat agent with tool calling; delegates skill work to the A2A skills-agent subagent and orchestrates deterministic workflows",
    "url": "/chat",
    "version": "0.1.0",
    "skills": [
        {
            "name": "chat",
            "description": "answer talent/skill questions using delegated tools",
        },
        {
            "name": "screen_candidate",
            "description": "deterministic JD-vs-resume coverage workflow",
        },
        {
            "name": "talent_brief",
            "description": "topic brief with agent recommendations and gaps",
        },
    ],
    "capabilities": ["tool-calling", "a2a-delegation", "workflows"],
}


class A2AClient:
    def __init__(self, base_url: str, transport=None) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def send_task(self, skill: str, params: dict | None = None) -> dict:
        payload = {"skill": skill, "params": params or {}}
        if self._transport is not None:
            return self._transport("POST", f"{self.base_url}/tasks", payload)
        import httpx

        resp = httpx.post(f"{self.base_url}/tasks", json=payload, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def artifact(task_response: dict) -> dict:
        return task_response.get("artifact", {})
