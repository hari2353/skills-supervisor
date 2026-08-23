from __future__ import annotations

from .a2a import A2AClient


def screen_candidate(skills_client: A2AClient, jd_text: str, resume_text: str) -> dict:
    jd_task = skills_client.send_task("infer_skills", {"text": jd_text, "context_type": "job_description"})
    resume_task = skills_client.send_task("infer_skills", {"text": resume_text, "context_type": "resume"})
    if jd_task.get("status") != "completed" or resume_task.get("status") != "completed":
        return {"status": "failed", "error": jd_task.get("error") or resume_task.get("error")}

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
    coverage = round(len(matched) / len(required), 4) if required else 0.0
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
    task = skills_client.send_task("infer_skills", {"text": topic, "context_type": "job_description"})
    if task.get("status") != "completed":
        return {"status": "failed", "error": task.get("error")}
    required = sorted({s["canonical_name"] for s in A2AClient.artifact(task).get("skills", []) if s.get("canonical_name")})
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
