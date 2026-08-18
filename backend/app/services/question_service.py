import json
import logging
from typing import List, Dict, Any, Optional
from app.config import MAX_TOTAL_QUESTIONS, MAX_FOLLOW_UPS_PER_TOPIC, INITIAL_QUESTIONS_COUNT
from app.schemas.interview import (
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
    QuestionSchema,
)
from app.services.gemini_service import GeminiService

logger = logging.getLogger("question_service")

class QuestionService:
    """
    Generates personalized initial interview questions and adaptive dynamic follow-ups
    tailored to the candidate's resume, target role, company, and real-time response depth.
    """

    @staticmethod
    async def generate_initial_questions(
        interview_id: int,
        interview_type: str,
        company_name: Optional[str],
        job_role: Optional[str],
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema],
        skill_match: SkillMatchSchema,
        num_questions: int = INITIAL_QUESTIONS_COUNT
    ) -> List[QuestionSchema]:
        """
        Generates the core question battery for an interview session.
        Uses Gemini when available, falling back to deterministic template generation.
        """
        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are a Senior Technical Interviewer and Placement Assessor.\n"
                    "Generate personalized, high-yield interview questions targeting the candidate's specific profile.\n"
                    "Return a JSON array of question objects."
                )
                # Prepare a display string for projects (handle structured project objects)
                projects_display = []
                for p in (resume.projects or [])[:3]:
                    if isinstance(p, dict):
                        if p.get("name"):
                            projects_display.append(p.get("name"))
                        elif p.get("description"):
                            projects_display.append(p.get("description")[:60])
                        else:
                            projects_display.append(str(p))
                    else:
                        projects_display.append(str(p))
                projects_display_str = ", ".join(projects_display) if projects_display else "(none listed)"

                prompt = (
                    f"Generate exactly {num_questions} personalized interview questions for:\n"
                    f"Interview Type: {interview_type}\n"
                    f"Company: {company_name or 'General Placement'}\n"
                    f"Role: {job_role or 'Software Engineer'}\n\n"
                    f"Candidate Profile:\n"
                    f"- Name: {resume.candidate_name}\n"
                    f"- Skills: {', '.join(resume.technical_skills[:8])}\n"
                    f"- Projects: {projects_display_str}\n"
                    f"- Skill Gaps vs JD: {', '.join(skill_match.skill_gaps[:4])}\n\n"

                    f"Distribution Requirements:\n"
                    f"1. Project Deep Dive (PROJECT)\n"
                    f"2. Core Technical Competency (TECHNICAL)\n"
                    f"3. Skill-Gap / Adaptation Question (SKILL_GAP or TECHNICAL)\n"
                    f"4. Problem Solving / Situational (SITUATIONAL)\n"
                    f"5. Behavioral / Teamwork (BEHAVIORAL)\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "questions": [\n'
                    f'    {{\n'
                    f'      "question": "...",\n'
                    f'      "category": "PROJECT",\n'
                    f'      "difficulty": "MEDIUM",\n'
                    f'      "expected_focus": ["architecture", "technologies", "challenges"],\n'
                    f'      "source": "RESUME"\n'
                    f'    }}\n'
                    f'  ]\n'
                    f"}}"
                )
                result = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.3
                )
                raw_list = result.get("questions", [])
                if raw_list and len(raw_list) > 0:
                    validated_questions = []
                    for idx, q in enumerate(raw_list[:num_questions], 1):
                        validated_questions.append(
                            QuestionSchema(
                                interview_id=interview_id,
                                question=q.get("question", "Explain your technical background."),
                                category=q.get("category", "TECHNICAL").upper(),
                                difficulty=q.get("difficulty", "MEDIUM").upper(),
                                expected_focus=q.get("expected_focus", ["core concepts", "implementation"]),
                                source=q.get("source", "GENERAL").upper(),
                                order_number=idx,
                                status="pending"
                            )
                        )
                    return validated_questions
            except Exception as e:
                logger.warning(f"Gemini question generation failed ({e}). Using deterministic question engine.")

        return QuestionService._deterministic_generate(
            interview_id, interview_type, company_name, job_role, resume, jd, skill_match, num_questions
        )

    @staticmethod
    def _deterministic_generate(
        interview_id: int,
        interview_type: str,
        company_name: Optional[str],
        job_role: Optional[str],
        resume: ResumeProfileSchema,
        jd: Optional[JDProfileSchema],
        skill_match: SkillMatchSchema,
        count: int = 5
    ) -> List[QuestionSchema]:
        """High-quality deterministic question generator mapped to candidate attributes."""
        questions: List[QuestionSchema] = []

        # 1. Project Question (Resume-based)
        primary_proj_display = "your primary software project"
        if resume.projects:
            p0 = resume.projects[0]
            if isinstance(p0, dict):
                primary_proj_display = p0.get("name") or (p0.get("description")[:80] if p0.get("description") else "your primary software project")
            else:
                primary_proj_display = str(p0)

        primary_skills = ", ".join(resume.programming_languages[:2] or resume.technical_skills[:2] or ["your chosen tech stack"])
        questions.append(
            QuestionSchema(
                interview_id=interview_id,
                question=f"Could you walk me through the architecture and implementation of '{primary_proj_display}'? Specifically highlight why you chose {primary_skills}.",
                category="PROJECT",
                difficulty="MEDIUM",
                expected_focus=["system architecture", "tech stack decisions", "technical obstacles", "outcomes"],
                source="RESUME",
                order_number=1,
                status="pending"
            )
        )

        # 2. Technical Core Question
        top_skill = resume.programming_languages[0] if resume.programming_languages else (resume.technical_skills[0] if resume.technical_skills else "Core Programming")
        questions.append(
            QuestionSchema(
                interview_id=interview_id,
                question=f"In {top_skill}, how do you manage memory lifecycle, concurrency, and error handling in high-throughput applications?",
                category="TECHNICAL",
                difficulty="MEDIUM",
                expected_focus=["memory management", "concurrency", "thread safety", "exception handling"],
                source="RESUME",
                order_number=2,
                status="pending"
            )
        )

        # 3. Company & Role / Skill Gap Question
        if interview_type == "company" and skill_match.skill_gaps:
            gap = skill_match.skill_gaps[0]
            questions.append(
                QuestionSchema(
                    interview_id=interview_id,
                    question=f"For this {job_role} position at {company_name}, experience with {gap} is valuable. Have you worked with {gap} or analogous technologies, and how would you approach adopting it?",
                    category="SKILL_GAP",
                    difficulty="HARD",
                    expected_focus=["conceptual understanding", "transferable knowledge", "fast learning approach"],
                    source="JD",
                    order_number=3,
                    status="pending"
                )
            )
        else:
            db_skill = resume.databases[0] if resume.databases else "Relational Databases"
            questions.append(
                QuestionSchema(
                    interview_id=interview_id,
                    question=f"When designing scalable schemas in {db_skill}, how do you approach indexing strategies and resolving performance bottlenecks?",
                    category="TECHNICAL",
                    difficulty="MEDIUM",
                    expected_focus=["indexing", "query optimization", "normalization vs denormalization"],
                    source="GENERAL",
                    order_number=3,
                    status="pending"
                )
            )

        # 4. Situational / System Design
        company_tag = f"at {company_name}" if company_name else "in a production environment"
        questions.append(
            QuestionSchema(
                interview_id=interview_id,
                question=f"Imagine a critical production API {company_tag} suddenly experiences a 10x traffic spike and elevated latency. Walk me through your step-by-step diagnostic and remediation process.",
                category="SITUATIONAL",
                difficulty="HARD",
                expected_focus=["monitoring & logs", "caching", "database query optimization", "rate limiting"],
                source="GENERAL",
                order_number=4,
                status="pending"
            )
        )

        # 5. Behavioral / Collaboration
        questions.append(
            QuestionSchema(
                interview_id=interview_id,
                question="Tell me about a challenging situation where you had a technical disagreement with a team member or mentor regarding design. How did you arrive at a resolution?",
                category="BEHAVIORAL",
                difficulty="EASY",
                expected_focus=["communication", "conflict resolution", "STAR method", "professional teamwork"],
                source="GENERAL",
                order_number=5,
                status="pending"
            )
        )

        return questions[:count]

    @staticmethod
    async def generate_dynamic_follow_up(
        interview_id: int,
        parent_question: QuestionSchema,
        candidate_answer: str,
        topic_follow_up_count: int,
        total_questions_asked: int,
        job_role: Optional[str] = None
    ) -> Optional[QuestionSchema]:
        """
        Dynamically analyzes candidate's answer and generates an adaptive follow-up question
        if the answer warrants deeper technical investigation or clarification.
        """
        # Guard: Check limits
        if total_questions_asked >= MAX_TOTAL_QUESTIONS:
            logger.info(f"Max total questions limit reached ({MAX_TOTAL_QUESTIONS}). Skipping follow-up.")
            return None

        if topic_follow_up_count >= MAX_FOLLOW_UPS_PER_TOPIC:
            logger.info(f"Max follow-up per topic reached ({MAX_FOLLOW_UPS_PER_TOPIC}). Moving to next topic.")
            return None

        # Check answer length: very brief or non-technical answers prompt clarification follow-ups
        words = candidate_answer.strip().split()
        if len(words) < 5:
            return QuestionSchema(
                interview_id=interview_id,
                question="Could you elaborate further on that point and provide a concrete technical example?",
                category=parent_question.category,
                difficulty="MEDIUM",
                expected_focus=parent_question.expected_focus,
                source="FOLLOW_UP",
                order_number=total_questions_asked + 1,
                status="pending"
            )

        if GeminiService.is_configured():
            try:
                system_instruction = (
                    "You are an active AI interviewer in a real-time placement mock interview.\n"
                    "Generate a concise, probing dynamic follow-up question based on the candidate's exact answer.\n"
                    "Challenge their technical choices, ask about trade-offs, edge cases, or deeper implementation details."
                )
                prompt = (
                    f"Original Question ({parent_question.category}): {parent_question.question}\n"
                    f"Candidate's Answer:\n\"{candidate_answer}\"\n\n"
                    f"Generate 1 focused follow-up question that builds directly on what the candidate just stated.\n"
                    f"Target Role: {job_role or 'Software Engineer'}\n\n"
                    f"Required JSON structure:\n"
                    f"{{\n"
                    f'  "question": "...",\n'
                    f'  "category": "{parent_question.category}",\n'
                    f'  "difficulty": "HARD",\n'
                    f'  "expected_focus": ["trade-offs", "edge cases", "performance"]\n'
                    f"}}"
                )
                res = await GeminiService.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.3
                )
                if res.get("question"):
                    return QuestionSchema(
                        interview_id=interview_id,
                        question=res["question"],
                        category=res.get("category", parent_question.category).upper(),
                        difficulty=res.get("difficulty", "HARD").upper(),
                        expected_focus=res.get("expected_focus", ["trade-offs", "deeper implementation"]),
                        source="FOLLOW_UP",
                        order_number=total_questions_asked + 1,
                        status="pending"
                    )
            except Exception as e:
                logger.warning(f"Gemini follow-up generation failed ({e}). Using deterministic follow-up logic.")

        # Deterministic Follow-up Fallback
        ans_lower = candidate_answer.lower()
        if "sql" in ans_lower or "database" in ans_lower:
            follow_up_q = "How did you handle database transaction isolation, consistency, and potential race conditions in that design?"
            focus = ["ACID properties", "isolation levels", "concurrency control"]
        elif "react" in ans_lower or "javascript" in ans_lower or "frontend" in ans_lower:
            follow_up_q = "What state management strategies and performance optimization techniques (like memoization or virtual lists) did you apply there?"
            focus = ["state management", "rendering performance", "component lifecycles"]
        elif "api" in ans_lower or "rest" in ans_lower or "fastapi" in ans_lower:
            follow_up_q = "How did you secure those API endpoints, manage authentication tokens, and handle rate-limiting?"
            focus = ["API security", "JWT auth", "rate limiting", "payload validation"]
        else:
            follow_up_q = "What trade-offs did you consider when implementing that solution, and what would you do differently if scaling it 10x?"
            focus = ["scalability", "architectural trade-offs", "refactoring"]

        return QuestionSchema(
            interview_id=interview_id,
            question=follow_up_q,
            category=parent_question.category,
            difficulty="HARD",
            expected_focus=focus,
            source="FOLLOW_UP",
            order_number=total_questions_asked + 1,
            status="pending"
        )
