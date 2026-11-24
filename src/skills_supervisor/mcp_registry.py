from __future__ import annotations

import json
import threading
from pathlib import Path

DEFAULT_SERVERS = [
    {
        "name": "skills-engine-tools",
        "transport": "stdio",
        "endpoint": "python src/skills_mcp/server.py",
        "framework": "fastmcp",
        "tools": [
            "infer_skills",
            "normalize_skill",
            "search_taxonomy",
            "taxonomy_stats",
            "lifecycle_report",
        ],
    }
]


class McpRegistry:
    def __init__(
        self, servers: list[dict] | None = None, persistence_path: Path | None = None
    ) -> None:
        self._servers: dict[str, dict] = {
            s["name"]: s for s in (servers if servers is not None else DEFAULT_SERVERS)
        }
        self._health: dict[str, bool] = {}
        self._lock = threading.Lock()
        self.persistence_path = persistence_path
        self._load()

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        data = json.loads(self.persistence_path.read_text(encoding="utf-8"))
        for entry in data.get("servers", []):
            self._servers[entry["name"]] = entry

    def _save(self) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"servers": list(self._servers.values())}
        self.persistence_path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def register(self, entry: dict) -> dict:
        with self._lock:
            if "name" not in entry or not str(entry["name"]).strip():
                raise ValueError("server entry requires a non-empty name")
            required = {"transport", "endpoint"}
            missing = required - set(entry)
            if missing:
                raise ValueError(f"server entry missing fields: {sorted(missing)}")
            entry.setdefault("framework", "fastmcp")
            entry.setdefault("tools", [])
            self._servers[entry["name"]] = entry
            self._save()
            return entry

    def deregister(self, name: str) -> bool:
        with self._lock:
            return self._servers.pop(name, None) is not None

    def list_servers(self) -> list[dict]:
        out = []
        for name in sorted(self._servers):
            entry = dict(self._servers[name])
            entry["healthy"] = self._health.get(name, True)
            out.append(entry)
        return out

    def get(self, name: str) -> dict | None:
        return self._servers.get(name)

    def check_health(self, prober=None) -> dict[str, bool]:
        results = {}
        for name, entry in self._servers.items():
            try:
                ok = prober(entry) if prober is not None else True
            except Exception:
                ok = False
            self._health[name] = bool(ok)
            results[name] = bool(ok)
        return results
