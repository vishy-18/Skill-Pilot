"""Typed contracts at every boundary for Cognitive Career Navigator (Skill-Pilot).

Adheres to Principle 2 (docs/ARCHITECTURE.md:88):
- Every step produces and consumes a Pydantic model, never loose prose.
- Models wrap lists so schemas enforce bounds and repair passes have unambiguous targets.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field


def gen_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ------------------------------------------------------------------- Auth & Profile

class StudentRegistration(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=120)
    college: str = Field(min_length=2, max_length=150)
    department: str = Field(min_length=2, max_length=100)
    graduation_year: int = Field(ge=2024, le=2032)
    password: str = Field(min_length=4)


class Student(BaseModel):
    student_id: str = Field(default_factory=lambda: gen_id("std"))
    name: str
    email: str
    password_hash: str
    college: str
    department: str
    graduation_year: int
    created_at: float = Field(default_factory=time.time)


class ProjectEvidence(BaseModel):
    id: str = Field(default_factory=lambda: gen_id("proj"))
    title: str
    description: str
    skills_used: list[str] = Field(default_factory=list)
    github_url: str = ""
    verified: bool = False


class CertificateEvidence(BaseModel):
    id: str = Field(default_factory=lambda: gen_id("cert"))
    name: str
    issuer: str
    date_issued: str
    credential_id: str = ""


class SkillEvidenceItem(BaseModel):
    skill: str
    score: int = Field(ge=0, le=100)
    status: Literal["Strong", "Developing", "Weak", "Beginner"]
    evidence_type: Literal["self_reported", "assessment", "project", "verified_learning"] = "assessment"
    verified: bool = False
    source_notes: str = ""
    last_updated: float = Field(default_factory=time.time)


class StudentProfile(BaseModel):
    student_id: str
    name: str
    college: str
    department: str
    graduation_year: int
    skills: dict[str, SkillEvidenceItem] = Field(default_factory=dict)
    projects: list[ProjectEvidence] = Field(default_factory=list)
    certifications: list[CertificateEvidence] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    completion_pct: int = 80


# ------------------------------------------------------------------- Career Goals

class CareerGoal(BaseModel):
    id: str = Field(default_factory=lambda: gen_id("goal"))
    student_id: str
    role: str
    is_primary: bool = True
    target_skills: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --------------------------------------------------------------- Assessment & Misconceptions

class DiagnosticQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: gen_id("q"))
    skill: str
    question: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str = ""


class AssessmentAnswer(BaseModel):
    student_id: str
    question_id: str
    skill: str
    student_answer: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EvaluationResult(BaseModel):
    skill: str
    is_correct: bool
    score_delta: int
    detected_misconception: str | None = None
    misconception_confidence: float = 0.0
    explanation: str = ""


class MisconceptionRecord(BaseModel):
    id: str = Field(default_factory=lambda: gen_id("misc"))
    student_id: str
    skill: str
    misconception: str
    detected_answer: str
    confidence: float = 0.95
    status: Literal["ACTIVE", "RESOLVED", "UNRESOLVED"] = "ACTIVE"
    attempts_count: int = 1
    detected_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


# ------------------------------------------------------------------- AI Learning Coach

class Lesson(BaseModel):
    skill: str
    title: str
    concept_summary: str
    key_points: list[str] = Field(default_factory=list)


class FollowupQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: gen_id("fq"))
    skill: str
    misconception_targeted: str
    question: str
    expected_concept: str


# ------------------------------------------------------------- Job Description & Citations

class ExtractedRequirement(BaseModel):
    skill: str
    importance: Literal["Required", "Preferred", "Not found"] = "Required"
    required_level: Literal["High", "Medium", "Low"] = "Medium"
    source_quote: str = ""
    citation: str = ""
    verification_status: Literal["Verified", "Unverified", "Excluded"] = "Unverified"
    verification_note: str = ""


class ExtractedRequirementsBatch(BaseModel):
    """Wrapper to enforce bounding on LLM extraction outputs (docs/ARCHITECTURE.md:150)."""
    items: list[ExtractedRequirement] = Field(min_length=1, max_length=12)


class JobDocument(BaseModel):
    job_id: str = Field(default_factory=lambda: gen_id("job"))
    student_id: str
    title: str
    company: str
    text: str
    url: str | None = None
    created_at: float = Field(default_factory=time.time)


# -------------------------------------------------------------- Skill Gap & Learning Plan

class SkillGap(BaseModel):
    skill: str
    current_score: int
    current_status: Literal["Strong", "Developing", "Weak", "Beginner"]
    required_level: Literal["High", "Medium", "Low"]
    gap: Literal["Small", "Medium", "High"]
    priority: Literal["High", "Medium", "Low"]
    reason: str = ""


class JobGapReport(BaseModel):
    report_id: str = Field(default_factory=lambda: gen_id("gap"))
    job_id: str
    student_id: str
    gaps: list[SkillGap] = Field(default_factory=list)
    high_priority_skills: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class DailyScheduleItem(BaseModel):
    day: str
    topic: str
    description: str


class LearningPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: gen_id("plan"))
    student_id: str
    title: str
    target_skills: list[str] = Field(default_factory=list)
    schedule: list[DailyScheduleItem] = Field(default_factory=list)
    recommendation_factors: list[str] = Field(default_factory=list)
    status: Literal["WAITING_FOR_STUDENT", "ACCEPTED", "MODIFIED", "REJECTED"] = "WAITING_FOR_STUDENT"
    created_at: float = Field(default_factory=time.time)


# ------------------------------------------------------------- Human Approval Checkpoint

class StudentCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: gen_id("chk"))
    student_id: str
    recommendation_type: str = "learning_plan_update"
    summary: str
    reasons: list[str] = Field(default_factory=list)
    proposed_plan: LearningPlan | None = None
    status: Literal["WAITING_FOR_STUDENT", "ACCEPTED", "MODIFIED", "REJECTED"] = "WAITING_FOR_STUDENT"
    created_at: float = Field(default_factory=time.time)


class CheckpointDecision(BaseModel):
    checkpoint_id: str
    action: Literal["ACCEPT", "MODIFY", "REJECT"]
    student_feedback: str = ""
    timestamp: float = Field(default_factory=time.time)


# ------------------------------------------------------------- Activity Timeline & Events

class ActivityEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: gen_id("act"))
    student_id: str
    event_type: str
    title: str
    details: str
    timestamp: float = Field(default_factory=time.time)
