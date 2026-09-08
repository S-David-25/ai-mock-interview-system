import unittest
import asyncio
from app.schemas.interview import (
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
    QuestionSchema,
)
from app.services.resume_service import ResumeService
from app.services.jd_service import JDService
from app.services.matching_service import SkillMatchingService
from app.services.question_service import QuestionService
from app.services.fluency_service import FluencyService
from app.services.communication_service import CommunicationService
from app.services.answer_evaluation_service import AnswerEvaluationService
from app.services.vision_service import VisionService
from app.services.emotion_service import EmotionRecognitionService

class TestAIEngineServices(unittest.TestCase):

    def test_01_resume_analysis_deterministic(self):
        resume_text = (
            "Alex Johnson\n"
            "Education: Bachelor of Technology in Computer Science, 2024\n"
            "Skills: Python, Java, ReactJS, PostgreSQL, Docker, Git, REST API\n"
            "Projects: AI Smart Parking System using React and FastAPI.\n"
            "Experience: Software Engineering Intern at Tech Corp.\n"
            "Certifications: AWS Certified Cloud Practitioner"
        )
        res = asyncio.run(ResumeService.analyze_resume(resume_text))
        self.assertIsInstance(res, ResumeProfileSchema)
        self.assertIn("Python", res.technical_skills)
        self.assertIn("Java", res.technical_skills)
        self.assertTrue(len(res.education) > 0)
        self.assertTrue(len(res.projects) > 0)

    def test_02_jd_analysis_deterministic(self):
        jd_text = (
            "Job Title: Backend Engineer\n"
            "Company: Google\n"
            "Requirements: 3+ years experience with Python, FastAPI, PostgreSQL, Kubernetes, Docker, and Microservices.\n"
            "Strong communication and problem solving skills required."
        )
        res = asyncio.run(JDService.analyze_jd(jd_text, default_company="Google", default_role="Backend Engineer"))
        self.assertIsInstance(res, JDProfileSchema)
        self.assertEqual(res.company, "Google")
        self.assertEqual(res.job_role, "Backend Engineer")
        self.assertTrue(any("python" in s.lower() for s in res.required_skills))

    def test_03_skill_matching_and_alias_normalization(self):
        # Candidate has: JS, py, Postgres, ReactJS, Docker
        resume = ResumeProfileSchema(
            candidate_name="Alex",
            technical_skills=["JS", "py", "Postgres", "ReactJS", "Docker"],
            programming_languages=["JavaScript", "Python"],
            frameworks=["React"],
            databases=["PostgreSQL"],
            tools=["Docker"]
        )
        # JD requires: JavaScript, Python, PostgreSQL, Kubernetes, Spring Boot
        jd = JDProfileSchema(
            company="Google",
            job_role="Full Stack Engineer",
            required_skills=["JavaScript", "Python", "PostgreSQL", "Kubernetes", "Spring Boot"]
        )

        match = SkillMatchingService.match_skills(resume, jd)
        self.assertIsInstance(match, SkillMatchSchema)
        
        # Verify matched skills via alias normalization
        matched_lower = [s.lower() for s in match.matched_skills]
        self.assertTrue(any("javascript" in s for s in matched_lower))
        self.assertTrue(any("python" in s for s in matched_lower))
        self.assertTrue(any("postgresql" in s for s in matched_lower))

        # Verify skill gaps identified
        gaps_lower = [s.lower() for s in match.skill_gaps]
        self.assertTrue(any("kubernetes" in s for s in gaps_lower))
        self.assertTrue(any("spring boot" in s for s in gaps_lower))
        self.assertGreater(match.match_percentage, 0.0)

    def test_04_personalized_question_generation(self):
        resume = ResumeProfileSchema(
            candidate_name="Alex",
            technical_skills=["Python", "FastAPI", "PostgreSQL"],
            programming_languages=["Python"],
            frameworks=["FastAPI"],
            databases=["PostgreSQL"],
            projects=[{"name": "AI Smart Parking System", "description": None, "technologies": [], "responsibilities": [], "outcomes": []}]
        )
        jd = JDProfileSchema(
            company="Amazon",
            job_role="Cloud Engineer",
            required_skills=["Python", "AWS", "Docker"]
        )
        match = SkillMatchingService.match_skills(resume, jd)

        q1 = asyncio.run(QuestionService.generate_initial_question(
            interview_id=1,
            interview_type="company",
            company_name="Amazon",
            job_role="Cloud Engineer",
            resume=resume,
            jd=jd,
            skill_match=match
        ))

        self.assertIsInstance(q1, QuestionSchema)
        self.assertEqual(q1.order_number, 1)
        self.assertEqual(q1.status, "pending")
        self.assertGreater(len(q1.question), 10)
        self.assertIn(q1.difficulty, ["EASY", "MEDIUM", "HARD"])
        self.assertTrue(len(q1.expected_focus) > 0)

    def test_05_dynamic_follow_up_and_next_question_generation(self):
        parent_q = QuestionSchema(
            id=1,
            interview_id=1,
            question="Could you explain your Smart Parking project architecture?",
            category="PROJECT",
            difficulty="MEDIUM",
            expected_focus=["system architecture", "tech stack"],
            source="RESUME",
            order_number=1
        )
        resume = ResumeProfileSchema(
            candidate_name="Alex",
            technical_skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            programming_languages=["Python"],
            frameworks=["FastAPI"],
            databases=["PostgreSQL"],
            projects=[{"name": "AI Smart Parking System", "description": None, "technologies": [], "responsibilities": [], "outcomes": []}]
        )
        jd = JDProfileSchema(
            company="Amazon",
            job_role="Cloud Engineer",
            required_skills=["Python", "AWS", "Docker"]
        )
        match = SkillMatchingService.match_skills(resume, jd)

        # 1. Brief / Incomplete answer triggers dynamic follow-up
        brief_ans = "I used FastAPI."
        tech_eval_brief = asyncio.run(AnswerEvaluationService.evaluate_technical_answer(
            parent_q.question, parent_q.category, parent_q.expected_focus, brief_ans, "Cloud Engineer"
        ))

        follow_up_q, is_fu = asyncio.run(QuestionService.generate_next_question_or_follow_up(
            interview_id=1,
            interview_type="company",
            company_name="Amazon",
            job_role="Cloud Engineer",
            resume=resume,
            jd=jd,
            skill_match=match,
            previous_questions=[parent_q.dict()],
            previous_answers=[{"transcript_text": brief_ans}],
            latest_question=parent_q,
            latest_answer=brief_ans,
            latest_eval=tech_eval_brief,
            remaining_time_seconds=1200,
            current_order_number=1
        ))

        self.assertIsInstance(follow_up_q, QuestionSchema)
        self.assertEqual(follow_up_q.order_number, 2)
        self.assertTrue(is_fu)
        self.assertEqual(follow_up_q.source, "FOLLOW_UP")
        self.assertGreater(len(follow_up_q.question), 10)

        # 2. Comprehensive answer triggers next diverse question topic
        detailed_ans = "We designed the AI Smart Parking System with FastAPI asynchronous worker endpoints, PostgreSQL with B-tree indexing for vehicle lookup, and Docker containers deployed to AWS ECS."
        tech_eval_detailed = asyncio.run(AnswerEvaluationService.evaluate_technical_answer(
            parent_q.question, parent_q.category, parent_q.expected_focus, detailed_ans, "Cloud Engineer"
        ))

        next_q, is_fu_next = asyncio.run(QuestionService.generate_next_question_or_follow_up(
            interview_id=1,
            interview_type="company",
            company_name="Amazon",
            job_role="Cloud Engineer",
            resume=resume,
            jd=jd,
            skill_match=match,
            previous_questions=[parent_q.dict(), follow_up_q.dict()],
            previous_answers=[{"transcript_text": brief_ans}, {"transcript_text": detailed_ans}],
            latest_question=follow_up_q,
            latest_answer=detailed_ans,
            latest_eval=tech_eval_detailed,
            remaining_time_seconds=1100,
            current_order_number=2
        ))

        self.assertIsInstance(next_q, QuestionSchema)
        self.assertEqual(next_q.order_number, 3)
        self.assertGreater(len(next_q.question), 10)

    def test_06_fluency_analysis(self):
        transcript_clean = "We designed the microservices architecture using Docker containers and deployed it to AWS with high availability."
        clean_eval = FluencyService.analyze_fluency(transcript_clean, duration_seconds=8.0)
        self.assertGreaterEqual(clean_eval.fluency_score, 80.0)
        self.assertEqual(clean_eval.filler_word_count, 0)

        transcript_with_fillers = "Um, like, basically we, uh, deployed the, the database, like, actually on AWS, you know."
        filler_eval = FluencyService.analyze_fluency(transcript_with_fillers, duration_seconds=10.0)
        self.assertGreater(filler_eval.filler_word_count, 3)
        self.assertLess(filler_eval.fluency_score, clean_eval.fluency_score)
        self.assertIn("um", filler_eval.filler_words)
        self.assertIn("like", filler_eval.filler_words)

    def test_07_communication_analysis(self):
        transcript = "In our project, we implemented clean architectural patterns with decoupled services to improve code maintainability and testability."
        res = asyncio.run(CommunicationService.evaluate_communication(transcript, "Explain project architecture."))
        self.assertGreaterEqual(res.grammar_score, 0.0)
        self.assertLessEqual(res.grammar_score, 100.0)
        self.assertGreaterEqual(res.communication_score, 0.0)
        self.assertLessEqual(res.communication_score, 100.0)
        self.assertGreater(len(res.feedback), 5)

    def test_08_technical_evaluation(self):
        question = "How do you handle database transaction isolation and race conditions in PostgreSQL?"
        expected_focus = ["ACID properties", "isolation levels", "concurrency control"]
        answer = "We used serializable isolation levels and row-level locking to prevent race conditions during high concurrency balance updates."

        eval_res = asyncio.run(AnswerEvaluationService.evaluate_technical_answer(
            question_text=question,
            question_category="TECHNICAL",
            expected_focus=expected_focus,
            candidate_answer=answer,
            role_context="Backend Engineer"
        ))

        self.assertGreaterEqual(eval_res.technical_score, 0.0)
        self.assertLessEqual(eval_res.technical_score, 100.0)
        self.assertGreaterEqual(eval_res.correctness, 0.0)
        self.assertGreaterEqual(eval_res.completeness, 0.0)
        self.assertGreater(len(eval_res.feedback), 5)

    def test_09_vision_service_and_emotion_classifier(self):
        # Empty frame handling
        res_empty = VisionService.process_frame("")
        self.assertFalse(res_empty["face_detected"])

        # Emotion classifier reporting clean status
        emotion_res = EmotionRecognitionService.classify_facial_expression(None)
        self.assertIn("status", emotion_res)
        self.assertIn("dominant_emotion", emotion_res)
        self.assertIn("emotion_probabilities", emotion_res)

if __name__ == "__main__":
    unittest.main()
