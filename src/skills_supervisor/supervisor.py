from __future__ import annotations

import json
import uuid


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_skills_agent",
            "description": "Delegate skill work to the A2A skills-agent subagent. Skills: infer_skills (params: text, context_type), normalize_skill (params: name), search_taxonomy (params: query, k), lifecycle_report (params: today optional).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "enum": ["infer_skills", "normalize_skill", "search_taxonomy", "lifecycle_report"]},
                    "params": {"type": "object"},
                },
                "required": ["skill"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_agent_registry",
            "description": "Find registered A2A agents from the agent-registry that cover a given skill name.",
            "parameters": {
                "type": "object",
                "properties": {"skill_name": {"type": "string"}},
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_mcp_servers",
            "description": "List MCP servers registered in the MCP registry with their transports and tools.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = (
    "You are a talent-intelligence supervisor. You do not answer skill questions directly; you delegate to the "
    "skills-agent subagent via ask_skills_agent, discover agents via search_agent_registry, and inspect MCP "
    "infrastructure via list_mcp_servers. Cite which tool produced each fact. If delegation fails, say so plainly."
)

MAX_TOOL_ROUNDS = 6


class SupervisorChatAgent:
    def __init__(self, llm_chat, skills_client, registry_client, mcp_registry) -> None:
        self.llm_chat = llm_chat
        self.skills_client = skills_client
        self.registry_client = registry_client
        self.mcp_registry = mcp_registry
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_message: str) -> dict:
        self.messages.append({"role": "user", "content": user_message})
        trace: list[dict] = []
        for _ in range(MAX_TOOL_ROUNDS):
            response = self.llm_chat(self.messages, tools=TOOLS)
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                reply = response.get("content") or ""
                self.messages.append({"role": "assistant", "content": reply})
                return {"reply": reply, "tool_trace": trace}
            assistant_msg = {"role": "assistant", "content": response.get("content"), "tool_calls": response["raw_tool_calls"]}
            self.messages.append(assistant_msg)
            for call in tool_calls:
                result = self._dispatch(call["name"], call["arguments"])
                trace.append({"tool": call["name"], "arguments": call["arguments"], "ok": "error" not in result})
                self.messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, default=str)}
                )
        return {"reply": "stopped after maximum tool rounds", "tool_trace": trace}

    def _dispatch(self, name: str, arguments: dict) -> dict:
        try:
            if name == "ask_skills_agent":
                task = self.skills_client.send_task(arguments["skill"], arguments.get("params", {}))
                return task
            if name == "search_agent_registry":
                matches = self.registry_client.find_by_skill(arguments["skill_name"])
                return {"agents": [a.card.model_dump(mode="json") for a in matches]}
            if name == "list_mcp_servers":
                return {"servers": self.mcp_registry.list_servers()}
            return {"error": f"unknown tool '{name}'"}
        except Exception as exc:
            return {"error": str(exc), "request_id": uuid.uuid4().hex}
