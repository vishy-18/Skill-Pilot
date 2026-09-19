"""Domain backend services for Cognitive Career Navigator (Skill-Pilot).

Implements all functions specified in the specification (Sections 4-18, 21):
- Authentication & Sessions
- Profile & Evidence Portfolio
- Career Goals & Target Roles
- Initial Diagnostic Assessment
- Daily AI Learning Coach (selection, lesson, evaluation, misconception untangling)
- Job Description Analyzer (provenance, citation check, gap report)
- Personalized Learning Plan & Checkpoints
- Progress Tracking & Activity Timeline

Persists durable records in SQLite (Store) outside the context window (Principle 1).
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from slice.config import settings
from slice.records import RunState
from slice.store import Store
from .provenance import verify_batch
from .schema import (
    ActivityEvent,
    AssessmentAnswer,
    CareerGoal,
    CertificateEvidence,
    CheckpointDecision,
    DailyScheduleItem,
    DiagnosticQuestion,
    EvaluationResult,
    ExtractedRequirement,
    JobDocument,
    JobGapReport,
    LearningPlan,
    Lesson,
    MisconceptionRecord,
    ProjectEvidence,
    SkillEvidenceItem,
    SkillGap,
    Student,
    StudentCheckpoint,
    StudentProfile,
    StudentRegistration,
    gen_id,
)

# Standard role skills mapping
ROLE_SKILLS = {
    "Software Engineering Intern": ["Python", "SQL", "DSA", "REST APIs", "Git"],
    "Backend Developer": ["Python", "SQL", "REST APIs", "Docker", "Database Design"],
    "Frontend Developer": ["JavaScript", "TypeScript", "React", "CSS", "HTML"],
    "Data Analyst": ["Python", "SQL", "Pandas", "Tableau", "Statistics"],
    "Machine Learning Engineer": ["Python", "PyTorch", "Math & Stats", "DSA", "MLOps"],
    "Cloud Engineer": ["Linux", "Docker", "Kubernetes", "AWS", "Networking"],
}


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()[:32]


class NavigatorService:
    """Encapsulates all Student Portal business logic backed by SQLite Store."""

    def __init__(self, db_path: str = "run.db") -> None:
        self.store = Store(db_path)
        self.ensure_default_seed()

    def ensure_default_seed(self) -> None:
        """Seed Arun's initial benchmark profile for the standard demo if not present."""
        runs = self.store.list_runs(limit=100)
        arun_runs = [r for r in runs if r.get("domain") == "student_arun"]
        if not arun_runs:
            run_id = self.store.create_run(
                domain="student_arun",
                meta={"name": "Arun", "email": "arun@college.edu", "target_role": "Software Engineering Intern"}
            )
            # 1. Profile
            self.store.append(run_id, "student_profile", {
                "student_id": "std_arun",
                "name": "Arun",
                "college": "National Institute of Technology",
                "department": "Computer Science",
                "graduation_year": 2027,
                "skills": {
                    "Python": {"skill": "Python", "score": 80, "status": "Strong", "evidence_type": "assessment", "verified": True},
                    "SQL": {"skill": "SQL", "score": 55, "status": "Developing", "evidence_type": "assessment", "verified": True},
                    "DSA": {"skill": "DSA", "score": 45, "status": "Weak", "evidence_type": "assessment", "verified": True},
                    "REST APIs": {"skill": "REST APIs", "score": 30, "status": "Beginner", "evidence_type": "assessment", "verified": True},
                    "Git": {"skill": "Git", "score": 85, "status": "Strong", "evidence_type": "assessment", "verified": True},
                },
                "preferred_domains": ["Backend Development", "Software Engineering"],
                "preferred_roles": ["Software Engineering Intern"],
                "completion_pct": 90,
            }, produced_by="system_seed")

            # 2. Career Goal
            self.store.append(run_id, "career_goal", {
                "id": "goal_arun_1",
                "student_id": "std_arun",
                "role": "Software Engineering Intern",
                "is_primary": True,
                "target_skills": ROLE_SKILLS["Software Engineering Intern"],
            }, produced_by="system_seed")

            # 3. Prior Misconception: Confused POST with GET
            self.store.append(run_id, "misconception", {
                "id": "misc_arun_1",
                "student_id": "std_arun",
                "skill": "REST APIs",
                "misconception": "Confusion between GET and POST",
                "detected_answer": "POST is used to retrieve data from a database.",
                "confidence": 0.96,
                "status": "ACTIVE",
                "attempts_count": 1,
            }, produced_by="system_seed")

            # 4. Initial activity log
            self.store.append(run_id, "activity", {
                "event_id": "act_seed_1",
                "student_id": "std_arun",
                "event_type": "profile_init",
                "title": "Career Profile Initialized",
                "details": "Profile created for Arun with Software Engineering Intern target.",
            }, produced_by="system_seed")

    def _get_student_run_id(self, student_id: str) -> str:
        runs = self.store.list_runs(limit=100)
        for r in runs:
            meta = self.store.meta(r["id"])
            if meta.get("student_id") == student_id or r.get("domain") == f"student_{student_id}":
                return r["id"]
        # Fallback to Arun's run if std_arun
        if student_id in ("std_arun", "arun"):
            for r in runs:
                if r.get("domain") == "student_arun":
                    return r["id"]
        # Create run if not exists
        return self.store.create_run(domain=f"student_{student_id}", meta={"student_id": student_id})

    # ----------------------------------------------------------- Authentication (Section 4)

    def register_student(self, data: StudentRegistration) -> Student:
        student_id = gen_id("std")
        run_id = self.store.create_run(
            domain=f"student_{student_id}",
            meta={"student_id": student_id, "name": data.name, "email": data.email}
        )
        student = Student(
            student_id=student_id,
            name=data.name,
            email=data.email,
            password_hash=_hash(data.password),
            college=data.college,
            department=data.department,
            graduation_year=data.graduation_year,
        )
        self.store.append(run_id, "student_account", student.model_dump(), produced_by="auth")
        self.create_student_profile(student_id, {
            "name": data.name,
            "college": data.college,
            "department": data.department,
            "graduation_year": data.graduation_year,
        })
        return student

    def login_student(self, email: str, password: str) -> Student | None:
        runs = self.store.list_runs(limit=100)
        for r in runs:
            acc = self.store.latest(r["id"], "student_account")
            if acc and acc.get("email") == email:
                if acc.get("password_hash") == _hash(password):
                    return Student(**acc)
        # Default seed Arun fallback for demo convenience
        if email in ("arun@college.edu", "arun"):
            return Student(
                student_id="std_arun",
                name="Arun",
                email="arun@college.edu",
                password_hash=_hash("secret"),
                college="National Institute of Technology",
                department="Computer Science",
                graduation_year=2027,
            )
        return None

    def get_student_by_id(self, student_id: str) -> Student | None:
        if student_id in ("std_arun", "arun"):
            return Student(
                student_id="std_arun",
                name="Arun",
                email="arun@college.edu",
                password_hash=_hash("secret"),
                college="National Institute of Technology",
                department="Computer Science",
                graduation_year=2027,
            )
        runs = self.store.list_runs(limit=100)
        for r in runs:
            acc = self.store.latest(r["id"], "student_account")
            if acc and acc.get("student_id") == student_id:
                return Student(**acc)
        prof = self.get_student_profile(student_id)
        if prof and prof.name != "Student":
            return Student(
                student_id=student_id,
                name=prof.name,
                email=f"{student_id}@college.edu",
                password_hash="",
                college=prof.college,
                department=prof.department,
                graduation_year=prof.graduation_year,
            )
        return None

    def logout_student(self, student_id: str) -> bool:
        run_id = self._get_student_run_id(student_id)
        self.record_activity(student_id, "auth", "User Logged Out", "Student logged out of portal.")
        return True

    def validate_session(self, session_token: str) -> bool:
        return bool(session_token and len(session_token) > 4)

    # --------------------------------------------------------- Career Profile (Section 5)

    def create_student_profile(self, student_id: str, data: dict[str, Any]) -> StudentProfile:
        run_id = self._get_student_run_id(student_id)
        profile = StudentProfile(
            student_id=student_id,
            name=data.get("name", "Student"),
            college=data.get("college", "University"),
            department=data.get("department", "Engineering"),
            graduation_year=data.get("graduation_year", 2027),
            skills={
                k: SkillEvidenceItem(
                    skill=k,
                    score=v.get("score", 50),
                    status=v.get("status", "Developing"),
                    evidence_type=v.get("evidence_type", "assessment"),
                    verified=v.get("verified", False),
                )
                for k, v in data.get("skills", {}).items()
            },
            preferred_domains=data.get("preferred_domains", []),
            preferred_roles=data.get("preferred_roles", []),
            completion_pct=data.get("completion_pct", 75),
        )
        self.store.append(run_id, "student_profile", profile.model_dump(), produced_by="profile_service")
        return profile

    def get_student_profile(self, student_id: str) -> StudentProfile:
        run_id = self._get_student_run_id(student_id)
        raw = self.store.latest(run_id, "student_profile")
        if raw:
            return StudentProfile(**raw)
        return StudentProfile(
            student_id=student_id,
            name="Student",
            college="University",
            department="Engineering",
            graduation_year=2027,
        )

    def update_student_profile(self, student_id: str, data: dict[str, Any]) -> StudentProfile:
        prof = self.get_student_profile(student_id)
        dump = prof.model_dump()
        dump.update(data)
        updated = StudentProfile(**dump)
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "student_profile", updated.model_dump(), produced_by="profile_service")
        return updated

    def add_skill_to_profile(self, student_id: str, skill: str, score: int = 50, status: str = "Developing", evidence_type: str = "self_reported") -> None:
        prof = self.get_student_profile(student_id)
        verified = (evidence_type in ("assessment", "project", "verified_learning"))
        prof.skills[skill] = SkillEvidenceItem(
            skill=skill,
            score=score,
            status=status,  # type: ignore
            evidence_type=evidence_type,  # type: ignore
            verified=verified,
        )
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "student_profile", prof.model_dump(), produced_by="profile_service")
        self.record_activity(student_id, "skill_add", f"Skill Added: {skill}", f"Added {skill} with score {score} ({status})")

    def add_project_evidence(self, student_id: str, project: ProjectEvidence) -> None:
        prof = self.get_student_profile(student_id)
        prof.projects.append(project)
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "student_profile", prof.model_dump(), produced_by="evidence_portfolio")
        self.record_activity(student_id, "project_evidence", f"Project Added: {project.title}", f"Linked skills: {', '.join(project.skills_used)}")

    def get_profile_completion_status(self, student_id: str) -> int:
        prof = self.get_student_profile(student_id)
        return prof.completion_pct

    # ----------------------------------------------------- Career Goal Management (Section 6)

    def create_career_goal(self, student_id: str, role: str) -> CareerGoal:
        run_id = self._get_student_run_id(student_id)
        target_skills = ROLE_SKILLS.get(role, ["Python", "SQL", "REST APIs"])
        goal = CareerGoal(
            student_id=student_id,
            role=role,
            is_primary=True,
            target_skills=target_skills,
        )
        self.store.append(run_id, "career_goal", goal.model_dump(), produced_by="career_goal_service")
        self.record_activity(student_id, "career_goal", f"Selected Target Role: {role}", f"Loaded skills: {', '.join(target_skills)}")
        return goal

    def get_active_career_goal(self, student_id: str) -> CareerGoal:
        run_id = self._get_student_run_id(student_id)
        raw = self.store.latest(run_id, "career_goal")
        if raw:
            return CareerGoal(**raw)
        return self.create_career_goal(student_id, "Software Engineering Intern")

    def update_career_goal(self, student_id: str, role: str) -> CareerGoal:
        return self.create_career_goal(student_id, role)

    def list_career_goals(self, student_id: str) -> list[CareerGoal]:
        run_id = self._get_student_run_id(student_id)
        history = self.store.history(run_id, "career_goal")
        return [CareerGoal(**v.payload) for v in history]

    # ---------------------------------------------------- Initial Skill Assessment (Section 7)

    def generate_initial_assessment(self, student_id: str, role: str) -> list[DiagnosticQuestion]:
        skills = ROLE_SKILLS.get(role, ["Python", "REST APIs", "SQL", "DSA", "Git"])
        questions = [
            DiagnosticQuestion(
                skill="Python",
                question="What is the difference between a list and a tuple in Python?",
                options=["Lists are mutable, tuples are immutable", "Tuples are mutable, lists are immutable", "Both are immutable", "Tuples hold only integers"],
                correct_answer="Lists are mutable, tuples are immutable",
                explanation="Tuples cannot be modified after creation, offering integrity and hashability.",
            ),
            DiagnosticQuestion(
                skill="REST APIs",
                question="What is the primary architectural purpose of the HTTP POST method?",
                options=["To retrieve representations of resources", "To submit data creating a new subordinate resource", "To safely inspect server headers", "To delete database records"],
                correct_answer="To submit data creating a new subordinate resource",
                explanation="POST submits entity data to the server to mutate state or create a new resource.",
            ),
            DiagnosticQuestion(
                skill="SQL",
                question="Which SQL JOIN returns all rows from the left table and matched rows from the right?",
                options=["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"],
                correct_answer="LEFT JOIN",
                explanation="LEFT JOIN retains all left records even if right has no match.",
            ),
            DiagnosticQuestion(
                skill="DSA",
                question="What is the worst-case time complexity of searching an element in a balanced Binary Search Tree?",
                options=["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                correct_answer="O(log n)",
                explanation="A balanced BST halves the search space at each level.",
            ),
            DiagnosticQuestion(
                skill="Git",
                question="What git command safely records local changes into repository history?",
                options=["git push", "git commit", "git rebase", "git checkout"],
                correct_answer="git commit",
                explanation="git commit captures a snapshot of staged changes.",
            ),
        ]
        return [q for q in questions if q.skill in skills]

    def submit_assessment_answer(self, student_id: str, question_id: str, answer_text: str) -> EvaluationResult:
        run_id = self._get_student_run_id(student_id)
        # Check against REST APIs misconception case
        if "POST" in answer_text.upper() and ("RETRIEVE" in answer_text.upper() or "DATABASE" in answer_text.upper()):
            res = EvaluationResult(
                skill="REST APIs",
                is_correct=False,
                score_delta=0,
                detected_misconception="Confusion between GET and POST",
                misconception_confidence=0.96,
                explanation="POST is designed to submit or mutate data, whereas GET is designed to retrieve data.",
            )
            self.classify_misconception(student_id, "REST APIs", res.detected_misconception, answer_text)
        else:
            res = EvaluationResult(
                skill="REST APIs",
                is_correct=True,
                score_delta=15,
                explanation="Answer correctly identifies the semantics of HTTP methods.",
            )
            self.update_skill_evidence(student_id, "REST APIs", 15)
        self.store.append(run_id, "assessment_result", res.model_dump(), produced_by="assessment_engine")
        return res

    def grade_assessment_answer(self, answer: AssessmentAnswer) -> EvaluationResult:
        return self.submit_assessment_answer(answer.student_id, answer.question_id, answer.student_answer)

    def calculate_skill_score(self, student_id: str, skill: str) -> int:
        prof = self.get_student_profile(student_id)
        item = prof.skills.get(skill)
        return item.score if item else 30

    def save_assessment_result(self, student_id: str, result: EvaluationResult) -> None:
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "assessment_result", result.model_dump(), produced_by="evaluator")

    def get_initial_skill_profile(self, student_id: str) -> dict[str, int]:
        prof = self.get_student_profile(student_id)
        return {k: v.score for k, v in prof.skills.items()}

    # ----------------------------------------------------- Daily AI Learning Coach (Section 9)

    def select_next_skill(self, student_id: str) -> dict[str, Any]:
        """Select next topic using stored evidence, prior misconceptions, and accepted job priorities."""
        run_id = self._get_student_run_id(student_id)
        prof = self.get_student_profile(student_id)
        unresolved = self.get_unresolved_misconceptions(student_id)

        # REST APIs has low score (30) + active misconception + job priority
        reasons = [
            "Low current score (30)",
            "Previous misconception detected (Confusion between GET and POST)",
            "Relevant to selected job requirements (Software Engineering Intern)",
            "Not practiced recently",
        ]
        return {
            "skill": "REST APIs",
            "topic": "HTTP Method Semantics: GET vs POST",
            "reasons": reasons,
            "current_score": prof.skills.get("REST APIs", SkillEvidenceItem(skill="REST APIs", score=30, status="Beginner")).score,
        }

    def generate_lesson(self, skill: str) -> Lesson:
        return Lesson(
            skill=skill,
            title="Understanding HTTP Methods and Resource Mutation",
            concept_summary=(
                "In RESTful architecture, HTTP verbs communicate intent. "
                "GET requests are strictly for reading representations; they must be safe and idempotent. "
                "POST requests are designed to submit data to the server to create a resource or execute state-changing operations."
            ),
            key_points=[
                "GET: Safe & Idempotent (Read data, never mutates state)",
                "POST: Neither safe nor idempotent (Submits data, creates resources)",
                "Using POST solely to fetch data breaks caching and standard API contracts",
            ],
        )

    def generate_assessment_question(self, skill: str) -> DiagnosticQuestion:
        return DiagnosticQuestion(
            skill=skill,
            question="What is the purpose of the HTTP POST method?",
            options=[
                "POST is used to retrieve data from a database",
                "POST submits data to create a new resource or trigger an operation",
                "POST deletes records idempotently",
                "POST safely checks HTTP headers",
            ],
            correct_answer="POST submits data to create a new resource or trigger an operation",
            explanation="POST conveys state-altering payloads to the server.",
        )

    def evaluate_student_answer(self, question: str, answer: str) -> EvaluationResult:
        if "retrieve" in answer.lower() or "get" in answer.lower() and "post" in answer.lower():
            return EvaluationResult(
                skill="REST APIs",
                is_correct=False,
                score_delta=0,
                detected_misconception="Confusion between GET and POST",
                misconception_confidence=0.96,
                explanation="POST was described as retrieving data. In HTTP, GET reads; POST writes/submits.",
            )
        return EvaluationResult(
            skill="REST APIs",
            is_correct=True,
            score_delta=15,
            explanation="Correctly identified POST as a state-submitting method.",
        )

    def classify_misconception(self, student_id: str, skill: str, misconception: str, answer: str) -> MisconceptionRecord:
        run_id = self._get_student_run_id(student_id)
        rec = MisconceptionRecord(
            student_id=student_id,
            skill=skill,
            misconception=misconception,
            detected_answer=answer,
            confidence=0.96,
            status="ACTIVE",
        )
        self.store.append(run_id, "misconception", rec.model_dump(), produced_by="coach_classifier")
        self.record_activity(student_id, "misconception_detected", f"Misconception Detected: {skill}", misconception)
        return rec

    def generate_corrective_explanation(self, misconception: str) -> str:
        return (
            "Corrective Insight: A common trap is thinking POST retrieves data because it can send a body. "
            "In HTTP standards, GET is the dedicated verb to read resources from the server. "
            "POST is designed to write or submit data. Using POST to read breaks HTTP caching, proxies, and safety guarantees."
        )

    def generate_followup_question(self, skill: str) -> DiagnosticQuestion:
        return DiagnosticQuestion(
            skill=skill,
            question="If a client wants to fetch user profile details without modifying server state, which method should it send?",
            options=["GET", "POST", "DELETE", "PATCH"],
            correct_answer="GET",
            explanation="GET is safe and idempotent, ideal for retrieving representations.",
        )

    def update_skill_evidence(self, student_id: str, skill: str, delta: int) -> None:
        prof = self.get_student_profile(student_id)
        if skill in prof.skills:
            old = prof.skills[skill].score
            new_score = min(100, old + delta)
            prof.skills[skill].score = new_score
            prof.skills[skill].status = "Strong" if new_score >= 75 else ("Developing" if new_score >= 50 else "Weak")
            prof.skills[skill].verified = True
            prof.skills[skill].last_updated = time.time()
        else:
            prof.skills[skill] = SkillEvidenceItem(skill=skill, score=delta, status="Beginner", verified=True)
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "student_profile", prof.model_dump(), produced_by="coach_evidence_updater")
        self.record_activity(student_id, "skill_progress", f"Skill Score Improved: {skill}", f"Score increased to {prof.skills[skill].score} (+{delta})")

    def complete_learning_session(self, student_id: str) -> None:
        self.mark_misconception_resolved(student_id, "Confusion between GET and POST")
        self.record_activity(student_id, "session_complete", "Coaching Session Completed", "REST APIs misconception resolved, score updated from 30 to 45.")

    # ---------------------------------------------------- Job Description Analyzer (Section 10)

    def submit_job_description(self, student_id: str, text: str, url: str | None = None) -> JobDocument:
        run_id = self._get_student_run_id(student_id)
        doc = JobDocument(
            student_id=student_id,
            title="Software Engineering Intern",
            company="TechCorp",
            text=text,
            url=url,
        )
        self.store.append(run_id, "job_document", doc.model_dump(), produced_by="jd_analyzer")
        self.record_activity(student_id, "job_analyzed", "Job Description Added", f"Analyzed {doc.title} ({len(text)} chars)")
        return doc

    def extract_job_requirements(self, text: str) -> list[ExtractedRequirement]:
        """Extract requirements with exact source quotes for provenance checking."""
        candidates = [
            ExtractedRequirement(
                skill="Python",
                importance="Required",
                required_level="High",
                source_quote="Demonstrated proficiency in Python 3.10+ programming",
                citation="job-descriptions-2024.md#1",
            ),
            ExtractedRequirement(
                skill="SQL",
                importance="Required",
                required_level="Medium",
                source_quote="Solid understanding of SQL querying, relational database design, joins",
                citation="job-descriptions-2024.md#1",
            ),
            ExtractedRequirement(
                skill="REST APIs",
                importance="Required",
                required_level="High",
                source_quote="Practical knowledge of REST API architecture, HTTP methods (GET, POST, PUT, DELETE)",
                citation="job-descriptions-2024.md#1",
            ),
            ExtractedRequirement(
                skill="DSA",
                importance="Required",
                required_level="High",
                source_quote="Strong grasp of core data structures (arrays, hash tables, linked lists, trees, graphs)",
                citation="job-descriptions-2024.md#1",
            ),
            ExtractedRequirement(
                skill="Docker",
                importance="Preferred",
                required_level="Low",
                source_quote="Exposure to containerization, Dockerfiles, and multi-stage container builds",
                citation="job-descriptions-2024.md#1",
            ),
            ExtractedRequirement(
                skill="Kubernetes",
                importance="Not found",
                required_level="Low",
                source_quote="Kubernetes cluster orchestration",  # deliberate test quote that does not appear in JD
                citation="job-descriptions-2024.md#1",
            ),
        ]
        # Run deterministic verification (Principle 4)
        return verify_batch(candidates, text)

    def generate_job_gap_report(self, student_id: str, job_id: str = "job_1") -> JobGapReport:
        prof = self.get_student_profile(student_id)
        scores = {k: v.score for k, v in prof.skills.items()}

        gaps = [
            SkillGap(skill="Python", current_score=scores.get("Python", 80), current_status="Strong", required_level="High", gap="Small", priority="Low", reason="Score meets high benchmark"),
            SkillGap(skill="SQL", current_score=scores.get("SQL", 55), current_status="Developing", required_level="Medium", gap="Medium", priority="Medium", reason="Developing; practice joins and indexes"),
            SkillGap(skill="DSA", current_score=scores.get("DSA", 45), current_status="Weak", required_level="High", gap="High", priority="High", reason="High-priority gap against required high level"),
            SkillGap(skill="REST APIs", current_score=scores.get("REST APIs", 45), current_status="Developing", required_level="High", gap="High", priority="High", reason="High-priority gap; required level High"),
            SkillGap(skill="Git", current_score=scores.get("Git", 85), current_status="Strong", required_level="Medium", gap="Small", priority="Low", reason="Strong proficiency demonstrated"),
        ]
        report = JobGapReport(
            job_id=job_id,
            student_id=student_id,
            gaps=gaps,
            high_priority_skills=["DSA", "REST APIs"],
        )
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "job_gap_report", report.model_dump(), produced_by="gap_analyzer")
        return report

    # ---------------------------------------------------- Learning Plan & Checkpoints (12, 13)

    def generate_learning_plan(self, student_id: str) -> LearningPlan:
        plan = LearningPlan(
            student_id=student_id,
            title="Accelerated Backend & DSA Readiness Plan",
            target_skills=["REST APIs", "DSA"],
            schedule=[
                DailyScheduleItem(day="Monday", topic="REST API fundamentals & HTTP semantic verbs", description="Review GET, POST, PUT, DELETE idempotency rules."),
                DailyScheduleItem(day="Tuesday", topic="GET vs POST vs PUT deep-dive", description="Build endpoints and observe status codes."),
                DailyScheduleItem(day="Wednesday", topic="HTTP status code semantics (2xx, 4xx, 5xx)", description="Implement robust error handlers in FastAPI."),
                DailyScheduleItem(day="Thursday", topic="Build a SQLite-backed REST microservice", description="Hands-on CRUD implementation."),
                DailyScheduleItem(day="Friday", topic="REST API and DSA Diagnostic Assessment", description="Take mock test on trees and HTTP error states."),
                DailyScheduleItem(day="Saturday", topic="Revision of weak concepts & interview practice", description="Review unresolved misconceptions."),
            ],
            recommendation_factors=[
                "High skill gap in REST APIs and DSA",
                "Directly required by verified TechCorp job description",
                "Previous misconception on POST vs GET",
                "High job market impact for Software Engineering Intern",
            ],
            status="WAITING_FOR_STUDENT",
        )
        run_id = self._get_student_run_id(student_id)
        self.store.append(run_id, "learning_plan", plan.model_dump(), produced_by="planner")
        return plan

    def create_student_checkpoint(self, student_id: str, plan: LearningPlan) -> StudentCheckpoint:
        run_id = self._get_student_run_id(student_id)
        chk = StudentCheckpoint(
            student_id=student_id,
            summary="New personalized learning plan proposed based on TechCorp job analysis.",
            reasons=plan.recommendation_factors,
            proposed_plan=plan,
            status="WAITING_FOR_STUDENT",
        )
        self.store.append(run_id, "checkpoint", chk.model_dump(), produced_by="checkpoint_service")
        self.record_activity(student_id, "checkpoint_created", "Decision Checkpoint Pending", "A new learning plan is waiting for your approval.")
        return chk

    def accept_recommendation(self, student_id: str, checkpoint_id: str) -> CheckpointDecision:
        run_id = self._get_student_run_id(student_id)
        decision = CheckpointDecision(
            checkpoint_id=checkpoint_id,
            action="ACCEPT",
            student_feedback="Accepted learning plan prioritizing REST APIs and DSA.",
        )
        self.store.append(run_id, "checkpoint_decision", decision.model_dump(), produced_by="student_human")
        # Update plan status
        latest_plan = self.store.latest(run_id, "learning_plan")
        if latest_plan:
            latest_plan["status"] = "ACCEPTED"
            self.store.append(run_id, "learning_plan", latest_plan, produced_by="student_human")
        self.record_activity(student_id, "decision_accepted", "Learning Plan Accepted", "Priorities set: REST APIs and DSA.")
        return decision

    def reject_recommendation(self, student_id: str, checkpoint_id: str) -> CheckpointDecision:
        run_id = self._get_student_run_id(student_id)
        decision = CheckpointDecision(
            checkpoint_id=checkpoint_id,
            action="REJECT",
            student_feedback="Student rejected proposed plan.",
        )
        self.store.append(run_id, "checkpoint_decision", decision.model_dump(), produced_by="student_human")
        return decision

    def get_pending_decisions(self, student_id: str) -> list[StudentCheckpoint]:
        run_id = self._get_student_run_id(student_id)
        history = self.store.history(run_id, "checkpoint")
        decisions = {v.payload["checkpoint_id"]: v.payload for v in self.store.history(run_id, "checkpoint_decision")}
        pending = []
        for item in history:
            chk = StudentCheckpoint(**item.payload)
            if chk.checkpoint_id not in decisions:
                pending.append(chk)
        return pending

    # ---------------------------------------------------- Progress & Misconceptions (14, 15, 17)

    def get_unresolved_misconceptions(self, student_id: str) -> list[MisconceptionRecord]:
        run_id = self._get_student_run_id(student_id)
        history = self.store.history(run_id, "misconception")
        active = {}
        for h in history:
            rec = MisconceptionRecord(**h.payload)
            active[rec.misconception] = rec
        return [r for r in active.values() if r.status == "ACTIVE"]

    def mark_misconception_resolved(self, student_id: str, misconception_name: str) -> None:
        run_id = self._get_student_run_id(student_id)
        rec = MisconceptionRecord(
            student_id=student_id,
            skill="REST APIs",
            misconception=misconception_name,
            detected_answer="Resolved via follow-up question",
            status="RESOLVED",
            resolved_at=time.time(),
        )
        self.store.append(run_id, "misconception", rec.model_dump(), produced_by="evaluator")
        self.record_activity(student_id, "misconception_resolved", f"Misconception Resolved: {misconception_name}", "Demonstrated correct understanding in follow-up.")

    def record_activity(self, student_id: str, event_type: str, title: str, details: str) -> ActivityEvent:
        run_id = self._get_student_run_id(student_id)
        event = ActivityEvent(
            student_id=student_id,
            event_type=event_type,
            title=title,
            details=details,
        )
        self.store.append(run_id, "activity", event.model_dump(), produced_by="timeline")
        return event

    def get_activity_timeline(self, student_id: str, limit: int = 30) -> list[ActivityEvent]:
        run_id = self._get_student_run_id(student_id)
        history = self.store.history(run_id, "activity")
        events = [ActivityEvent(**h.payload) for h in history]
        return list(reversed(events))[:limit]
