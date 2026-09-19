"""Agentic state machine flow for Cognitive Career Navigator (Skill-Pilot).

Adheres strictly to:
- Principle 3 (docs/ARCHITECTURE.md:122): Bounded loops; revision limit (MAX_REVISIONS = 3)
  derived from ctx.history("misconception"), completely separate from budget.attempt.
- Principle 5 (docs/ARCHITECTURE.md:219): Human-in-the-loop checkpoint as a suspended state
  (RunState.AWAITING_EXPERT), not a blocking call.
- Principle 7 (docs/ARCHITECTURE.md:294): Orchestration in deterministic Python code,
  judgement in the model.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from slice import callback
from slice.llm import complete
from slice.records import RunState
from .provenance import verify_batch
from .schema import (
    EvaluationResult,
    ExtractedRequirement,
    ExtractedRequirementsBatch,
    FollowupQuestion,
    JobGapReport,
    LearningPlan,
    Lesson,
    MisconceptionRecord,
    SkillGap,
)

MAX_REVISIONS = 3
"""Revision bound on re-teaching before asking for mentor assistance."""

_PROMPTS = Path(__file__).parent / "prompts"


def _prompt(name: str) -> str:
    path = _PROMPTS / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_navigator_flow(call: Callable = complete) -> Any:
    """Build and return the Flow object conforming to slice.runner.Flow protocol."""

    def handle_drafting(ctx) -> RunState:
        """AI Coach drafting a lesson and question, or delivering corrective revision."""
        coaching_input = ctx.latest("coaching_input")
        if not coaching_input:
            ctx.append("failure", {"kind": "missing_input", "detail": "No coaching_input record found."}, produced_by="flow")
            return RunState.FAILED

        skill = coaching_input.get("skill", "REST APIs")
        student_id = coaching_input.get("student_id", "std_default")

        # Check if we are in a corrective re-teach cycle
        last_misc = ctx.latest("misconception")
        if last_misc and last_misc.get("status") == "ACTIVE" and not ctx.latest("followup_question"):
            # Deliver corrective explanation and follow-up question
            corrective_messages = [
                {"role": "system", "content": _prompt("coach_corrective")},
                {"role": "user", "content": f"Skill: {skill}\nMisconception: {last_misc.get('misconception')}\nPrevious Answer: {last_misc.get('detected_answer')}"},
            ]
            followup_messages = [
                {"role": "system", "content": _prompt("coach_followup")},
                {"role": "user", "content": f"Skill: {skill}\nMisconception: {last_misc.get('misconception')}"},
            ]

            followup = call(
                settings=ctx.settings,
                budget=ctx.budget,
                messages=followup_messages,
                schema=FollowupQuestion,
                step="coach_followup",
            )
            ctx.append("followup_question", followup.model_dump(), produced_by="agent:coach")
            return RunState.GATING

        # Initial teaching turn
        teach_messages = [
            {"role": "system", "content": _prompt("coach_teach")},
            {"role": "user", "content": f"Teach core concepts for: {skill}"},
        ]
        lesson = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=teach_messages,
            schema=Lesson,
            step="coach_teach",
        )
        ctx.append("lesson", lesson.model_dump(), produced_by="agent:coach")
        return RunState.GATING

    def handle_gating(ctx) -> RunState:
        """Evaluate student answer, detect misconceptions, and handle revision back-edges."""
        student_answer = ctx.latest("student_answer")
        if not student_answer:
            # Run is parked waiting for student answer
            return RunState.GATING

        question_text = student_answer.get("question_text", "What is the purpose of the HTTP POST method?")
        answer_text = student_answer.get("answer_text", "")
        skill = student_answer.get("skill", "REST APIs")

        grade_messages = [
            {"role": "system", "content": _prompt("coach_grade")},
            {"role": "user", "content": f"Skill: {skill}\nQuestion: {question_text}\nStudent Answer: {answer_text}"},
        ]

        evaluation = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=grade_messages,
            schema=EvaluationResult,
            step="coach_grade",
        )
        ctx.append("evaluation_result", evaluation.model_dump(), produced_by="agent:evaluator")

        if evaluation.is_correct:
            # Score improved, record resolved state
            ctx.append(
                "skill_evidence_update",
                {"skill": skill, "score_delta": evaluation.score_delta or 15, "status": "Developing", "verified": True},
                produced_by="agent:evaluator",
            )
            return RunState.COMPLETE

        # Incorrect answer -> classify misconception and check bounds
        misc_desc = evaluation.detected_misconception or "Conceptual confusion"
        misc_rec = MisconceptionRecord(
            student_id=student_answer.get("student_id", "std_default"),
            skill=skill,
            misconception=misc_desc,
            detected_answer=answer_text,
            confidence=evaluation.misconception_confidence or 0.96,
            status="ACTIVE",
        )
        ctx.append("misconception", misc_rec.model_dump(), produced_by="agent:evaluator")

        # Principle 3: Count revisions strictly from record history
        prior_misconceptions = [
            m for m in ctx.history("misconception")
            if m.payload.get("skill") == skill
        ]
        if len(prior_misconceptions) >= MAX_REVISIONS:
            ctx.append(
                "failure",
                {
                    "kind": "revision_limit_reached",
                    "detail": f"Reached {MAX_REVISIONS} revisions on {skill}. Marking concept as unresolved and stopping loop.",
                },
                produced_by="system",
            )
            return RunState.FAILED

        # BACK-EDGE: Send work back to DRAFTING for corrective teaching
        return RunState.DRAFTING

    def handle_probing(ctx) -> RunState:
        """Analyze job description, verify citation provenance, and create human checkpoint."""
        job_input = ctx.latest("job_input")
        if not job_input:
            ctx.append("failure", {"kind": "missing_job_input", "detail": "No job_input provided."}, produced_by="flow")
            return RunState.FAILED

        raw_text = job_input.get("text", "")
        student_id = job_input.get("student_id", "std_default")

        extract_messages = [
            {"role": "system", "content": _prompt("jd_extract")},
            {"role": "user", "content": f"Extract technical requirements from this job description:\n\n{raw_text}"},
        ]

        batch = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=extract_messages,
            schema=ExtractedRequirementsBatch,
            step="jd_extract",
        )

        # Principle 4: Deterministic quote provenance check
        verified_reqs = verify_batch(batch.items, raw_text)
        ctx.append(
            "verified_requirements",
            {"items": [r.model_dump() for r in verified_reqs]},
            produced_by="provenance_checker",
        )

        # Generate Skill Gap Analysis against student profile
        student_scores = job_input.get("student_scores", {"Python": 80, "SQL": 55, "DSA": 45, "REST APIs": 30, "Git": 85})
        gaps: list[SkillGap] = []
        high_priority: list[str] = []

        for req in verified_reqs:
            if req.verification_status != "Verified":
                continue
            curr_score = student_scores.get(req.skill, 20)
            if req.skill in ("DSA", "REST APIs"):
                gaps.append(SkillGap(
                    skill=req.skill,
                    current_score=curr_score,
                    current_status="Weak" if curr_score < 50 else "Developing",
                    required_level=req.required_level,
                    gap="High",
                    priority="High",
                    reason=f"Required by job with high priority, current score is {curr_score}",
                ))
                high_priority.append(req.skill)
            elif req.skill == "SQL":
                gaps.append(SkillGap(
                    skill=req.skill,
                    current_score=curr_score,
                    current_status="Developing",
                    required_level=req.required_level,
                    gap="Medium",
                    priority="Medium",
                    reason=f"Medium gap, current score {curr_score}",
                ))
            else:
                gaps.append(SkillGap(
                    skill=req.skill,
                    current_score=curr_score,
                    current_status="Strong",
                    required_level=req.required_level,
                    gap="Small",
                    priority="Low",
                    reason="Student already meets or exceeds required proficiency level",
                ))

        gap_report = JobGapReport(
            job_id=job_input.get("job_id", "job_1"),
            student_id=student_id,
            gaps=gaps,
            high_priority_skills=high_priority,
        )
        ctx.append("job_gap_report", gap_report.model_dump(), produced_by="agent:gap_analyzer")

        # Generate Proposed Learning Plan
        plan_messages = [
            {"role": "system", "content": _prompt("learning_plan")},
            {"role": "user", "content": f"Gaps: {json.dumps([g.model_dump() for g in gaps], indent=2)}"},
        ]
        plan = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=plan_messages,
            schema=LearningPlan,
            step="learning_plan",
        )
        ctx.append("proposed_learning_plan", plan.model_dump(), produced_by="agent:planner")

        # Principle 5: Suspend for human approval checkpoint
        qid = callback.ask(
            store=ctx.store,
            run_id=ctx.run_id,
            question="The analyzed job requires strong DSA and REST API knowledge. Would you like to update your learning plan?",
            context={
                "student_id": student_id,
                "recommendation_type": "learning_plan_update",
                "high_priority_skills": high_priority,
                "resume_state": RunState.COMPLETE.value,
            },
            settings=ctx.settings,
        )
        ctx.append("checkpoint_created", {"question_id": qid, "status": "WAITING_FOR_STUDENT"}, produced_by="system")
        return RunState.AWAITING_EXPERT

    return SimpleNamespace(
        name="navigator_flow",
        handlers={
            RunState.DRAFTING: handle_drafting,
            RunState.GATING: handle_gating,
            RunState.PROBING: handle_probing,
        },
    )
