import json
import logging
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

class InterviewService:
    @staticmethod
    def create_interview(db: DatabaseSession, user_id: int, data: InterviewCreate) -> Interview:
        cursor = db.execute(
            """
            INSERT INTO interviews (
                user_id, interview_type, company_name, job_role, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'setup', datetime('now', 'utc'), datetime('now', 'utc'))
            """,
            (user_id, data.interview_type, data.company_name, data.job_role)
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
        return Interview.from_row(row)

    @staticmethod
    def get_user_interviews(db: DatabaseSession, user_id: int) -> List[Interview]:
        rows = db.fetchall(
            "SELECT * FROM interviews WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
        return [Interview.from_row(r) for r in rows]

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
        if interview.interview_type == "general":
            is_ready = bool(interview.resume_filename)
        elif interview.interview_type == "company":
            is_ready = bool(interview.resume_filename and interview.jd_filename)

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
        except Exception as e:
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
        if not interview.resume_analysis_json:
            resume_prof, jd_prof, skill_match, resume_validation, jd_validation, ats_analysis = await InterviewService.process_interview_documents(db, interview_id, user_id)
            if not resume_validation.get("is_valid"):
                # Cannot generate questions without a valid resume
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume validation failed. Please upload a valid resume before generating questions.")
            if interview.interview_type == 'company' and jd_validation and not jd_validation.get('is_valid'):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job Description validation failed. Please provide a valid JD before generating questions.")
        else:
            resume_prof = ResumeProfileSchema(**json.loads(interview.resume_analysis_json))
            jd_prof = JDProfileSchema(**json.loads(interview.jd_analysis_json)) if interview.jd_analysis_json else None
            skill_match = SkillMatchSchema(**json.loads(interview.skill_match_json)) if interview.skill_match_json else SkillMatchSchema()

        # Generate questions
        generated = await QuestionService.generate_initial_questions(
            interview_id=interview.id,
            interview_type=interview.interview_type,
            company_name=interview.company_name,
            job_role=interview.job_role,
            resume=resume_prof,
            jd=jd_prof,
            skill_match=skill_match
        )

        # Clear previous questions if regenerating
        if force_regenerate:
            db.execute("DELETE FROM interview_questions WHERE interview_id = ?", (interview_id,))

        # Save to database
        saved_questions = []
        for q in generated:
            cursor = db.execute(
                """
                INSERT INTO interview_questions (
                    interview_id, question_text, question_category, difficulty,
                    expected_focus_json, source, order_num, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now', 'utc'))
                """,
                (
                    interview.id,
                    q.question,
                    q.category,
                    q.difficulty,
                    json.dumps(q.expected_focus),
                    q.source,
                    q.order_number
                )
            )
            q_id = cursor.lastrowid
            q.id = q_id
            saved_questions.append(q)

        db.commit()
        return saved_questions

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
        updates question status, evaluates dynamic follow-up, and returns next question.
        """
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)

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

        # 4. Multi-modal Analysis
        tech_eval = await AnswerEvaluationService.evaluate_technical_answer(
            question_text=question.question_text,
            question_category=question.question_category,
            expected_focus=question.expected_focus,
            candidate_answer=transcript,
            role_context=interview.job_role
        )

        comm_eval = await CommunicationService.evaluate_communication(
            transcript=transcript,
            question_context=question.question_text
        )

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

        # 6. Dynamic Follow-up Check
        # Count existing questions and follow-ups for this parent
        all_q_rows = db.fetchall("SELECT * FROM interview_questions WHERE interview_id = ?", (interview.id,))
        total_questions = len(all_q_rows)

        topic_parent_id = question.parent_question_id or question.id
        topic_follow_ups = sum(1 for r in all_q_rows if r["parent_question_id"] == topic_parent_id)

        follow_up = None
        is_follow_up = False

        # If answer was not a brief single-word and we haven't reached topic follow-up limit
        if question.source != "FOLLOW_UP" or topic_follow_ups < 2:
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
            follow_up = await QuestionService.generate_dynamic_follow_up(
                interview_id=interview.id,
                parent_question=parent_schema,
                candidate_answer=transcript,
                topic_follow_up_count=topic_follow_ups,
                total_questions_asked=total_questions,
                job_role=interview.job_role
            )

        next_q_schema = None
        if follow_up:
            # Insert follow up as next question
            f_cursor = db.execute(
                """
                INSERT INTO interview_questions (
                    interview_id, question_text, question_category, difficulty,
                    expected_focus_json, source, order_num, parent_question_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'FOLLOW_UP', ?, ?, 'pending', datetime('now', 'utc'))
                """,
                (
                    interview.id,
                    follow_up.question,
                    follow_up.category,
                    follow_up.difficulty,
                    json.dumps(follow_up.expected_focus),
                    total_questions + 1,
                    topic_parent_id
                )
            )
            db.commit()
            follow_up.id = f_cursor.lastrowid
            next_q_schema = follow_up
            is_follow_up = True
        else:
            # Fetch next pending question in queue
            pending_row = db.fetchone(
                "SELECT * FROM interview_questions WHERE interview_id = ? AND status = 'pending' ORDER BY order_num ASC LIMIT 1",
                (interview.id,)
            )
            if pending_row:
                next_q_schema = QuestionSchema(
                    id=pending_row["id"],
                    interview_id=pending_row["interview_id"],
                    question=pending_row["question_text"],
                    category=pending_row["question_category"],
                    difficulty=pending_row["difficulty"],
                    expected_focus=json.loads(pending_row["expected_focus_json"] or "[]"),
                    source=pending_row["source"],
                    order_number=pending_row["order_num"],
                    status="pending"
                )

        is_completed = next_q_schema is None
        if is_completed:
            db.execute("UPDATE interviews SET status = 'completed', updated_at = datetime('now', 'utc') WHERE id = ?", (interview.id,))
            db.commit()

        return AnswerSubmitResponse(
            interview_id=interview.id,
            question_id=question.id,
            answer_id=answer_id,
            technical_evaluation=tech_eval,
            communication_evaluation=comm_eval,
            fluency_evaluation=fluency_eval,
            is_follow_up=is_follow_up,
            next_question=next_q_schema,
            is_completed=is_completed,
            message="Answer evaluated successfully." if not is_completed else "Interview session completed! Ready for report generation in Master Prompt 3."
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
