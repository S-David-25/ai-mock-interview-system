import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.database.session import DatabaseSession
from app.models.interview import Interview, InterviewQuestion, InterviewAnswer, AnswerAnalysis, BehaviorAnalysis
from app.schemas.interview import (
    PerformanceReportResponse,
    InterviewScoreResponse,
    CategoryRatingSchema,
    MistakeItemSchema,
    QuestionBreakdownSchema,
    RoadmapResponse,
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
)
from app.services.scoring_service import MultiModalScoringService
from app.services.roadmap_service import PersonalizedRoadmapService

logger = logging.getLogger("report_service")

class PerformanceReportService:
    """
    Synthesizes interview metrics, answer evaluations, computer vision indicators,
    and skill gap analyses into a comprehensive, explainable performance report and roadmap.
    """

    @classmethod
    def generate_and_save_report(
        cls,
        db: DatabaseSession,
        interview_id: int,
        user_id: int
    ) -> PerformanceReportResponse:
        # 1. Fetch Interview and verify ownership
        int_row = db.fetchone(
            "SELECT * FROM interviews WHERE id = ? AND user_id = ?",
            (interview_id, user_id)
        )
        if not int_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found or you do not have permission to access it."
            )

        interview = Interview.from_row(int_row)

        # 2. Fetch all Question, Answer, and Analysis records
        questions_raw = db.fetchall(
            "SELECT * FROM interview_questions WHERE interview_id = ? ORDER BY order_num ASC",
            (interview_id,)
        )
        answers_raw = db.fetchall(
            "SELECT * FROM interview_answers WHERE interview_id = ?",
            (interview_id,)
        )
        answer_analyses_raw = db.fetchall(
            "SELECT * FROM answer_analyses WHERE interview_id = ?",
            (interview_id,)
        )
        behavior_analyses_raw = db.fetchall(
            "SELECT * FROM behavior_analyses WHERE interview_id = ?",
            (interview_id,)
        )

        # 3. Compute Multi-Modal Scoring
        score_data = MultiModalScoringService.evaluate_interview_scores(
            interview_id=interview_id,
            answer_analyses=answer_analyses_raw,
            behavior_analyses=behavior_analyses_raw
        )

        # 4. Parse Profiles & Skill Match
        resume_profile = None
        if interview.resume_analysis_json:
            try:
                resume_profile = ResumeProfileSchema(**json.loads(interview.resume_analysis_json))
            except Exception:
                pass

        jd_profile = None
        if interview.jd_analysis_json:
            try:
                jd_profile = JDProfileSchema(**json.loads(interview.jd_analysis_json))
            except Exception:
                pass

        skill_match = None
        if interview.skill_match_json:
            try:
                skill_match = SkillMatchSchema(**json.loads(interview.skill_match_json))
            except Exception:
                pass

        # 5. Extract Strengths & Weaknesses grounded in actual metrics
        strengths: List[str] = []
        weaknesses: List[str] = []

        tech_score = score_data.dimensions["technical"].raw_score
        comm_score = score_data.dimensions["communication"].raw_score
        fluency_score = score_data.dimensions["fluency"].raw_score
        eye_score = score_data.dimensions["eye_contact"].raw_score
        posture_score = score_data.dimensions["posture"].raw_score

        # Grounded Strengths
        if tech_score >= 80.0:
            strengths.append(f"Strong technical knowledge demonstrated across {interview.job_role or 'software engineering'} fundamentals.")
        if comm_score >= 80.0:
            strengths.append("High clarity and professional articulation with strong domain terminology.")
        if fluency_score >= 80.0:
            strengths.append("Natural, well-paced vocal delivery with minimal hesitation.")
        if eye_score >= 80.0:
            strengths.append("Consistent camera-facing alignment and visual stability.")
        if posture_score >= 80.0:
            strengths.append("Upright, professional physical posture maintained throughout responses.")
        if skill_match and skill_match.match_percentage >= 70.0:
            strengths.append(f"High resume-to-job requirement alignment ({skill_match.match_percentage}% match).")
        if not strengths:
            strengths.append("Successfully attempted all technical and situational interview questions.")

        # Grounded Weaknesses
        if tech_score < 75.0:
            weaknesses.append("Explanations of architectural trade-offs, concurrency, and performance bottlenecks lacked depth.")
        if comm_score < 75.0:
            weaknesses.append("Occasional casual phrasing and opportunities for more concise technical terminology.")
        if fluency_score < 75.0:
            weaknesses.append("Frequent filler words ('um', 'like', 'actually') observed during pauses.")
        if eye_score < 70.0 and score_data.dimensions["eye_contact"].is_available:
            weaknesses.append("Gaze wandered away from the camera during longer technical explanations.")
        if posture_score < 70.0 and score_data.dimensions["posture"].is_available:
            weaknesses.append("Observable shifts in posture and off-center alignment in frame.")
        if skill_match and skill_match.skill_gaps:
            weaknesses.append(f"Missing core competencies required in JD: {', '.join(skill_match.skill_gaps[:3])}.")
        if not weaknesses:
            weaknesses.append("Minor opportunities to deepen runtime complexity analysis on advanced system design topics.")

        # 6. Extract Frequently Observed Mistakes
        mistakes: List[MistakeItemSchema] = []
        all_fillers: List[str] = []
        all_repeats: List[str] = []
        brief_answers_count = 0

        for a in answer_analyses_raw:
            try:
                fillers = json.loads(a.get("filler_words_json") or "[]")
                all_fillers.extend(fillers)
                repeats = json.loads(a.get("repeated_words_json") or "[]")
                all_repeats.extend(repeats)
            except Exception:
                pass
            if float(a.get("speaking_duration") or 0.0) < 6.0:
                brief_answers_count += 1

        if all_fillers:
            from collections import Counter
            top_fillers = Counter(all_fillers).most_common(2)
            filler_names = " and ".join([f"'{f[0]}' ({f[1]} times)" for f in top_fillers])
            mistakes.append(
                MistakeItemSchema(
                    mistake_type="Hesitation Disfluency",
                    description=f"Frequent usage of filler vocalizations: {filler_names}.",
                    frequency=len(all_fillers),
                    severity="Medium" if len(all_fillers) > 6 else "Low",
                    remediation_tip="Substitute silent 2-second pauses for filler words to gather thoughts."
                )
            )

        if all_repeats:
            mistakes.append(
                MistakeItemSchema(
                    mistake_type="Immediate Word Repetitions",
                    description=f"Consecutive word stutters detected (e.g., {', '.join(set(all_repeats[:3]))}).",
                    frequency=len(all_repeats),
                    severity="Low",
                    remediation_tip="Slow down initial sentence tempo by 10% to prevent vocal restarts."
                )
            )

        if brief_answers_count > 0:
            mistakes.append(
                MistakeItemSchema(
                    mistake_type="Under-elaborated Answers",
                    description=f"{brief_answers_count} question(s) answered with very brief statements lacking technical detail.",
                    frequency=brief_answers_count,
                    severity="High" if brief_answers_count > 1 else "Medium",
                    remediation_tip="Use the STAR method: State Context, Implementation Steps, and Quantifiable Results."
                )
            )

        # 7. Construct Category Ratings
        category_ratings: List[CategoryRatingSchema] = [
            CategoryRatingSchema(
                category_name="Technical Knowledge",
                score=tech_score,
                level=MultiModalScoringService.calculate_readiness_level(tech_score),
                strengths="Solid baseline in core programming languages." if tech_score >= 75 else "Foundational concepts understood.",
                weaknesses="Needs deeper explanations of system design and scale." if tech_score < 85 else "Minor trade-off details missing.",
                recommendation="Practice intermediate system-design problems and database transaction management."
            ),
            CategoryRatingSchema(
                category_name="Communication",
                score=comm_score,
                level=MultiModalScoringService.calculate_readiness_level(comm_score),
                strengths="Good sentence structure and articulation." if comm_score >= 75 else "Answers were comprehensible.",
                weaknesses="Opportunities for richer domain terminology." if comm_score < 85 else "Keep answers concise.",
                recommendation="Incorporate standard software engineering vocabulary in daily technical reviews."
            ),
            CategoryRatingSchema(
                category_name="Fluency",
                score=fluency_score,
                level=MultiModalScoringService.calculate_readiness_level(fluency_score),
                strengths="Steady conversational pace." if fluency_score >= 75 else "Maintained speaking flow.",
                weaknesses="Hesitations during complex questions." if fluency_score < 85 else "Slight vocal pauses.",
                recommendation="Record yourself answering timed 2-minute placement questions without filler words."
            ),
            CategoryRatingSchema(
                category_name="Confidence Indicator",
                score=score_data.confidence_indicator,
                level=MultiModalScoringService.calculate_readiness_level(score_data.confidence_indicator),
                strengths="Maintained steady delivery throughout the interview." if score_data.confidence_indicator >= 75 else "Showed composure under questioning.",
                weaknesses="Pacing fluctuated during follow-up probing." if score_data.confidence_indicator < 85 else "Slight hesitation on edge cases.",
                recommendation="Practice mock interviews under time pressure to build verbal stamina."
            ),
            CategoryRatingSchema(
                category_name="Eye Contact",
                score=eye_score,
                level=MultiModalScoringService.calculate_readiness_level(eye_score),
                strengths="Good camera-facing attention." if eye_score >= 75 else "Looked toward camera.",
                weaknesses="Looked away when formulating answers." if eye_score < 85 else "Minor gaze shifts.",
                recommendation="Position the webcam at eye level to optimize direct camera-facing presence."
            ),
            CategoryRatingSchema(
                category_name="Posture & Professional Behaviour",
                score=posture_score,
                level=MultiModalScoringService.calculate_readiness_level(posture_score),
                strengths="Maintained upright, centered upper-body posture." if posture_score >= 75 else "Centered in video frame.",
                weaknesses="Occasional lateral leaning." if posture_score < 85 else "Minor posture adjustments.",
                recommendation="Keep shoulders squared and sit comfortably upright throughout the session."
            )
        ]

        # 8. Construct Question-by-Question Breakdown
        question_breakdowns: List[QuestionBreakdownSchema] = []
        ans_by_qid = {a["question_id"]: a for a in answers_raw}
        analysis_by_qid = {a["question_id"]: a for a in answer_analyses_raw}

        for q in questions_raw:
            qid = q["id"]
            ans = ans_by_qid.get(qid, {})
            ana = analysis_by_qid.get(qid, {})

            q_tech = float(ana.get("technical_score") or 70.0)
            q_comm = float(ana.get("communication_score") or 70.0)
            q_flue = float(ana.get("fluency_score") or 70.0)
            q_fb = ana.get("technical_feedback") or "Good answer provided."

            question_breakdowns.append(
                QuestionBreakdownSchema(
                    order_number=q["order_num"],
                    question=q["question_text"],
                    category=q["question_category"],
                    difficulty=q["difficulty"],
                    candidate_answer=ans.get("transcript_text") or "Spoken answer submitted.",
                    technical_score=round(q_tech, 1),
                    communication_score=round(q_comm, 1),
                    fluency_score=round(q_flue, 1),
                    feedback=q_fb,
                    strengths="Directly addressed core question concepts." if q_tech >= 75 else "Communicated technical intent.",
                    weaknesses="Could deepen discussion of edge cases and trade-offs." if q_tech < 85 else "Minor omissions."
                )
            )

        # 9. Generate Personalized Roadmap
        roadmap_response = PersonalizedRoadmapService.generate_roadmap(
            interview_id=interview_id,
            user_id=user_id,
            score_data=score_data,
            skill_match=skill_match,
            weaknesses=weaknesses,
            mistakes=[m.dict() for m in mistakes],
            job_role=interview.job_role
        )

        summary_text = (
            f"Candidate achieved an Overall Score of {score_data.overall_score}% with a readiness classification of "
            f"'{score_data.readiness_level}'. Technical proficiency scored at {tech_score}%, with communication at {comm_score}% "
            f"and speech fluency at {fluency_score}%. A 5-phase personalized learning roadmap has been generated to address "
            f"identified skill gaps and elevate placement drive performance."
        )

        # 10. Persist in Database (Scores, Reports, Roadmaps)
        # 10.1 Save to interview_scores
        db.execute(
            """
            INSERT OR REPLACE INTO interview_scores (
                interview_id, overall_score, technical_score, communication_score,
                fluency_score, eye_contact_score, posture_score, expression_score,
                confidence_indicator, readiness_level, weights_json, available_weights_sum,
                unavailable_modalities_json, contributions_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'utc'))
            """,
            (
                interview_id,
                score_data.overall_score,
                tech_score,
                comm_score,
                fluency_score,
                eye_score,
                posture_score,
                score_data.dimensions["expression"].raw_score,
                score_data.confidence_indicator,
                score_data.readiness_level,
                json.dumps(score_data.weights_used),
                score_data.available_weights_sum,
                json.dumps(score_data.unavailable_modalities),
                json.dumps({k: v.contribution for k, v in score_data.dimensions.items()})
            )
        )

        # 10.2 Save to roadmaps
        db.execute(
            """
            INSERT OR REPLACE INTO roadmaps (
                interview_id, user_id, phases_json, created_at
            ) VALUES (?, ?, ?, datetime('now', 'utc'))
            """,
            (
                interview_id,
                user_id,
                json.dumps([p.dict() for p in roadmap_response.phases])
            )
        )

        # 10.3 Save to interview_reports
        db.execute(
            """
            INSERT OR REPLACE INTO interview_reports (
                interview_id, user_id, overall_score, readiness_level, summary_text,
                strengths_json, weaknesses_json, mistakes_json, skill_gaps_json,
                category_ratings_json, question_breakdowns_json, resume_review_json,
                jd_match_json, roadmap_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'utc'))
            """,
            (
                interview_id,
                user_id,
                score_data.overall_score,
                score_data.readiness_level,
                summary_text,
                json.dumps(strengths),
                json.dumps(weaknesses),
                json.dumps([m.dict() for m in mistakes]),
                json.dumps(skill_match.skill_gaps if skill_match else []),
                json.dumps([c.dict() for c in category_ratings]),
                json.dumps([q.dict() for q in question_breakdowns]),
                json.dumps(resume_profile.dict() if resume_profile else {}),
                json.dumps(jd_profile.dict() if jd_profile else {}),
                json.dumps([p.dict() for p in roadmap_response.phases])
            )
        )

        # 10.4 Update interview overall score
        db.execute(
            """
            UPDATE interviews
            SET overall_score = ?,
                technical_score = ?,
                communication_score = ?,
                facial_score = ?,
                status = 'completed',
                updated_at = datetime('now', 'utc')
            WHERE id = ?
            """,
            (score_data.overall_score, tech_score, comm_score, eye_score, interview_id)
        )
        db.commit()

        return PerformanceReportResponse(
            interview_id=interview_id,
            user_id=user_id,
            interview_type=interview.interview_type,
            company_name=interview.company_name,
            job_role=interview.job_role,
            overall_score=score_data.overall_score,
            readiness_level=score_data.readiness_level,
            confidence_indicator=score_data.confidence_indicator,
            summary_text=summary_text,
            score_breakdown=score_data,
            category_ratings=category_ratings,
            strengths=strengths,
            weaknesses=weaknesses,
            frequently_observed_mistakes=mistakes,
            skill_gaps=skill_match.skill_gaps if skill_match else [],
            matched_skills=skill_match.matched_skills if skill_match else [],
            match_percentage=skill_match.match_percentage if skill_match else 100.0,
            question_breakdowns=question_breakdowns,
            roadmap=roadmap_response,
            created_at=""
        )

    @classmethod
    def get_report(cls, db: DatabaseSession, interview_id: int, user_id: int) -> PerformanceReportResponse:
        # Check if report already exists in DB
        rep_row = db.fetchone(
            "SELECT * FROM interview_reports WHERE interview_id = ? AND user_id = ?",
            (interview_id, user_id)
        )
        if rep_row:
            score_row = db.fetchone("SELECT * FROM interview_scores WHERE interview_id = ?", (interview_id,))
            int_row = db.fetchone("SELECT * FROM interviews WHERE id = ?", (interview_id,))

            score_data = MultiModalScoringService.compute_weighted_score(
                technical_score=score_row["technical_score"] if score_row else 70.0,
                communication_score=score_row["communication_score"] if score_row else 70.0,
                fluency_score=score_row["fluency_score"] if score_row else 70.0,
                eye_contact_score=score_row["eye_contact_score"] if score_row else 75.0,
                posture_score=score_row["posture_score"] if score_row else 75.0,
                expression_score=score_row["expression_score"] if score_row else 0.0,
                is_expression_available=False,
                is_fluency_available=True,
                is_vision_available=True
            )
            score_resp = InterviewScoreResponse(
                interview_id=interview_id,
                overall_score=rep_row["overall_score"],
                readiness_level=rep_row["readiness_level"],
                confidence_indicator=score_row["confidence_indicator"] if score_row else 75.0,
                dimensions=score_data[1],
                weights_used=score_data[2],
                available_weights_sum=score_data[3],
                unavailable_modalities=score_data[4]
            )

            roadmap_phases = json.loads(rep_row["roadmap_json"] or "[]")
            roadmap_resp = RoadmapResponse(
                interview_id=interview_id,
                user_id=user_id,
                overall_score=rep_row["overall_score"],
                readiness_level=rep_row["readiness_level"],
                phases=roadmap_phases,
                created_at=rep_row["created_at"]
            )

            return PerformanceReportResponse(
                interview_id=interview_id,
                user_id=user_id,
                interview_type=int_row["interview_type"] if int_row else "general",
                company_name=int_row["company_name"] if int_row else None,
                job_role=int_row["job_role"] if int_row else None,
                overall_score=rep_row["overall_score"],
                readiness_level=rep_row["readiness_level"],
                confidence_indicator=score_row["confidence_indicator"] if score_row else 75.0,
                summary_text=rep_row["summary_text"] or "",
                score_breakdown=score_resp,
                category_ratings=json.loads(rep_row["category_ratings_json"] or "[]"),
                strengths=json.loads(rep_row["strengths_json"] or "[]"),
                weaknesses=json.loads(rep_row["weaknesses_json"] or "[]"),
                frequently_observed_mistakes=json.loads(rep_row["mistakes_json"] or "[]"),
                skill_gaps=json.loads(rep_row["skill_gaps_json"] or "[]"),
                matched_skills=[],
                match_percentage=80.0,
                question_breakdowns=json.loads(rep_row["question_breakdowns_json"] or "[]"),
                roadmap=roadmap_resp,
                created_at=rep_row["created_at"]
            )

        # Otherwise generate freshly (will verify ownership and raise 404 if not found)
        return cls.generate_and_save_report(db, interview_id, user_id)
