"""Agent repair contract: workflow rejections and delegation failures carry a
stable code, a plain-language fix, and a docs pointer.
"""

from pathlib import Path

from skills_supervisor.diagnostics import CATALOG
from skills_supervisor.supervisor import SupervisorChatAgent
from skills_supervisor.workflows import MAX_WORKFLOW_CHARS, screen_candidate

ROOT = Path(__file__).resolve().parents[1]


class NoCall:
    def send_task(self, *args, **kwargs):
        raise AssertionError("validation must happen before any downstream call")


class EmptySkills:
    def send_task(self, skill, params):
        return {"status": "completed", "artifact": {"skills": []}}


class DownSkills:
    def send_task(self, skill, params):
        raise RuntimeError("engine down")


def test_blank_input_has_code_and_fix() -> None:
    out = screen_candidate(NoCall(), "  ", "resume")
    assert out["status"] == "failed"
    diag = out["diagnostic"]
    assert diag["code"] == "SUP_INPUT_EMPTY"
    assert diag["hint"] and diag["docs"].startswith("docs/diagnostics.md#")


def test_oversize_input_has_its_own_code() -> None:
    out = screen_candidate(NoCall(), "x" * (MAX_WORKFLOW_CHARS + 1), "resume")
    assert out["diagnostic"]["code"] == "SUP_INPUT_TOO_LARGE"


def test_no_extracted_skills_has_code() -> None:
    out = screen_candidate(EmptySkills(), "jd", "resume")
    assert out["diagnostic"]["code"] == "SUP_NO_SKILLS"


def test_unknown_tool_reports_code() -> None:
    out = SupervisorChatAgent(None, None, None, None)._dispatch("nope", {})
    assert out["diagnostic"]["code"] == "SUP_TOOL_UNKNOWN"
    assert out["diagnostic"]["hint"]


def test_delegation_failure_reports_code_and_request_id() -> None:
    supervisor = SupervisorChatAgent(None, DownSkills(), None, None)
    out = supervisor._dispatch("ask_skills_agent", {"skill": "infer_skills"})
    assert out["diagnostic"]["code"] == "SUP_DELEGATION_FAILED"
    assert out["request_id"]


def test_api_a2a_failure_detail_has_code(client) -> None:
    resp = client.post("/a2a/skills-agent/tasks", json={"skill": "nope", "params": {}})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "SUP_TOOL_UNKNOWN"


def test_catalog_is_documented() -> None:
    docs = (ROOT / "docs" / "diagnostics.md").read_text(encoding="utf-8")
    missing = [code for code in CATALOG if code not in docs]
    assert not missing, f"undocumented diagnostic codes: {missing}"
