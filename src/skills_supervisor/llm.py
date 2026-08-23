from __future__ import annotations

import json
import os

import httpx

from .supervisor import TOOLS


class OpenAICompatChat:
    def __init__(self, base_url: str | None = None, api_key: str = "", model: str = "", timeout: float = 60.0) -> None:
        self.base_url = (base_url or os.getenv("SKILLS_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("SKILLS_LLM_API_KEY", "")
        self.model = model or os.getenv("SKILLS_LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.base_url)

    def __call__(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self.base_url:
            raise RuntimeError("LLM backend not configured; set SKILLS_LLM_BASE_URL (Ollama/Groq/vLLM all work)")
        payload: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            payload["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]
        raw_calls = message.get("tool_calls") or []
        parsed_calls = [
            {
                "id": call.get("id", ""),
                "name": call["function"]["name"],
                "arguments": json.loads(call["function"]["arguments"] or "{}"),
            }
            for call in raw_calls
        ]
        return {"content": message.get("content"), "tool_calls": parsed_calls, "raw_tool_calls": raw_calls}


def tool_manifest() -> list[dict]:
    return TOOLS
