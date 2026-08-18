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

        questions = asyncio.run(QuestionService.generate_initial_questions(
            interview_id=1,
            interview_type="company",
            company_name="Amazon",
            job_role="Cloud Engineer",
            resume=resume,
            jd=jd,
            skill_match=match,
            num_questions=5
        ))

        self.assertEqual(len(questions), 5)
        categories = [q.category for q in questions]
        self.assertIn("PROJECT", categories)
        self.assertIn("TECHNICAL", categories)
        self.assertIn("BEHAVIORAL", categories)

        for q in questions:
            self.assertGreater(len(q.question), 10)
            self.assertIn(q.difficulty, ["EASY", "MEDIUM", "HARD"])
            self.assertTrue(len(q.expected_focus) > 0)

    def test_05_dynamic_follow_up_generation(self):
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
        candidate_ans = "I used FastAPI for backend REST API endpoints, PostgreSQL for database transactions, and React for the frontend interface."

        follow_up = asyncio.run(QuestionService.generate_dynamic_follow_up(
            interview_id=1,
            parent_question=parent_q,
            candidate_answer=candidate_ans,
            topic_follow_up_count=0,
            total_questions_asked=1,
            job_role="Backend Developer"
        ))

        self.assertIsNotNone(follow_up)
        self.assertEqual(follow_up.source, "FOLLOW_UP")
        self.assertGreater(len(follow_up.question), 10)

        # Test limit reached (max follow-ups per topic)
        follow_up_limited = asyncio.run(QuestionService.generate_dynamic_follow_up(
            interview_id=1,
            parent_question=parent_q,
            candidate_answer=candidate_ans,
            topic_follow_up_count=3,
            total_questions_asked=1
        ))
        self.assertIsNone(follow_up_limited)

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
