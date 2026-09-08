import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from app.database.session import DatabaseSession
from app.models.interview import (
    Interview,
    InterviewQuestion,
    InterviewAnswer,
    AnswerAnalysis,
    BehaviorAnalysis
)
from app.schemas.interview import (
    InterviewCreate,
    InterviewStats,
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
    QuestionSchema,
    AnswerSubmitResponse,
    TechnicalEvaluationSchema,
    CommunicationEvaluationSchema,
    FluencyEvaluationSchema,
    VisionFrameResponse
)
from app.services.resume_service import ResumeService
from app.services.jd_service import JDService
from app.services.matching_service import SkillMatchingService
from app.services.question_service import QuestionService
from app.services.answer_evaluation_service import AnswerEvaluationService
from app.services.communication_service import CommunicationService
from app.services.fluency_service import FluencyService
from app.services.vision_service import VisionService
from app.services.emotion_service import EmotionRecognitionService

logger = logging.getLogger("interview_service")

def parse_utc_timestamp(ts: Optional[str]) -> Optional[datetime]:
    """Parses a stored UTC timestamp string into a timezone-aware UTC datetime."""
    if not ts:
        return None
    try:
        clean = ts.strip().replace(" ", "T")
        if not clean.endswith("Z") and "+" not in clean and "-" not in clean[10:]:
            clean += "+00:00"
        elif clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

