from skills_supervisor.a2a import A2AClient
from skills_supervisor.workflows import screen_candidate, talent_brief


def make_client(skills_by_text):
    def transport(method, url, payload):
        if url.endswith("/tasks"):
            text = payload["params"]["text"]
            return {
                "status": "completed",
                "artifact": {
                    "skills": [{"canonical_name": s} for s in skills_by_text(text)]
                },
            }
        raise AssertionError(url)

    return A2AClient("http://fake", transport=transport)


def test_screen_candidate_matches_and_reports_gaps():
    skills = lambda t: (
        ["Python", "Docker"] if "resume" in t else ["Python", "Kubernetes", "Go"]
    )
    client = make_client(skills)
    out = screen_candidate(
        client, jd_text="Kubernetes Go Python", resume_text="my resume"
    )
    assert out["matched"] == ["Python"]
    assert out["gaps"] == ["Go", "Kubernetes"]
    assert abs(out["coverage"] - 1 / 3) < 0.001
    assert out["verdict"] == "partial_match"


def test_screen_candidate_strong_match():
    skills = lambda t: ["Python", "Docker"]
    out = screen_candidate(make_client(skills), "jd", "resume")
    assert out["verdict"] == "strong_match" and out["coverage"] == 1.0


def test_talent_brief_recommends_agents_and_gaps():
    class Agent:
        card = type("C", (), {"name": "screener", "url": "u"})()

    brief = talent_brief(
        make_client(lambda t: ["Python", "Rust"]),
        registry_find_by_skill=lambda s: [Agent()] if s == "Python" else [],
        topic="backend role",
    )
    assert brief["recommended_agents"][0]["agent"] == "screener"
    assert brief["skill_gaps"] == ["Rust"]
    assert "1/2" in brief["summary"]
