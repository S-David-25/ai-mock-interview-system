import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from app.config import MAX_TOTAL_QUESTIONS, MAX_FOLLOW_UPS_PER_TOPIC, INITIAL_QUESTIONS_COUNT
from app.schemas.interview import (
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
    QuestionSchema,
    TechnicalEvaluationSchema,
)
from app.services.gemini_service import GeminiService

logger = logging.getLogger("question_service")

class QuestionService:
    """
    Generates genuine, dynamic, non-template interview questions and adaptive follow-ups
    powered exclusively by Google Gemini. All questions are crafted in real time using
    the candidate's actual extracted resume, job description, role, company, past interview history,
    and the candidate's live answer transcripts.
    """

    @staticmethod
    def _normalize_tokens(text: str) -> set:
        """Extracts significant lowercase alphanumeric tokens for duplicate detection."""
        words = re.findall(r"\b[a-z0-9_]+\b", text.lower())
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of",
            "with", "and", "or", "how", "what", "why", "you", "your", "could", "can", "would",
            "tell", "explain", "describe", "walk", "me", "through", "please", "specifically",
            "highlight", "project", "mention", "using"
        }
        return {w for w in words if w not in stop_words and len(w) > 2}

    @staticmethod
    def _is_too_similar(new_question: str, previous_questions: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a candidate question is a near-duplicate of an already asked question
        using token overlap and exact substring matching.
        """
        if not previous_questions or not new_question:
            return False, None

        new_tokens = QuestionService._normalize_tokens(new_question)
        if not new_tokens:
            return False, None

        for prev in previous_questions:
            if not prev or not isinstance(prev, str):
                continue
            if new_question.strip().lower() == prev.strip().lower():
                return True, prev

            prev_tokens = QuestionService._normalize_tokens(prev)
            if not prev_tokens:
                continue

            intersection = new_tokens.intersection(prev_tokens)
            union = new_tokens.union(prev_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= 0.60:
                return True, prev

        return False, None

    @staticmethod
    def _format_projects_display(resume: ResumeProfileSchema) -> str:
        projects_display = []
        for p in (resume.projects or [])[:5]:
            if isinstance(p, dict):
                p_name = p.get("name")
                p_desc = p.get("description")
                p_tech = p.get("technologies")
                parts = []
                if p_name:
                    parts.append(f"Name: {p_name}")
                if p_tech:
                    parts.append(f"Technologies: {', '.join(p_tech) if isinstance(p_tech, list) else str(p_tech)}")
                if p_desc:
                    parts.append(f"Summary: {p_desc}")
                projects_display.append(" | ".join(parts) if parts else str(p))
            else:
                projects_display.append(str(p))
        return "\n  • ".join(projects_display) if projects_display else "(none listed)"

    @staticmethod
    def _format_experience_display(resume: ResumeProfileSchema) -> str:
        exp_display = []
        for e in (resume.experience or [])[:4]:
            if isinstance(e, dict):
                comp = e.get("company", "")
                role = e.get("role", "")
                dur = e.get("duration", "")
                resp = e.get("responsibilities", [])
                exp_str = f"{role} at {comp} ({dur})"
                if resp:
                    exp_str += f" - Duties: {', '.join(resp[:2])}"
                exp_display.append(exp_str)
            else:
                exp_display.append(str(e))
        return "\n  • ".join(exp_display) if exp_display else "(none listed)"

    @staticmethod
    async def generate_initial_question(
        interview_id: int,
        interview_type: str,
        company_name: Optional[str],
        job_role: Optional[str],
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema] = None,
        skill_match: Optional[SkillMatchSchema] = None,
        past_session_questions: Optional[List[str]] = None
    ) -> QuestionSchema:
        """
        Dynamically generates Question 1 for the interview session via Gemini.
        Zero hardcoded templates. Strictly personalized to candidate background and role.
        """
        logger.info(f"Generating dynamic initial question using Gemini for Interview #{interview_id} ({interview_type})...")

        tech_skills_str = ", ".join(resume.technical_skills or []) or "General Software Development"
        prog_lang_str = ", ".join(resume.programming_languages or []) or "General Languages"
        frameworks_str = ", ".join(resume.frameworks or []) or "Standard Frameworks"
        databases_str = ", ".join(resume.databases or []) or "Relational/NoSQL"
        tools_str = ", ".join(resume.tools or []) or "Standard Developer Tools"
        projects_str = QuestionService._format_projects_display(resume)
        experience_str = QuestionService._format_experience_display(resume)
        education_str = ", ".join(resume.education or []) or "Degree in Computing/Engineering"

        jd_context_lines = []
        if interview_type == "company" and jd:
            jd_context_lines.append(f"Target Company: {company_name or jd.company or 'Target Employer'}")
            jd_context_lines.append(f"Target Job Role: {job_role or jd.job_role or 'Software Engineer'}")
            if jd.required_skills:
                jd_context_lines.append(f"JD Required Skills: {', '.join(jd.required_skills)}")
            if jd.responsibilities:
                jd_context_lines.append(f"Key Responsibilities: {', '.join(jd.responsibilities[:3])}")
            if skill_match and skill_match.skill_gaps:
                jd_context_lines.append(f"Identified Skill Gaps to probe: {', '.join(skill_match.skill_gaps)}")
        else:
            jd_context_lines.append(f"Interview Focus: General Placement Mock Interview for {job_role or 'Software Engineer'}")

        anti_repeat_context = ""
        if past_session_questions:
            anti_repeat_context = f"\nQUESTIONS ASKED IN PAST INTERVIEWS WITH THIS CANDIDATE (DO NOT REPEAT):\n" + "\n".join([f"- {q}" for q in past_session_questions[-8:]])

        system_instruction = (
            "You are an elite, natural, and perceptive AI Technical Interviewer conducting a live technical placement interview.\n\n"
            "MANDATORY INSTRUCTIONS:\n"
            "1. NEVER use canned, rigid sentence templates (e.g. 'Could you walk me through the architecture and implementation of...').\n"
            "2. NEVER use fixed question boilerplate. Decide the phrasing, angle, depth, and tone dynamically.\n"
            "3. Craft an engaging, authentic, high-signal technical question that immediately probes the candidate's actual software projects, design decisions, architectural trade-offs, concurrency handling, database choices, or engineering challenges.\n"
            "4. The question must sound like an experienced Senior Staff Engineer or Hiring Manager asking in real time.\n"
            "5. Return STRICT JSON matching the schema:\n"
            "{\n"
            '  "question": "<The fully phrased technical interview question>",\n'
            '  "category": "PROJECT" | "TECHNICAL" | "SKILL_GAP" | "SYSTEM_DESIGN" | "SCENARIO" | "BEHAVIORAL" | "CODING",\n'
            '  "difficulty": "EASY" | "MEDIUM" | "HARD",\n'
            '  "expected_focus": ["key technical concept 1", "key technical concept 2", "key trade-off 3"]\n'
            "}"
        )

        prompt = (
            f"Generate the opening question (Question 1) for this interview session.\n\n"
            f"--- CANDIDATE PROFILE ---\n"
            f"Candidate Name: {resume.candidate_name or 'Candidate'}\n"
            f"Education: {education_str}\n"
            f"Technical Skills: {tech_skills_str}\n"
            f"Programming Languages: {prog_lang_str}\n"
            f"Frameworks & Libraries: {frameworks_str}\n"
            f"Databases & Storage: {databases_str}\n"
            f"Tools & Cloud: {tools_str}\n"
            f"Projects:\n  • {projects_str}\n"
            f"Experience:\n  • {experience_str}\n\n"
            f"--- INTERVIEW CONTEXT ---\n"
            f"Session ID: {interview_id}\n"
            f"{chr(10).join(jd_context_lines)}\n"
            f"{anti_repeat_context}\n\n"
            f"Generate a unique, compelling opening question tailored specifically to this candidate's background."
        )

        previous_to_check = list(past_session_questions or [])
        last_error = None

        for attempt in range(1, 4):
            try:
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.7 + (attempt * 0.1),
                    purpose="Initial Question Generation"
                )

                q_text = (result.get("question") or "").strip()
                if not q_text or len(q_text) < 15:
                    raise ValueError(f"Gemini returned an empty or invalid question string: '{q_text}'")

                # Anti-repetition check
                is_duplicate, duplicate_prev = QuestionService._is_too_similar(q_text, previous_to_check)
                if is_duplicate:
                    logger.warning(f"Attempt {attempt}: Question was too similar to '{duplicate_prev}'. Retrying with Gemini...")
                    prompt += f"\n\nNOTE: The question '{q_text}' was too similar to a previous question. Generate a completely different question exploring a distinct project or topic."
                    continue

                category = result.get("category", "PROJECT").upper()
                valid_categories = {"PROJECT", "TECHNICAL", "SKILL_GAP", "SYSTEM_DESIGN", "SCENARIO", "BEHAVIORAL", "CODING"}
                if category not in valid_categories:
                    category = "TECHNICAL"

                difficulty = result.get("difficulty", "MEDIUM").upper()
                if difficulty not in {"EASY", "MEDIUM", "HARD"}:
                    difficulty = "MEDIUM"

                focus = result.get("expected_focus", [])
                if not isinstance(focus, list) or not focus:
                    focus = ["technical depth", "trade-offs", "problem-solving"]

                logger.info(f"Gemini question generation successful.")
                logger.info(f"Gemini generated question: \"{q_text}\" (Category: {category})")

                return QuestionSchema(
                    id=None,
                    interview_id=interview_id,
                    question=q_text,
                    category=category,
                    difficulty=difficulty,
                    expected_focus=[str(f) for f in focus],
                    source="RESUME" if category in {"PROJECT", "TECHNICAL"} else "JD",
                    order_number=1,
                    status="pending"
                )

            except Exception as e:
                logger.warning(f"Attempt {attempt} failed to generate initial question via Gemini: {e}")
                last_error = e

        logger.error(f"Gemini question generation failed: {last_error}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Question Generation Error: Gemini failed to generate a dynamic interview question: {str(last_error)}"
        )

    @staticmethod
    async def generate_initial_questions(
        interview_id: int,
        interview_type: str,
        company_name: Optional[str],
        job_role: Optional[str],
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema] = None,
        skill_match: Optional[SkillMatchSchema] = None,
        num_questions: int = 1,
        past_session_questions: Optional[List[str]] = None
    ) -> List[QuestionSchema]:
        """
        Backward-compatible wrapper returning the single dynamically generated Question 1.
        """
        q1 = await QuestionService.generate_initial_question(
            interview_id=interview_id,
            interview_type=interview_type,
            company_name=company_name,
            job_role=job_role,
            resume=resume,
            jd=jd,
            skill_match=skill_match,
            past_session_questions=past_session_questions
        )
        return [q1]

    @staticmethod
    async def generate_next_question_or_follow_up(
        interview_id: int,
        interview_type: str,
        company_name: Optional[str],
        job_role: Optional[str],
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema],
        skill_match: Optional[SkillMatchSchema],
        previous_questions: List[Dict[str, Any]],
        previous_answers: List[Dict[str, Any]],
        latest_question: QuestionSchema,
        latest_answer: str,
        latest_eval: TechnicalEvaluationSchema,
        remaining_time_seconds: Optional[int],
        current_order_number: int
    ) -> Tuple[QuestionSchema, bool]:
        """
        Core real-time adaptive engine:
        Called immediately after candidate submits an answer.
        Gemini analyzes candidate's actual answer, technical depth, and omissions.
        Gemini decides whether to ask an adaptive follow-up or generate a new diverse question.
        Zero hardcoded templates.
        """
        logger.info(f"Generating next dynamic question / adaptive follow-up using Gemini for Interview #{interview_id} (Order #{current_order_number + 1})...")

        # Compile historical Q&A transcript for context
        qa_history_lines = []
        all_asked_questions = []
        for i, q in enumerate(previous_questions):
            q_text = q.get("question_text") or q.get("question") or ""
            if q_text:
                all_asked_questions.append(q_text)
            ans_text = "(Not yet answered)"
            if i < len(previous_answers):
                ans_text = previous_answers[i].get("transcript_text", "")
            qa_history_lines.append(f"Q{i+1} [{q.get('question_category', 'TECH')}]: {q_text}\nAnswer: {ans_text}")

        # Candidate profile summaries
        tech_skills_str = ", ".join(resume.technical_skills or [])
        projects_str = QuestionService._format_projects_display(resume)
        experience_str = QuestionService._format_experience_display(resume)

        jd_summary = []
        if jd:
            if jd.required_skills:
                jd_summary.append(f"Required Skills: {', '.join(jd.required_skills)}")
            if skill_match and skill_match.skill_gaps:
                jd_summary.append(f"Skill Gaps to probe: {', '.join(skill_match.skill_gaps)}")

        rem_time_str = f"{remaining_time_seconds // 60}m {remaining_time_seconds % 60}s" if remaining_time_seconds is not None else "Active Session"

        system_instruction = (
            "You are an elite, insightful AI Technical Interviewer conducting a live, interactive technical interview.\n\n"
            "YOUR TASK:\n"
            "Analyze the candidate's LATEST ANSWER transcript and evaluation metrics, then generate the NEXT best question.\n\n"
            "DECISION LOGIC:\n"
            "1. ADAPTIVE FOLLOW-UP (Set is_follow_up = true):\n"
            "   - If the candidate's answer was incomplete, hand-wavy, missed critical technical trade-offs/mechanisms (e.g. concurrency, transactions, caching, error recovery, API security, scalability), OR made a specific technical claim that warrants rigorous technical verification.\n"
            "   - The follow-up question MUST directly quote or reference specific details from what the candidate just said.\n"
            "2. NEW QUESTION (Set is_follow_up = false):\n"
            "   - If the candidate gave a thorough, well-reasoned answer, or if the current topic has already been explored in depth.\n"
            "   - Pivot dynamically to an uncovered project, a different required skill from the JD, a system design problem, an algorithmic scenario, a database challenge, or a behavioral/engineering judgment scenario.\n\n"
            "CRITICAL RULES:\n"
            "- NEVER use fixed sentence templates (e.g. 'Could you walk me through...', 'Specifically highlight why...').\n"
            "- NEVER repeat any question that has already been asked in this session.\n"
            "- Craft natural, human-sounding, rigorous questions.\n"
            "- Return STRICT JSON matching the schema:\n"
            "{\n"
            '  "is_follow_up": true | false,\n'
            '  "follow_up_rationale": "<Short rationale for follow-up vs next question>",\n'
            '  "question": "<The fully phrased technical question>",\n'
            '  "category": "PROJECT" | "TECHNICAL" | "SKILL_GAP" | "SYSTEM_DESIGN" | "SCENARIO" | "BEHAVIORAL" | "CODING",\n'
            '  "difficulty": "EASY" | "MEDIUM" | "HARD",\n'
            '  "expected_focus": ["focus 1", "focus 2", "focus 3"]\n'
            "}"
        )

        prompt = (
            f"--- INTERVIEW SESSION CONTEXT ---\n"
            f"Interview ID: {interview_id}\n"
            f"Target Role: {job_role or 'Software Engineer'}\n"
            f"Target Company: {company_name or 'Tech Employer'}\n"
            f"Time Remaining: {rem_time_str}\n"
            f"{chr(10).join(jd_summary)}\n\n"
            f"--- CANDIDATE RESUME HIGHLIGHTS ---\n"
            f"Skills: {tech_skills_str}\n"
            f"Projects:\n  • {projects_str}\n"
            f"Experience:\n  • {experience_str}\n\n"
            f"--- INTERVIEW CONVERSATION TRANSCRIPT ---\n"
            f"{chr(10).join(qa_history_lines)}\n\n"
            f"--- MOST RECENT QUESTION & ANSWER ---\n"
            f"Question Asked: {latest_question.question}\n"
            f"Candidate's Actual Answer: \"{latest_answer}\"\n"
            f"Evaluation Depth Score: {latest_eval.depth}/100 | Completeness: {latest_eval.completeness}/100 | Technical Score: {latest_eval.technical_score}/100\n"
            f"Evaluation Feedback: {latest_eval.feedback}\n\n"
            f"Decide whether to probe the candidate's actual answer with an adaptive follow-up or ask a new distinct question, then generate it in JSON."
        )

        last_error = None

        for attempt in range(1, 4):
            try:
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.6 + (attempt * 0.1),
                    purpose="Next Question / Follow-up Generation"
                )

                q_text = (result.get("question") or "").strip()
                if not q_text or len(q_text) < 15:
                    raise ValueError(f"Gemini returned an invalid question string: '{q_text}'")

                # Anti-repetition check against all previously asked questions in current session
                is_duplicate, duplicate_prev = QuestionService._is_too_similar(q_text, all_asked_questions)
                if is_duplicate:
                    logger.warning(f"Attempt {attempt}: Generated question was too similar to '{duplicate_prev}'. Retrying with Gemini...")
                    prompt += f"\n\nNOTE: The question '{q_text}' was too similar to previous question '{duplicate_prev}'. Generate a completely different question on a new topic."
                    continue

                is_follow_up = bool(result.get("is_follow_up", False))
                category = result.get("category", "TECHNICAL").upper()
                valid_categories = {"PROJECT", "TECHNICAL", "SKILL_GAP", "SYSTEM_DESIGN", "SCENARIO", "BEHAVIORAL", "CODING"}
                if category not in valid_categories:
                    category = "TECHNICAL"

                difficulty = result.get("difficulty", "MEDIUM").upper()
                if difficulty not in {"EASY", "MEDIUM", "HARD"}:
                    difficulty = "MEDIUM"

                focus = result.get("expected_focus", [])
                if not isinstance(focus, list) or not focus:
                    focus = ["technical depth", "clarity", "architecture"]

                logger.info(f"Gemini question generation successful.")
                logger.info(f"Gemini generated question: \"{q_text}\" (Follow-up: {is_follow_up}, Category: {category})")

                next_q = QuestionSchema(
                    id=None,
                    interview_id=interview_id,
                    question=q_text,
                    category=category,
                    difficulty=difficulty,
                    expected_focus=[str(f) for f in focus],
                    source="FOLLOW_UP" if is_follow_up else ("RESUME" if category in {"PROJECT", "TECHNICAL"} else "JD"),
                    order_number=current_order_number + 1,
                    status="pending"
                )

                return next_q, is_follow_up

            except Exception as e:
                logger.warning(f"Attempt {attempt} failed to generate next question/follow-up via Gemini: {e}")
                last_error = e

        logger.error(f"Gemini question generation failed: {last_error}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Question Generation Error: Gemini failed to generate a dynamic interview question: {str(last_error)}"
        )

    @staticmethod
    async def generate_dynamic_follow_up(
        interview_id: int,
        parent_question: QuestionSchema,
        candidate_answer: str,
        topic_follow_up_count: int = 0,
        total_questions_asked: int = 1,
        job_role: Optional[str] = None
    ) -> Optional[QuestionSchema]:
        """
        Standalone dynamic follow-up method for direct callers.
        Decoupled from fixed interview completion limits.
        """
        if topic_follow_up_count >= MAX_FOLLOW_UPS_PER_TOPIC:
            return None

        if not candidate_answer or len(candidate_answer.strip().split()) < 3:
            return None

        system_instruction = (
            "You are an expert AI Technical Interviewer.\n"
            "Analyze the candidate's answer and generate a sharp, adaptive follow-up question probing specific claims, implementation details, trade-offs, or omissions.\n"
            "NEVER use canned or fixed template phrasing.\n"
            "Return JSON: {\"question\": \"...\", \"difficulty\": \"MEDIUM\", \"expected_focus\": [...]}"
        )

        prompt = (
            f"Question Asked: {parent_question.question}\n"
            f"Candidate Answer: \"{candidate_answer}\"\n"
            f"Role: {job_role or 'Software Engineer'}\n"
            f"Generate a direct technical follow-up question probing their answer."
        )

        try:
            res = await GeminiService.generate_structured_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.7
            )
            q_text = (res.get("question") or "").strip()
            if not q_text or len(q_text) < 15:
                return None

            return QuestionSchema(
                id=None,
                interview_id=interview_id,
                question=q_text,
                category=parent_question.category,
                difficulty=res.get("difficulty", "MEDIUM").upper(),
                expected_focus=res.get("expected_focus", ["implementation depth"]),
                source="FOLLOW_UP",
                order_number=total_questions_asked + 1,
                status="pending"
            )
        except Exception as e:
            logger.warning(f"Standalone follow-up generation failed: {e}")
            return None
