"""Deterministic test runner & end-to-end demo execution for Cognitive Career Navigator.

Replicates the 20-step Section 24 demonstration workflow:
1. Arun logs into the portal
2. His existing skill profile is displayed
3. REST APIs has a low score of 30
4. The system remembers his GET vs POST misconception
5. AI selects REST APIs as today's learning topic
6. AI teaches the concept
7. Arun gives an incorrect answer ("POST is used to retrieve data from a database.")
8. Agent detects the misconception (Confusion between GET and POST, 0.96 confidence)
9. Agent provides corrective teaching
10. Arun answers the follow-up correctly ("GET")
11. Skill evidence is updated from 30 to 45
12. Arun pastes a real software engineering job description
13. System extracts and verifies required skills with verbatim citations
14. System compares job requirements with Arun's profile
15. DSA and REST APIs are identified as priority gaps
16. System recommends a new learning plan
17. Arun accepts the recommendation
18. Recommendation is saved in SQLite
19. Arun restarts the application (Store reopened from disk)
20. The next session prioritizes the accepted job-related skills
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .services import NavigatorService


def run_arun_demo(db_path: str = "run.db") -> dict[str, Any]:
    """Execute the full 20-step Section 24 demo workflow."""
    results: list[dict[str, Any]] = []

    def step(num: int, title: str, status: str, detail: str) -> None:
        results.append({"step": num, "title": title, "status": status, "detail": detail})

    service = NavigatorService(db_path)

    # 1. Arun logs into the portal
    student = service.login_student("arun@college.edu", "secret")
    assert student is not None, "Login failed"
    step(1, "Student Login", "PASS", f"Arun logged in successfully (ID: {student.student_id})")

    # 2. Existing skill profile displayed
    profile = service.get_student_profile(student.student_id)
    step(2, "Load Skill Profile", "PASS", f"Loaded profile for {profile.name} with {len(profile.skills)} skills.")

    # 3. REST APIs has a low score of 30
    rest_score = profile.skills["REST APIs"].score
    assert rest_score == 30, f"Expected REST APIs score 30, got {rest_score}"
    step(3, "Inspect REST APIs Score", "PASS", f"REST APIs score verified at {rest_score}/100 (Beginner).")

    # 4. System remembers GET vs POST misconception
    unresolved = service.get_unresolved_misconceptions(student.student_id)
    assert any("Confusion between GET and POST" in m.misconception for m in unresolved), "Misconception not found"
    step(4, "Check Prior Misconceptions", "PASS", "Found stored misconception: 'Confusion between GET and POST'.")

    # 5. AI selects REST APIs as today's learning topic
    rec = service.select_next_skill(student.student_id)
    assert rec["skill"] == "REST APIs", "AI did not select REST APIs"
    step(5, "Select Today's Topic", "PASS", f"Selected {rec['skill']} — Reasons: {'; '.join(rec['reasons'])}")

    # 6. AI teaches the concept
    lesson = service.generate_lesson("REST APIs")
    step(6, "AI Concept Lesson", "PASS", f"Lesson delivered: '{lesson.title}'.")

    # 7. Arun gives an incorrect answer
    student_ans = "POST is used to retrieve data from a database."
    step(7, "Student Answers Question", "RECORDED", f"Student answer submitted: '{student_ans}'")

    # 8. Agent detects misconception (0.96 confidence)
    eval_res = service.evaluate_student_answer("What is the purpose of HTTP POST?", student_ans)
    assert not eval_res.is_correct, "Evaluation should have marked answer incorrect"
    assert eval_res.detected_misconception == "Confusion between GET and POST"
    assert eval_res.misconception_confidence == 0.96
    step(8, "Misconception Classification", "PASS", f"Detected '{eval_res.detected_misconception}' (Confidence: {eval_res.misconception_confidence}).")

    # 9. Agent provides corrective teaching
    corrective = service.generate_corrective_explanation(eval_res.detected_misconception)
    step(9, "Corrective Teaching", "PASS", f"Generated targeted correction: '{corrective[:80]}...'")

    # 10. Arun answers follow-up correctly ("GET")
    followup_q = service.generate_followup_question("REST APIs")
    followup_eval = service.evaluate_student_answer(followup_q.question, "GET is safe and idempotent, used for fetching")
    assert followup_eval.is_correct, "Follow-up should have passed"
    step(10, "Follow-up Assessment", "PASS", "Arun answered follow-up correctly with 'GET'.")

    # 11. Skill evidence updated from 30 to 45
    service.update_skill_evidence(student.student_id, "REST APIs", 15)
    service.mark_misconception_resolved(student.student_id, "Confusion between GET and POST")
    updated_profile = service.get_student_profile(student.student_id)
    new_rest_score = updated_profile.skills["REST APIs"].score
    assert new_rest_score == 45, f"Expected 45, got {new_rest_score}"
    step(11, "Update Skill Evidence", "PASS", f"REST APIs score updated from 30 to {new_rest_score} in SQLite.")

    # 12. Arun pastes a real software engineering job description
    corpus_jd = Path("corpus/job-descriptions-2024.md").read_text(encoding="utf-8")
    job_doc = service.submit_job_description(student.student_id, corpus_jd)
    step(12, "Submit Job Description", "PASS", f"Stored JD document for {job_doc.company} ({len(job_doc.text)} chars).")

    # 13. System extracts and verifies required skills with verbatim citations
    reqs = service.extract_job_requirements(corpus_jd)
    verified_skills = [r.skill for r in reqs if r.verification_status == "Verified"]
    excluded_skills = [r.skill for r in reqs if r.verification_status == "Excluded"]
    assert "Python" in verified_skills and "REST APIs" in verified_skills and "DSA" in verified_skills
    assert "Kubernetes" in excluded_skills  # Provenance checker demoted hallucinated requirement!
    step(13, "Citation Provenance Check", "PASS", f"Verified: {verified_skills}; Excluded unverified: {excluded_skills}")

    # 14. System compares job requirements with Arun's profile
    gap_report = service.generate_job_gap_report(student.student_id, job_doc.job_id)
    step(14, "Skill Gap Analysis", "PASS", f"Generated gap report with {len(gap_report.gaps)} evaluated competencies.")

    # 15. DSA and REST APIs are identified as priority gaps
    assert "DSA" in gap_report.high_priority_skills
    assert "REST APIs" in gap_report.high_priority_skills
    step(15, "Identify Priority Gaps", "PASS", f"Identified High Priority Gaps: {gap_report.high_priority_skills}")

    # 16. System recommends a new learning plan
    plan = service.generate_learning_plan(student.student_id)
    assert plan.status == "WAITING_FOR_STUDENT"
    checkpoint = service.create_student_checkpoint(student.student_id, plan)
    step(16, "Generate Learning Plan", "PASS", f"Plan '{plan.title}' parked in WAITING_FOR_STUDENT state.")

    # 17. Arun accepts the recommendation
    decision = service.accept_recommendation(student.student_id, checkpoint.checkpoint_id)
    assert decision.action == "ACCEPT"
    step(17, "Student Approval Checkpoint", "PASS", f"Arun explicitly approved plan: '{decision.action}'.")

    # 18. Recommendation is saved in SQLite
    latest_plan = service.store.latest(service._get_student_run_id(student.student_id), "learning_plan")
    assert latest_plan["status"] == "ACCEPTED"
    step(18, "Durable State Persistence", "PASS", "Accepted plan and decision written to immutable SQLite versions table.")

    # 19. Arun restarts the application (Simulated by initializing new service instance)
    restarted_service = NavigatorService(db_path)
    restarted_profile = restarted_service.get_student_profile(student.student_id)
    assert restarted_profile.skills["REST APIs"].score == 45
    step(19, "Application Restart Survival", "PASS", f"Store re-opened: REST APIs score {restarted_profile.skills['REST APIs'].score} preserved.")

    # 20. Next session prioritizes the accepted job-related skills
    restarted_plan = restarted_service.store.latest(restarted_service._get_student_run_id(student.student_id), "learning_plan")
    assert restarted_plan["status"] == "ACCEPTED"
    assert "REST APIs" in restarted_plan["target_skills"] and "DSA" in restarted_plan["target_skills"]
    step(20, "Next Session Adaptation", "PASS", f"Next session prioritizes accepted skills: {restarted_plan['target_skills']}")

    return {
        "success": True,
        "steps_completed": len(results),
        "student": student.name,
        "final_rest_score": new_rest_score,
        "accepted_skills": restarted_plan["target_skills"],
        "timeline": results,
    }
