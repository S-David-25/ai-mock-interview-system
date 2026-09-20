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
        job_role: Optional[str] = None,
        previous_scores: Optional[Dict[str, float]] = None
    ) -> RoadmapResponse:
        phases: List[RoadmapPhaseSchema] = []

        role_title = job_role or "Target Software Engineering Role"
        weaknesses = weaknesses or []
        mistakes = mistakes or []
        technical = score_data.dimensions.get("technical")
        communication = score_data.dimensions.get("communication")
        fluency = score_data.dimensions.get("fluency")
        tech_raw = technical.raw_score if technical else 0.0
        comm_raw = communication.raw_score if communication else 0.0
        fluency_raw = fluency.raw_score if fluency else 0.0

        # -------------------------------------------------------------
        # PHASE 1: Immediate Improvement (Days 1 - 3)
        # -------------------------------------------------------------
        phase1_items: List[RoadmapItemSchema] = []
        filler_mistake = next((m for m in mistakes if "filler" in m.get("mistake_type", "").lower()), None)
        if filler_mistake:
            phase1_items.append(
                RoadmapItemSchema(
                    area="Speech Fluency & Hesitation Control",
                    problem=filler_mistake["description"],
                    recommended_action="Practice 2-second deliberate pauses before answering rather than filling silence with vocal disfluencies.",
                    practice_task="Record 3 daily two-minute audio answers explaining core project components with zero filler words.",
                    priority="High",
                    estimated_duration="3 days",
                    measurable_target=f"Reduce the observed filler count of {filler_mistake['frequency']} by at least 50% in the next interview."
                )
            )

        for weakness in weaknesses[:2]:
            if "filler" not in weakness.lower() and not any(weakness == item.problem for item in phase1_items):
                phase1_items.append(RoadmapItemSchema(
                    area="Immediate Interview Gap",
                    problem=weakness,
                    recommended_action="Review the answer evidence and use a written outline before responding.",
                    practice_task="Record one two-minute answer targeting this gap and compare it with the original transcript.",
                    priority="High",
                    estimated_duration="3 days",
                    measurable_target="Show a clear improvement on this same dimension in the next mock interview."
                ))
        if not phase1_items:
            phase1_items.append(RoadmapItemSchema(
                area="Evidence Review",
                problem="No recurring immediate weakness was identified in the available interview evidence.",
                recommended_action="Review the question transcripts and preserve the answer structure that produced the current result.",
                practice_task="Re-record one representative answer and compare its clarity and completeness with this interview.",
                priority="Low",
                estimated_duration="3 days",
                measurable_target="Maintain or improve the same measurable dimensions in the next interview."
            ))

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

        if skill_match and skill_match.skill_gaps:
            primary_gap = skill_match.skill_gaps[0]
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

        if tech_raw < 75.0:
            phase2_items.append(
                RoadmapItemSchema(
                    area="System Design & Concurrency Trade-offs",
                    problem=next((w for w in weaknesses if "technical" in w.lower() or "architect" in w.lower() or "depth" in w.lower()), "Technical answers scored below the evidence-based improvement threshold."),
                    recommended_action="Revisit the concepts named in the question feedback and explain their trade-offs from first principles.",
                    practice_task="Solve and verbally explain three technical questions from the topics present in this interview.",
                    priority="Medium",
                    estimated_duration="5 days",
                    measurable_target=f"Improve the technical score from {tech_raw:.1f}% in the next interview."
                )
            )

        if not phase2_items:
            phase2_items.append(
                RoadmapItemSchema(
                    area="Advanced Algorithms & Optimization",
                    problem="No technical weakness was identified from the recorded answers.",
                    recommended_action="Maintain the technical level demonstrated in this interview.",
                    practice_task="Revisit the technical questions answered here and verify each explanation against official documentation.",
                    priority="Medium",
                    estimated_duration="7 days",
                    measurable_target=f"Maintain a technical score at or above {tech_raw:.1f}% in the next interview."
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
        if comm_raw < 75.0:
            phase3_items.append(RoadmapItemSchema(
                area="Communication Clarity",
                problem=next((w for w in weaknesses if "communication" in w.lower() or "phrasing" in w.lower() or "terminology" in w.lower()), "Communication score was below the evidence-based improvement threshold."),
                recommended_action="Use a short context, action, result structure and replace vague wording with terms from the answer feedback.",
                practice_task="Give five timed explanations of concepts covered in this interview and transcribe them for review.",
                priority="High",
                estimated_duration="5 days",
                measurable_target=f"Improve communication from {comm_raw:.1f}% in the next interview."
            ))
        if fluency_raw < 75.0 and not filler_mistake:
            phase3_items.append(RoadmapItemSchema(
                area="Speech Delivery",
                problem="Fluency score was below the evidence-based improvement threshold.",
                recommended_action="Practice steady pacing and deliberate pauses while answering the same question types.",
                practice_task="Record three timed answers and review pace, pauses, and sentence completion.",
                priority="Medium",
                estimated_duration="5 days",
                measurable_target=f"Improve fluency from {fluency_raw:.1f}% in the next interview."
            ))
        if not phase3_items:
            phase3_items.append(RoadmapItemSchema(
                area="Communication Maintenance",
                problem="No recurring communication weakness was identified in the available transcripts.",
                recommended_action="Maintain the clarity and pacing demonstrated in this interview.",
                practice_task="Rehearse one answer from this interview using the same structure and timing.",
                priority="Low",
                estimated_duration="5 days",
                measurable_target=f"Maintain communication at or above {comm_raw:.1f}% in the next interview."
            ))

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
                    problem="Practice should target the question types and weaknesses observed in this interview.",
                recommended_action=f"Conduct 3 full 30-minute AI voice mock interviews tailored for {role_title}.",
                practice_task="Complete 2 company-specific mock interviews and 1 general placement interview.",
                priority="High",
                estimated_duration="7 days",
                    measurable_target="Complete one mock interview and compare the same displayed metrics with this session."
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
        phase5_items: List[RoadmapItemSchema] = []
        if previous_scores:
            previous_overall = previous_scores.get("overall_score", 0.0)
            change = round(score_data.overall_score - previous_overall, 1)
            target = f"Previous overall score {previous_overall:.1f}%; current score {score_data.overall_score:.1f}% ({change:+.1f} points)."
        else:
            target = "No previous completed interview was available; establish this interview as the baseline."
        phase5_items.append(
            RoadmapItemSchema(
                area="Final Benchmark & Placement Readiness",
                problem=target,
                recommended_action="Execute final comprehensive mock interview session and review comparison metrics.",
                practice_task="Complete final benchmark mock interview session.",
                priority="High",
                estimated_duration="1 day",
                measurable_target="Complete another mock interview and recalculate the same technical, communication, fluency, vision, and overall metrics."
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
