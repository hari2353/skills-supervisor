from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, HTTPException

from .a2a import AGENT_CARD, A2AClient, SUPERVISOR_CARD
from .diagnostics import Diagnostic
from .mcp_registry import McpRegistry
from .skills_agent import SkillsAgent
from .supervisor import SupervisorChatAgent
from .workflows import screen_candidate, talent_brief


class NullRegistry:
    def find_by_skill(self, skill_name: str):
        return []


def create_app(
    skills_agent: SkillsAgent | None = None,
    registry=None,
    mcp_registry: McpRegistry | None = None,
    llm_chat=None,
) -> FastAPI:
    app = FastAPI(title="Skills Supervisor", version="0.1.0")

    agent = skills_agent or SkillsAgent(
        os.getenv("SKILLS_ENGINE_URL", "http://127.0.0.1:8000")
    )
    mcp = mcp_registry or McpRegistry()
    chat_llm = llm_chat
    registry_adapter = registry

    def a2a_transport(method: str, path: str, payload: dict) -> dict:
        return agent.handle(payload["skill"], payload["params"])

    skills_client_for_workflows = A2AClient(AGENT_CARD["url"], transport=a2a_transport)
    chat_skills_client = A2AClient(AGENT_CARD["url"], transport=a2a_transport)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/.well-known/skills-agent.json")
    def skills_agent_card() -> dict:
        return AGENT_CARD

    @app.get("/.well-known/supervisor.json")
    def supervisor_card() -> dict:
        return SUPERVISOR_CARD

    @app.post("/a2a/skills-agent/tasks")
    def a2a_tasks(payload: dict) -> dict:
        task_id = uuid.uuid4().hex[:12]
        result = agent.handle(
            str(payload.get("skill", "")), dict(payload.get("params", {}))
        )
        result["task_id"] = task_id
        if result["status"] == "failed":
            raise HTTPException(
                status_code=422, detail=result.get("diagnostic") or result.get("error")
            )
        return result

    @app.post("/chat")
    def chat(payload: dict) -> dict:
        if chat_llm is None:
            raise HTTPException(
                status_code=503,
                detail="LLM backend not configured; set SKILLS_LLM_BASE_URL",
            )
        message = str(payload.get("message", ""))[:10000].strip()
        if not message:
            raise HTTPException(
                status_code=422,
                detail=Diagnostic("SUP_INPUT_EMPTY", "message required").to_dict(),
            )
        supervisor = SupervisorChatAgent(
            chat_llm, chat_skills_client, registry_adapter or NullRegistry(), mcp
        )
        return supervisor.chat(message)

    @app.post("/workflows/screen-candidate")
    def workflow_screen(payload: dict) -> dict:
        jd_text = str(payload.get("jd_text", "")).strip()
        resume_text = str(payload.get("resume_text", "")).strip()
        if not jd_text or not resume_text:
            raise HTTPException(
                status_code=422,
                detail=Diagnostic(
                    "SUP_INPUT_EMPTY", "jd_text and resume_text required"
                ).to_dict(),
            )
        return screen_candidate(skills_client_for_workflows, jd_text, resume_text)

    @app.post("/workflows/talent-brief")
    def workflow_brief(payload: dict) -> dict:
        topic = str(payload.get("topic", "")).strip()
        if not topic:
            raise HTTPException(
                status_code=422,
                detail=Diagnostic("SUP_INPUT_EMPTY", "topic required").to_dict(),
            )
        if registry_adapter is None:
            raise HTTPException(status_code=503, detail="agent-registry not wired")
        return talent_brief(
            skills_client_for_workflows, registry_adapter.find_by_skill, topic
        )

    @app.get("/mcp/servers")
    def list_mcp_servers() -> list[dict]:
        return mcp.list_servers()

    @app.post("/mcp/servers")
    def register_mcp_server(entry: dict) -> dict:
        try:
            return mcp.register(entry)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.delete("/mcp/servers/{name}")
    def deregister_mcp_server(name: str) -> dict:
        if not mcp.deregister(name):
            raise HTTPException(status_code=404, detail="unknown server")
        return {"name": name, "deregistered": True}

    @app.post("/mcp/health")
    def mcp_health() -> dict:
        return mcp.check_health()

    return app


app = create_app()
