import json
import logging
from typing import List, Dict, Any, Optional
from app.schemas.interview import (
    RoadmapItemSchema,
    RoadmapPhaseSchema,
    RoadmapResponse,
    InterviewScoreResponse,
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
)

logger = logging.getLogger("roadmap_service")

class PersonalizedRoadmapService:
    """
    Constructs a structured, measurable, 5-phase placement improvement roadmap
    connecting identified candidate weaknesses, skill gaps, and interview metrics.
    """

    @classmethod
    def generate_roadmap(
        cls,
        interview_id: int,
        user_id: int,
        score_data: InterviewScoreResponse,
        skill_match: Optional[SkillMatchSchema] = None,
        weaknesses: Optional[List[str]] = None,
        mistakes: Optional[List[Dict[str, Any]]] = None,
        job_role: Optional[str] = None
    ) -> RoadmapResponse:
        phases: List[RoadmapPhaseSchema] = []

        gaps = skill_match.skill_gaps if skill_match else []
        priority_gaps = skill_match.priority_skills if skill_match else []
        role_title = job_role or "Target Software Engineering Role"

        # -------------------------------------------------------------
        # PHASE 1: Immediate Improvement (Days 1 - 3)
        # -------------------------------------------------------------
        phase1_items: List[RoadmapItemSchema] = []
        fluency_raw = score_data.dimensions.get("fluency", {}).raw_score if hasattr(score_data.dimensions.get("fluency"), "raw_score") else 75.0

        if fluency_raw < 80.0 or any("filler" in (w or "").lower() for w in (weaknesses or [])):
            phase1_items.append(
                RoadmapItemSchema(
                    area="Speech Fluency & Hesitation Control",
                    problem="Elevated frequency of filler words ('um', 'like', 'actually') during technical explanations.",
                    recommended_action="Practice 2-second deliberate pauses before answering rather than filling silence with vocal disfluencies.",
                    practice_task="Record 3 daily two-minute audio answers explaining core project components with zero filler words.",
                    priority="High",
                    estimated_duration="3 days",
                    measurable_target="Reduce filler word count by at least 50% in subsequent speech recordings."
                )
            )

        phase1_items.append(
            RoadmapItemSchema(
                area="Answer Structuring (STAR Method)",
                problem="Responses to project and situational questions lack clear delineation between Situation, Task, Action, and Result.",
                recommended_action="Frame all project discussions with explicit context: Problem Context (15%), Architecture/Action (60%), Business/Performance Result (25%).",
                practice_task="Write out bulleted STAR frameworks for your top 2 resume projects.",
                priority="High",
                estimated_duration="2 days",
                measurable_target="Achieve structured 2-minute project pitch covering technical challenges and measurable impact."
            )
        )

        phases.append(
            RoadmapPhaseSchema(
                phase_number=1,
                phase_title="Phase 1 — Immediate Improvement",
                focus_objective="Eliminate conversational friction, calibrate pacing, and structure technical answers cleanly.",
                items=phase1_items
            )
        )

        # -------------------------------------------------------------
        # PHASE 2: Technical Competency & Skill Gap Remediation (Days 4 - 14)
        # -------------------------------------------------------------
        phase2_items: List[RoadmapItemSchema] = []

        if gaps:
            primary_gap = gaps[0]
            phase2_items.append(
                RoadmapItemSchema(
                    area=f"Target Requirement Mastery ({primary_gap})",
                    problem=f"The target JD highlights {primary_gap} as a key requirement, which was missing or lightly represented in your profile.",
                    recommended_action=f"Deep-dive into {primary_gap} core architecture, lifecycle management, and standard production design patterns.",
                    practice_task=f"Build a standalone prototype or microservice integrating {primary_gap} with automated test coverage.",
                    priority="High",
                    estimated_duration="7 days",
                    measurable_target=f"Be able to authoritatively explain {primary_gap} trade-offs and best practices in technical deep-dives."
                )
            )

        tech_raw = score_data.dimensions.get("technical", {}).raw_score if hasattr(score_data.dimensions.get("technical"), "raw_score") else 75.0
        if tech_raw < 85.0:
            phase2_items.append(
                RoadmapItemSchema(
                    area="System Design & Concurrency Trade-offs",
                    problem="Explanations of database transactions, scaling bottlenecks, and indexing lacked depth on edge cases.",
                    recommended_action="Review database transaction isolation levels (ACID), indexing mechanisms (B-Tree vs Hash), and caching strategies (Redis).",
                    practice_task="Design an end-to-end scalable architecture diagram for a high-traffic microservice handling 10k requests/sec.",
                    priority="Medium",
                    estimated_duration="5 days",
                    measurable_target="Score 85%+ on technical depth and architecture questions."
                )
            )

        if not phase2_items:
            phase2_items.append(
                RoadmapItemSchema(
                    area="Advanced Algorithms & Optimization",
                    problem="Maintain mastery of time and space complexity trade-offs for placement coding rounds.",
                    recommended_action="Practice medium/hard graph, dynamic programming, and concurrency problems.",
                    practice_task="Solve and verbally explain 10 placement-level algorithmic problems.",
                    priority="Medium",
                    estimated_duration="7 days",
                    measurable_target="Verbalize time/space complexity within 30 seconds of problem review."
                )
            )

        phases.append(
            RoadmapPhaseSchema(
                phase_number=2,
                phase_title="Phase 2 — Technical Improvement",
                focus_objective=f"Bridge skill gaps required for {role_title} and master architectural trade-offs.",
                items=phase2_items
            )
        )

        # -------------------------------------------------------------
        # PHASE 3: Communication & Articulation (Days 15 - 21)
        # -------------------------------------------------------------
        phase3_items: List[RoadmapItemSchema] = []
        phase3_items.append(
            RoadmapItemSchema(
                area="Domain Vocabulary & Articulation",
                problem="Use of casual phrasing rather than precise software engineering terminology during technical explanations.",
                recommended_action="Incorporate industry-standard terminology (e.g. idempotent, decoupling, asynchronous concurrency, normalization).",
                practice_task="Explain 5 complex technical concepts aloud daily using precise engineering terms.",
                priority="Medium",
                estimated_duration="5 days",
                measurable_target="Increase vocabulary and lexical diversity score above 85%."
            )
        )

        phases.append(
            RoadmapPhaseSchema(
                phase_number=3,
                phase_title="Phase 3 — Communication Improvement",
                focus_objective="Elevate technical communication, professional vocabulary, and concise articulation.",
                items=phase3_items
            )
        )

        # -------------------------------------------------------------
        # PHASE 4: Simulated Placement Practice (Days 22 - 28)
        # -------------------------------------------------------------
        phase4_items: List[RoadmapItemSchema] = []
        phase4_items.append(
            RoadmapItemSchema(
                area="Targeted Mock Interview Simulation",
                problem="Need realistic under-pressure rehearsal against adaptive follow-up questions.",
                recommended_action=f"Conduct 3 full 30-minute AI voice mock interviews tailored for {role_title}.",
                practice_task="Complete 2 company-specific mock interviews and 1 general placement interview.",
                priority="High",
                estimated_duration="7 days",
                measurable_target="Complete 3 mock sessions with average overall score exceeding 85%."
            )
        )

        phases.append(
            RoadmapPhaseSchema(
                phase_number=4,
                phase_title="Phase 4 — Interview Practice",
                focus_objective="Simulate full-length placement rounds under adaptive questioning conditions.",
                items=phase4_items
            )
        )

        # -------------------------------------------------------------
        # PHASE 5: Final Reassessment & Benchmarking (Day 29+)
        # -------------------------------------------------------------
        target_score = min(95.0, round(score_data.overall_score + 12.0, 1))
        phase5_items: List[RoadmapItemSchema] = []
        phase5_items.append(
            RoadmapItemSchema(
                area="Final Benchmark & Placement Readiness",
                problem="Confirm retention of technical depth, fluency, and eliminated skill gaps.",
                recommended_action="Execute final comprehensive mock interview session and review comparison metrics.",
                practice_task="Complete final benchmark mock interview session.",
                priority="High",
                estimated_duration="1 day",
                measurable_target=f"Achieve an Overall Score of {target_score}%+ with 'Very Good' or 'Excellent' Readiness Level."
            )
        )

        phases.append(
            RoadmapPhaseSchema(
                phase_number=5,
                phase_title="Phase 5 — Reassessment",
                focus_objective="Validate score improvements and certify placement drive readiness.",
                items=phase5_items
            )
        )

        return RoadmapResponse(
            interview_id=interview_id,
            user_id=user_id,
            overall_score=score_data.overall_score,
            readiness_level=score_data.readiness_level,
            phases=phases,
            created_at=""
        )
