from __future__ import annotations

from .a2a import AGENT_CARD


class SkillsAgent:
    card = AGENT_CARD
    HANDLED_SKILLS = {s["name"] for s in AGENT_CARD["skills"]}

    def __init__(self, engine_base_url: str, engine_transport=None) -> None:
        self.engine_base_url = engine_base_url.rstrip("/")
        self._transport = engine_transport

    def _get(self, path: str, params: dict | None = None) -> dict:
        if self._transport is not None:
            return self._transport("GET", f"{self.engine_base_url}{path}", params or {})
        import httpx

        resp = httpx.get(f"{self.engine_base_url}{path}", params=params or {}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        if self._transport is not None:
            return self._transport("POST", f"{self.engine_base_url}{path}", payload)
        import httpx

        resp = httpx.post(f"{self.engine_base_url}{path}", json=payload, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

    def handle(self, skill: str, params: dict) -> dict:
        if skill not in self.HANDLED_SKILLS:
            return {"status": "failed", "error": f"unsupported skill '{skill}'"}
        try:
            if skill == "infer_skills":
                artifact = self._post("/v1/skills/infer", params)
            elif skill == "normalize_skill":
                artifact = self._post("/v1/skills/normalize", {"name": params.get("name", "")})
            elif skill == "search_taxonomy":
                artifact = {"results": self._get("/v1/skills/search", {"q": params.get("query", ""), "k": params.get("k", 5)})["results"]}
            else:
                report_params = {}
                if params.get("today"):
                    report_params["today"] = params["today"]
                artifact = self._get("/v1/lifecycle/report", report_params)
        except Exception as exc:
            return {"status": "failed", "error": f"skills-engine unreachable: {exc}"}
        return {"status": "completed", "artifact": artifact}