class InterviewService:
    @staticmethod
    def is_interview_expired(interview: Interview) -> bool:
        """Determines whether the interview session has exceeded its authoritative expires_at timestamp."""
        if not interview.expires_at:
            return False
        expires_dt = parse_utc_timestamp(interview.expires_at)
        if not expires_dt:
            return False
        return datetime.now(timezone.utc) >= expires_dt

    @staticmethod
    def check_and_handle_expiry(db: DatabaseSession, interview: Interview) -> bool:
        """If interview has expired, marks it as completed in database and updates interview object."""
        if interview.status == "completed":
            return True
        if InterviewService.is_interview_expired(interview):
            if interview.status != "completed":
                db.execute(
                    "UPDATE interviews SET status = 'completed', updated_at = datetime('now', 'utc') WHERE id = ?",
                    (interview.id,)
                )
                db.commit()
                interview.status = "completed"
            return True
        return False

    @staticmethod
    def create_interview(db: DatabaseSession, user_id: int, data: InterviewCreate) -> Interview:
        duration = data.duration_minutes or 30
        cursor = db.execute(
            """
            INSERT INTO interviews (
                user_id, interview_type, company_name, job_role, duration_minutes, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'setup', datetime('now', 'utc'), datetime('now', 'utc'))
            """,
            (user_id, data.interview_type, data.company_name, data.job_role, duration)
        )
        db.commit()
        interview_id = cursor.lastrowid
        return InterviewService.get_interview_by_id(db, interview_id, user_id)

    @staticmethod
    def get_interview_by_id(db: DatabaseSession, interview_id: int, user_id: Optional[int] = None) -> Interview:
        if user_id:
            row = db.fetchone("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user_id))
        else:
            row = db.fetchone("SELECT * FROM interviews WHERE id = ?", (interview_id,))

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found or you do not have permission to access it."
            )
        interview = Interview.from_row(row)
        if interview.status == "in_progress":
            InterviewService.check_and_handle_expiry(db, interview)
        return interview

    @staticmethod
    def get_user_interviews(db: DatabaseSession, user_id: int) -> List[Interview]:
        rows = db.fetchall(
            "SELECT * FROM interviews WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
        interviews = [Interview.from_row(r) for r in rows]
        for i in interviews:
            if i.status == "in_progress":
                InterviewService.check_and_handle_expiry(db, i)
        return interviews

    @staticmethod
    def get_user_interview_stats(db: DatabaseSession, user_id: int) -> InterviewStats:
        interviews = InterviewService.get_user_interviews(db, user_id)
        total = len(interviews)
        if total == 0:
            return InterviewStats(
                total_interviews=0,
                average_score=None,
                latest_score=None,
                completed_count=0,
                ready_count=0,
                setup_count=0
            )

        completed = [i for i in interviews if i.status == "completed" and i.overall_score is not None]
        ready_count = sum(1 for i in interviews if i.status == "ready" or i.status == "in_progress")
        setup_count = sum(1 for i in interviews if i.status == "setup")

        avg_score = None
        if completed:
            scores = [i.overall_score for i in completed if i.overall_score is not None]
            if scores:
                avg_score = round(sum(scores) / len(scores), 1)

        latest_score = None
        for i in interviews:
            if i.overall_score is not None:
                latest_score = round(i.overall_score, 1)
                break

        return InterviewStats(
            total_interviews=total,
            average_score=avg_score,
            latest_score=latest_score,
            completed_count=len(completed),
            ready_count=ready_count,
            setup_count=setup_count
        )

    @staticmethod
    def evaluate_and_update_status(db: DatabaseSession, interview: Interview) -> str:
        is_ready = False
        has_resume = bool(interview.resume_filename or interview.resume_text)
        has_jd = bool(interview.jd_filename or interview.jd_text)

        if interview.interview_type == "general":
            is_ready = has_resume
        elif interview.interview_type == "company":
            is_ready = bool(has_resume and has_jd)

        new_status = "ready" if is_ready else "setup"
        if interview.status not in ("completed", "in_progress", "ready") or (interview.status == "setup" and is_ready):
            db.execute(
                "UPDATE interviews SET status = ?, updated_at = datetime('now', 'utc') WHERE id = ?",
                (new_status, interview.id)
            )
            db.commit()
        return new_status

    @staticmethod
    async def process_interview_documents(
        db: DatabaseSession,
        interview_id: int,
        user_id: int
    ) -> Tuple[Optional[ResumeProfileSchema], Optional[JDProfileSchema], Optional[SkillMatchSchema], Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Processes uploaded documents for the interview:
        Extracts Resume & JD attributes, performs skill matching, and updates session state.
        """
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)

        if not interview.resume_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidate resume has not been uploaded yet."
            )

        if interview.interview_type == "company" and not interview.jd_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description has not been uploaded for this company interview."
            )

        db.execute("UPDATE interviews SET status = 'processing' WHERE id = ?", (interview.id,))
        db.commit()

        try:
            # Validate resume first
            resume_validation = ResumeService.validate_resume(interview.resume_text)
            if not resume_validation.get("is_valid"):
                # Persist validation result so frontend can show it after refresh
                db.execute(
                    "UPDATE interviews SET resume_analysis_json = ?, status = ?, updated_at = datetime('now', 'utc') WHERE id = ?",
                    (json.dumps({"validation": resume_validation}), 'setup', interview.id)
                )
                db.commit()
                return None, None, None, resume_validation, None, None

            # 1. Analyze Resume
            resume_profile = await ResumeService.analyze_resume(interview.resume_text)

            # Early exit for General interviews: resume-only processing
            if interview.interview_type == "general":
                skill_match = SkillMatchingService.match_skills(resume_profile, None)
                db.execute(
                    """
                    UPDATE interviews
                    SET resume_analysis_json = ?,
                        jd_analysis_json = NULL,
                        skill_match_json = ?,
                        ats_analysis_json = NULL,
                        overall_score = NULL,
                        status = 'ready',
                        updated_at = datetime('now', 'utc')
                    WHERE id = ?
                    """,
                    (
                        json.dumps(resume_profile.dict()),
                        json.dumps(skill_match.dict()),
                        interview.id
                    )
                )
                db.commit()
                return resume_profile, None, skill_match, resume_validation, None, None

            # Company interview validation pipeline
            jd_validation = None
            jd_profile = None
            if interview.interview_type == "company":
                if not interview.jd_text:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Job description has not been uploaded or provided for this company interview."
                    )
                jd_validation = JDService.validate_jd(interview.jd_text)
                if not jd_validation.get("is_valid"):
                    # Persist jd validation so frontend can show it
                    db.execute(
                        "UPDATE interviews SET jd_analysis_json = ?, resume_analysis_json = ?, status = ?, updated_at = datetime('now', 'utc') WHERE id = ?",
                        (json.dumps({"validation": jd_validation}), json.dumps(resume_profile.dict()), 'setup', interview.id)
                    )
                    db.commit()
                    return resume_profile, None, None, resume_validation, jd_validation, None

                # JD is valid -> analyze
                jd_profile = await JDService.analyze_jd(
                    interview.jd_text,
                    default_company=interview.company_name or "",
                    default_role=interview.job_role or ""
                )

            # 3. Match Skills
            skill_match = SkillMatchingService.match_skills(resume_profile, jd_profile)

            # 4. ATS Analysis (if JD present)
            ats_analysis = None
            if jd_profile:
                from app.services.ats_service import ATSService
                ats_analysis = ATSService.compute_ats(resume_profile, jd_profile, company=interview.company_name or "", role=interview.job_role or "", skill_match=skill_match.dict())

            # 5. Save structured results (including ATS analysis when available)
            db.execute(
                """
                UPDATE interviews
                SET resume_analysis_json = ?,
                    jd_analysis_json = ?,
                    skill_match_json = ?,
                    ats_analysis_json = ?,
                    overall_score = ?,
                    status = 'ready',
                    updated_at = datetime('now', 'utc')
                WHERE id = ?
                """,
                (
                    json.dumps(resume_profile.dict()),
                    json.dumps(jd_profile.dict()) if jd_profile else None,
                    json.dumps(skill_match.dict()),
                    json.dumps(ats_analysis) if ats_analysis else None,
                    ats_analysis.get('ats_score') if ats_analysis else None,
                    interview.id
                )
            )
            db.commit()

            return resume_profile, jd_profile, skill_match, resume_validation, jd_validation, ats_analysis
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to process documents")
            db.execute("UPDATE interviews SET status = 'failed' WHERE id = ?", (interview.id,))
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process documents: {str(e)}"
            )

    @staticmethod
    async def generate_questions(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        force_regenerate: bool = False
    ) -> List[QuestionSchema]:
        """
        Generates or returns existing personalized interview questions for the session.
        Generates exactly Question 1 dynamically at session start.
        """
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)

        # Return existing questions if already generated
        existing_rows = db.fetchall(
            "SELECT * FROM interview_questions WHERE interview_id = ? ORDER BY order_num ASC",
            (interview_id,)
        )
        if existing_rows and not force_regenerate:
            return [
                QuestionSchema(
                    id=r["id"],
                    interview_id=r["interview_id"],
                    question=r["question_text"],
                    category=r["question_category"],
                    difficulty=r["difficulty"],
                    expected_focus=json.loads(r["expected_focus_json"] or "[]"),
                    source=r["source"],
                    order_number=r["order_num"],
                    status=r["status"]
                ) for r in existing_rows
            ]

        # If analysis not done yet, run document processing first
        resume_data = json.loads(interview.resume_analysis_json) if interview.resume_analysis_json else None
        if not resume_data or ("validation" in resume_data and "technical_skills" not in resume_data):
            resume_prof, jd_prof, skill_match, resume_validation, jd_validation, ats_analysis = await InterviewService.process_interview_documents(db, interview_id, user_id)
            if not resume_validation or not resume_validation.get("is_valid"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume validation failed. Please upload a valid resume before generating questions.")
            if interview.interview_type == 'company' and jd_validation and not jd_validation.get('is_valid'):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job Description validation failed. Please provide a valid JD before generating questions.")
        else:
            resume_prof = ResumeProfileSchema(**resume_data)
            jd_data = json.loads(interview.jd_analysis_json) if interview.jd_analysis_json else None
            jd_prof = JDProfileSchema(**jd_data) if jd_data and ("validation" not in jd_data or "required_skills" in jd_data) else None
            skill_match = SkillMatchSchema(**json.loads(interview.skill_match_json)) if interview.skill_match_json else SkillMatchSchema()

        # Clear previous questions if regenerating
        if force_regenerate:
            db.execute("DELETE FROM interview_questions WHERE interview_id = ?", (interview_id,))

        # Fetch past questions from prior interviews for this user to avoid cross-interview repetition
        past_q_rows = db.fetchall(
            """
            SELECT iq.question_text
            FROM interview_questions iq
            JOIN interviews i ON iq.interview_id = i.id
            WHERE i.user_id = ? AND i.id != ?
            ORDER BY iq.id DESC LIMIT 15
            """,
            (user_id, interview_id)
        )
        past_questions = [r["question_text"] for r in past_q_rows if r["question_text"]]

        # Dynamically generate Question 1 via Gemini
        q1 = await QuestionService.generate_initial_question(
            interview_id=interview.id,
            interview_type=interview.interview_type,
            company_name=interview.company_name,
            job_role=interview.job_role,
            resume=resume_prof,
            jd=jd_prof,
            skill_match=skill_match,
            past_session_questions=past_questions
        )

        cursor = db.execute(
            """
            INSERT INTO interview_questions (
                interview_id, question_text, question_category, difficulty,
                expected_focus_json, source, order_num, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'pending', datetime('now', 'utc'))
            """,
            (
                interview.id,
                q1.question,
                q1.category,
                q1.difficulty,
                json.dumps(q1.expected_focus),
                q1.source
            )
        )
        q1.id = cursor.lastrowid
        db.commit()
        return [q1]

    @staticmethod
    def get_interview_questions(db: DatabaseSession, interview_id: int, user_id: int) -> List[QuestionSchema]:
        InterviewService.get_interview_by_id(db, interview_id, user_id)
        rows = db.fetchall(
            "SELECT * FROM interview_questions WHERE interview_id = ? ORDER BY order_num ASC",
            (interview_id,)
        )
        return [
            QuestionSchema(
                id=r["id"],
                interview_id=r["interview_id"],
                question=r["question_text"],
                category=r["question_category"],
                difficulty=r["difficulty"],
                expected_focus=json.loads(r["expected_focus_json"] or "[]"),
                source=r["source"],
                order_number=r["order_num"],
                status=r["status"]
            ) for r in rows
        ]

    @staticmethod
    def start_interview(db: DatabaseSession, interview_id: int, user_id: int) -> Interview:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        if interview.status == "completed":
            return interview

        now_utc = datetime.now(timezone.utc)
        if not interview.started_at or not interview.expires_at:
            duration = interview.duration_minutes or 30
            expires_dt = now_utc + timedelta(minutes=duration)
            started_at_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")
            expires_at_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE interviews SET status = 'in_progress', started_at = ?, expires_at = ?, updated_at = datetime('now', 'utc') WHERE id = ?",
                (started_at_str, expires_at_str, interview.id)
            )
        else:
            if InterviewService.is_interview_expired(interview):
                db.execute(
                    "UPDATE interviews SET status = 'completed', updated_at = datetime('now', 'utc') WHERE id = ?",
                    (interview.id,)
                )
            else:
                db.execute(
                    "UPDATE interviews SET status = 'in_progress', updated_at = datetime('now', 'utc') WHERE id = ?",
                    (interview.id,)
                )
        db.commit()
        return InterviewService.get_interview_by_id(db, interview_id, user_id)

    @staticmethod
    async def submit_answer(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        question_id: int,
        transcript: str,
        speaking_duration: float = 0.0,
        audio_filename: Optional[str] = None
    ) -> AnswerSubmitResponse:
        """
        Receives answer transcript, runs multi-modal analysis (Technical, Communication, Fluency),
        updates question status, evaluates dynamic follow-up vs next question via Gemini,
        and returns next question dynamically. Governed strictly by interview timer.
        """
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)

        # Expiry and Completion Check: Backend expiry must win
        if interview.status == "completed" or InterviewService.check_and_handle_expiry(db, interview):
            return AnswerSubmitResponse(
                interview_id=interview.id,
                question_id=question_id,
                answer_id=0,
                technical_evaluation=TechnicalEvaluationSchema(
                    technical_score=0.0, correctness=0.0, relevance=0.0, completeness=0.0, depth=0.0, feedback="Interview session has ended."
                ),
                communication_evaluation=CommunicationEvaluationSchema(
                    grammar_score=0.0, vocabulary_score=0.0, clarity_score=0.0, communication_score=0.0, feedback="Interview session has ended."
                ),
                fluency_evaluation=FluencyEvaluationSchema(
                    fluency_score=0.0, wpm=0.0, speaking_duration=speaking_duration, filler_word_count=0
                ),
                is_follow_up=False,
                next_question=None,
                is_completed=True,
                message="Interview time has ended. Session completed."
            )

        # 1. Fetch Question
        q_row = db.fetchone(
            "SELECT * FROM interview_questions WHERE id = ? AND interview_id = ?",
            (question_id, interview.id)
        )
        if not q_row:
            raise HTTPException(status_code=404, detail="Interview question not found in this session.")

        question = InterviewQuestion.from_row(q_row)

        # 2. Store Answer
        word_count = len(transcript.strip().split()) if transcript else 0
        ans_cursor = db.execute(
            """
            INSERT INTO interview_answers (
                interview_id, question_id, transcript_text, audio_filename,
                duration_seconds, word_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'utc'))
            """,
            (interview.id, question.id, transcript.strip(), audio_filename, speaking_duration, word_count)
        )
        answer_id = ans_cursor.lastrowid

        # 3. Mark Question as answered
        db.execute("UPDATE interview_questions SET status = 'answered' WHERE id = ?", (question.id,))

        # 4. Multi-modal Analysis (evaluate technical and communication concurrently)
        tech_task = AnswerEvaluationService.evaluate_technical_answer(
            question_text=question.question_text,
            question_category=question.question_category,
            expected_focus=question.expected_focus,
            candidate_answer=transcript,
            role_context=interview.job_role
        )
        comm_task = CommunicationService.evaluate_communication(
            transcript=transcript,
            question_context=question.question_text
        )
        tech_eval, comm_eval = await asyncio.gather(tech_task, comm_task)

        fluency_eval = FluencyService.analyze_fluency(
            transcript=transcript,
            duration_seconds=speaking_duration
        )

        # 5. Store Answer Analysis
        db.execute(
            """
            INSERT INTO answer_analyses (
                interview_id, question_id, answer_id,
                technical_score, correctness, relevance, completeness, depth, technical_feedback,
                fluency_score, wpm, speaking_duration, filler_word_count, filler_words_json, repeated_words_json,
                grammar_score, vocabulary_score, clarity_score, communication_score, communication_feedback,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'utc'))
            """,
            (
                interview.id, question.id, answer_id,
                tech_eval.technical_score, tech_eval.correctness, tech_eval.relevance, tech_eval.completeness, tech_eval.depth, tech_eval.feedback,
                fluency_eval.fluency_score, fluency_eval.wpm, fluency_eval.speaking_duration, fluency_eval.filler_word_count,
                json.dumps(fluency_eval.filler_words), json.dumps(fluency_eval.repeated_words),
                comm_eval.grammar_score, comm_eval.vocabulary_score, comm_eval.clarity_score, comm_eval.communication_score, comm_eval.feedback
            )
        )
        db.commit()

        # 6. Check Expiry before generating next question
        if InterviewService.check_and_handle_expiry(db, interview):
            return AnswerSubmitResponse(
                interview_id=interview.id,
                question_id=question.id,
                answer_id=answer_id,
                technical_evaluation=tech_eval,
                communication_evaluation=comm_eval,
                fluency_evaluation=fluency_eval,
                is_follow_up=False,
                next_question=None,
                is_completed=True,
                message="Interview time has ended. Session completed."
            )

        # 7. Dynamic Next Question / Follow-up Generation via Gemini
        all_q_rows = db.fetchall(
            "SELECT * FROM interview_questions WHERE interview_id = ? ORDER BY order_num ASC",
            (interview.id,)
        )
        all_ans_rows = db.fetchall(
            "SELECT * FROM interview_answers WHERE interview_id = ? ORDER BY id ASC",
            (interview.id,)
        )

        # Parse profile objects
        resume_prof = ResumeProfileSchema(**json.loads(interview.resume_analysis_json)) if interview.resume_analysis_json else ResumeProfileSchema()
        jd_prof = None
        if interview.jd_analysis_json:
            try:
                jd_data = json.loads(interview.jd_analysis_json)
                if jd_data and ("validation" not in jd_data or "required_skills" in jd_data):
                    jd_prof = JDProfileSchema(**jd_data)
            except Exception:
                pass
        skill_match = SkillMatchSchema(**json.loads(interview.skill_match_json)) if interview.skill_match_json else SkillMatchSchema()

        # Compute remaining seconds
        rem_seconds = None
        if interview.expires_at:
            exp_dt = parse_utc_timestamp(interview.expires_at)
            if exp_dt:
                rem_seconds = max(0, int((exp_dt - datetime.now(timezone.utc)).total_seconds()))

        parent_schema = QuestionSchema(
            id=question.id,
            interview_id=question.interview_id,
            question=question.question_text,
            category=question.question_category,
            difficulty=question.difficulty,
            expected_focus=question.expected_focus,
            source=question.source,
            order_number=question.order_num
        )

        next_q, is_follow_up = await QuestionService.generate_next_question_or_follow_up(
            interview_id=interview.id,
            interview_type=interview.interview_type,
            company_name=interview.company_name,
            job_role=interview.job_role,
            resume=resume_prof,
            jd=jd_prof,
            skill_match=skill_match,
            previous_questions=all_q_rows,
            previous_answers=all_ans_rows,
            latest_question=parent_schema,
            latest_answer=transcript,
            latest_eval=tech_eval,
            remaining_time_seconds=rem_seconds,
            current_order_number=len(all_q_rows)
        )

        # Guard: Check expiry again in case Gemini generation took time past expires_at
        if InterviewService.check_and_handle_expiry(db, interview):
            return AnswerSubmitResponse(
                interview_id=interview.id,
                question_id=question.id,
                answer_id=answer_id,
                technical_evaluation=tech_eval,
                communication_evaluation=comm_eval,
                fluency_evaluation=fluency_eval,
                is_follow_up=False,
                next_question=None,
                is_completed=True,
                message="Interview time has ended. Session completed."
            )

        # Persist new question in database
        topic_parent_id = None
        if is_follow_up and question.id:
            parent_candidate = question.parent_question_id or question.id
            parent_exists = db.fetchone("SELECT id FROM interview_questions WHERE id = ? AND interview_id = ?", (parent_candidate, interview.id))
            if parent_exists:
                topic_parent_id = parent_candidate

        q_cursor = db.execute(
            """
            INSERT INTO interview_questions (
                interview_id, question_text, question_category, difficulty,
                expected_focus_json, source, order_num, parent_question_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now', 'utc'))
            """,
            (
                interview.id,
                next_q.question,
                next_q.category,
                next_q.difficulty,
                json.dumps(next_q.expected_focus),
                next_q.source,
                len(all_q_rows) + 1,
                topic_parent_id
            )
        )
        db.commit()
        next_q.id = q_cursor.lastrowid

        return AnswerSubmitResponse(
            interview_id=interview.id,
            question_id=question.id,
            answer_id=answer_id,
            technical_evaluation=tech_eval,
            communication_evaluation=comm_eval,
            fluency_evaluation=fluency_eval,
            is_follow_up=is_follow_up,
            next_question=next_q,
            is_completed=False,
            message="Answer evaluated successfully."
        )

    @staticmethod
    def process_vision_frame(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        image_base64: str,
        question_id: Optional[int] = None
    ) -> VisionFrameResponse:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        vision_result = VisionService.process_frame(image_base64)
        emotion_result = EmotionRecognitionService.classify_facial_expression(None)

        db.execute(
            """
            INSERT INTO behavior_analyses (
                interview_id, question_id, face_detected, camera_facing_ratio,
                eye_contact_proxy_score, posture_score, head_stability_score,
                dominant_emotion, emotion_probabilities_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'utc'))
            """,
            (
                interview.id, question_id,
                1 if vision_result["face_detected"] else 0,
                vision_result["camera_facing_ratio"],
                vision_result["eye_contact_proxy_score"],
                vision_result["posture_score"],
                vision_result["head_stability_score"],
                emotion_result["dominant_emotion"],
                json.dumps(emotion_result["emotion_probabilities"])
            )
        )
        db.commit()

        return VisionFrameResponse(
            face_detected=vision_result["face_detected"],
            camera_facing_ratio=vision_result["camera_facing_ratio"],
            eye_contact_proxy_score=vision_result["eye_contact_proxy_score"],
            posture_score=vision_result["posture_score"],
            head_stability_score=vision_result["head_stability_score"],
            dominant_emotion=emotion_result["dominant_emotion"],
            emotion_probabilities=emotion_result["emotion_probabilities"],
            status=vision_result["status"]
        )

    @staticmethod
    def complete_interview(db: DatabaseSession, interview_id: int, user_id: int) -> Interview:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        db.execute(
            "UPDATE interviews SET status = 'completed', updated_at = datetime('now', 'utc') WHERE id = ?",
            (interview.id,)
        )
        db.commit()
        return InterviewService.get_interview_by_id(db, interview_id, user_id)
