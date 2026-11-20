from __future__ import annotations

from .a2a import A2AClient
from .diagnostics import Diagnostic

MAX_WORKFLOW_CHARS = 8000  # inputs beyond this are refused, never truncated


def _failed(diag: Diagnostic) -> dict:
    return {"status": "failed", "error": diag.message, "diagnostic": diag.to_dict()}


def _invalid(*fields: tuple[str, str]) -> dict | None:
    """Fail before any downstream call: bad workflow input is cheap to reject."""
    for label, text in fields:
        if not text or not text.strip():
            return _failed(Diagnostic("SUP_INPUT_EMPTY", f"{label} must be non-empty"))
        if len(text) > MAX_WORKFLOW_CHARS:
            return _failed(Diagnostic(
                "SUP_INPUT_TOO_LARGE",
                f"{label} too long ({len(text)} > {MAX_WORKFLOW_CHARS} chars)"))
    return None


def screen_candidate(skills_client: A2AClient, jd_text: str, resume_text: str) -> dict:
    bad = _invalid(("jd_text", jd_text), ("resume_text", resume_text))
    if bad:
        return bad
    jd_task = skills_client.send_task("infer_skills", {"text": jd_text, "context_type": "job_description"})
    resume_task = skills_client.send_task("infer_skills", {"text": resume_text, "context_type": "resume"})
    if jd_task.get("status") != "completed" or resume_task.get("status") != "completed":
        existing = jd_task.get("diagnostic") or resume_task.get("diagnostic")
        if existing:
            return {"status": "failed", "error": jd_task.get("error") or resume_task.get("error"),
                    "diagnostic": existing}
        return _failed(Diagnostic(
            "SUP_DELEGATION_FAILED",
            jd_task.get("error") or resume_task.get("error") or "delegation failed"))

    def canonical_names(task_response: dict) -> set[str]:
        return {
            s["canonical_name"]
            for s in A2AClient.artifact(task_response).get("skills", [])
            if s.get("canonical_name")
        }

    required = canonical_names(jd_task)
    have = canonical_names(resume_task)
    matched = sorted(required & have)
    gaps = sorted(required - have)
    if not required:
        return _failed(Diagnostic("SUP_NO_SKILLS",
                                  "no skills extracted from job description"))
    coverage = round(len(matched) / len(required), 4)
    return {
        "status": "completed",
        "required_skills": sorted(required),
        "candidate_skills": sorted(have),
        "matched": matched,
        "gaps": gaps,
        "coverage": coverage,
        "verdict": "strong_match" if coverage >= 0.75 and not gaps else ("partial_match" if matched else "no_overlap"),
    }


def talent_brief(skills_client: A2AClient, registry_find_by_skill, topic: str) -> dict:
    bad = _invalid(("topic", topic))
    if bad:
        return bad
    task = skills_client.send_task("infer_skills", {"text": topic, "context_type": "job_description"})
    if task.get("status") != "completed":
        existing = task.get("diagnostic")
        if existing:
            return {"status": "failed", "error": task.get("error"), "diagnostic": existing}
        return _failed(Diagnostic("SUP_DELEGATION_FAILED",
                                  task.get("error") or "delegation failed"))
    required = sorted({s["canonical_name"] for s in A2AClient.artifact(task).get("skills", []) if s.get("canonical_name")})
    if not required:
        return _failed(Diagnostic("SUP_NO_SKILLS", "no skills extracted from topic"))
    recommendations = []
    covered: set[str] = set()
    for skill in required:
        agents = registry_find_by_skill(skill)
        if agents:
            best = agents[0]
            recommendations.append({"skill": skill, "agent": best.card.name, "url": best.card.url})
            covered.add(skill)
    gaps = [s for s in required if s not in covered]
    return {
        "topic": topic,
        "required_skills": required,
        "recommended_agents": recommendations,
        "skill_gaps": gaps,
        "summary": f"{len(recommendations)}/{len(required)} skills coverable by registered agents; gaps: {', '.join(gaps) if gaps else 'none'}",
    }
