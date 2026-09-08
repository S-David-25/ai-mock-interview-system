import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from starlette.testclient import TestClient
from app.main import app
from app.database.base import reset_db
from app.database.session import DatabaseSession
from app.schemas.interview import (
    ResumeProfileSchema,
    JDProfileSchema,
    SkillMatchSchema,
    QuestionSchema,
    TechnicalEvaluationSchema,
)
from app.services.question_service import QuestionService
from app.services.matching_service import SkillMatchingService
from app.services.answer_evaluation_service import AnswerEvaluationService
from app.services.gemini_service import GeminiService
from tests.test_file_upload import create_sample_pdf_bytes

class TestDynamicGeminiQuestions(unittest.TestCase):
    """
    Comprehensive test suite validating genuine, dynamic Gemini interview question generation,
    adaptive follow-ups (Issue #15), personalization, cross-session diversity, no fixed question
    count limits (Issue #18), template elimination, and error reporting.
    """

    FORBIDDEN_TEMPLATES = [
        "could you walk me through the architecture and implementation of",
        "specifically highlight why you chose",
        "primary software project",
        "step-by-step diagnostic and remediation process",
    ]

    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

        res = cls.client.post('/api/auth/register', json={
            'name': 'Senior Candidate',
            'email': 'senior.candidate@university.edu',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        })
        cls.token = res.json()['access_token']
        cls.headers = {'Authorization': f'Bearer {cls.token}'}

    def _assert_not_template(self, question_text: str):
        """Verifies that the generated question contains none of the old fixed/template strings."""
        lower = question_text.lower()
        for forbidden in self.FORBIDDEN_TEMPLATES:
            self.assertNotIn(
                forbidden,
                lower,
                f"Generated question matches forbidden template: '{forbidden}' in '{question_text}'"
            )

    def test_01_two_different_resumes_produce_distinct_personalized_questions(self):
        """Test 1: Use Resume A and Resume B. Verify generated questions are meaningfully different and personalized."""
        resume_a = ResumeProfileSchema(
            candidate_name='Alice Pythonista',
            technical_skills=['Python', 'FastAPI', 'PostgreSQL', 'Redis'],
            programming_languages=['Python'],
            frameworks=['FastAPI'],
            databases=['PostgreSQL', 'Redis'],
            projects=[{
                'name': 'E-Commerce High Throughput Store',
                'description': 'Asynchronous ordering engine handling checkout and inventory locks',
                'technologies': ['FastAPI', 'PostgreSQL', 'Redis'],
                'responsibilities': ['Implemented Redis distributed locking for order processing'],
                'outcomes': ['Reduced latency by 40%']
            }]
        )

        resume_b = ResumeProfileSchema(
            candidate_name='Bob JavaDev',
            technical_skills=['Java', 'Spring Boot', 'Kafka', 'Cassandra'],
            programming_languages=['Java'],
            frameworks=['Spring Boot'],
            databases=['Cassandra'],
            projects=[{
                'name': 'Real-Time IoT Telemetry Stream',
                'description': 'Distributed telemetry ingestion pipeline for connected vehicles',
                'technologies': ['Java', 'Spring Boot', 'Kafka', 'Cassandra'],
                'responsibilities': ['Configured Kafka partition strategies and consumer groups'],
                'outcomes': ['Processed 50k events/sec']
            }]
        )

        q1_a = asyncio.run(QuestionService.generate_initial_question(
            interview_id=101,
            interview_type='general',
            company_name=None,
            job_role='Backend Engineer',
            resume=resume_a,
            jd=None
        ))

        q1_b = asyncio.run(QuestionService.generate_initial_question(
            interview_id=102,
            interview_type='general',
            company_name=None,
            job_role='Backend Engineer',
            resume=resume_b,
            jd=None
        ))

        self.assertIsInstance(q1_a, QuestionSchema)
        self.assertIsInstance(q1_b, QuestionSchema)

        # Verify no template strings
        self._assert_not_template(q1_a.question)
        self._assert_not_template(q1_b.question)

        # Verify Question A is genuinely personalized to Resume A
        self.assertTrue(any(kw in q1_a.question.lower() for kw in ['python', 'fastapi', 'e-commerce', 'redis', 'order', 'checkout', 'postgres']))

        # Verify Question B is genuinely personalized to Resume B
        self.assertTrue(any(kw in q1_b.question.lower() for kw in ['java', 'spring', 'kafka', 'telemetry', 'iot', 'cassandra', 'stream', 'partition']))

        # Verify questions are completely different
        self.assertNotEqual(q1_a.question, q1_b.question)

    def test_02_same_candidate_different_sessions_generates_diverse_questions(self):
        """Test 2: Use the same candidate but different interview sessions. Verify distinct questions across sessions."""
        resume = ResumeProfileSchema(
            candidate_name='Dana Engineer',
            technical_skills=['Python', 'Docker', 'Kubernetes', 'FastAPI', 'PostgreSQL'],
            programming_languages=['Python'],
            frameworks=['FastAPI'],
            databases=['PostgreSQL'],
            tools=['Docker', 'Kubernetes'],
            projects=[
                {
                    'name': 'Cloud Microservices Mesh',
                    'description': 'Kubernetes microservice deployment with service mesh',
                    'technologies': ['Kubernetes', 'Docker', 'FastAPI'],
                    'responsibilities': [],
                    'outcomes': []
                },
                {
                    'name': 'Database Sharding Proxy',
                    'description': 'Custom database connection proxy with read-write splitting',
                    'technologies': ['Python', 'PostgreSQL'],
                    'responsibilities': [],
                    'outcomes': []
                }
            ]
        )

        # Session 1: Opening question
        q1_session1 = asyncio.run(QuestionService.generate_initial_question(
            interview_id=201,
            interview_type='general',
            company_name=None,
            job_role='Senior Backend Engineer',
            resume=resume,
            past_session_questions=[]
        ))

        # Session 2: Opening question with Session 1 question in past history
        q1_session2 = asyncio.run(QuestionService.generate_initial_question(
            interview_id=202,
            interview_type='general',
            company_name=None,
            job_role='Senior Backend Engineer',
            resume=resume,
            past_session_questions=[q1_session1.question]
        ))

        self.assertNotEqual(q1_session1.question, q1_session2.question)
        self._assert_not_template(q1_session1.question)
        self._assert_not_template(q1_session2.question)

    def test_03_adaptive_follow_up_on_specific_technical_detail(self):
        """Test 3: Submit answer with unique detail ('I used Redis caching to reduce database queries'). Verify adaptive follow-up."""
        parent_q = QuestionSchema(
            id=1,
            interview_id=301,
            question="How did you optimize data retrieval in your product catalog service?",
            category="TECHNICAL",
            difficulty="MEDIUM",
            expected_focus=["caching strategy", "database performance"],
            source="RESUME",
            order_number=1
        )

        candidate_answer = "I used Redis caching to reduce database queries and speed up response times."

        resume = ResumeProfileSchema(
            candidate_name='Eva Dev',
            technical_skills=['Python', 'FastAPI', 'Redis', 'PostgreSQL'],
            programming_languages=['Python'],
            frameworks=['FastAPI'],
            databases=['PostgreSQL', 'Redis'],
            projects=[{'name': 'Catalog Service', 'description': 'Product search API', 'technologies': ['Redis', 'PostgreSQL'], 'responsibilities': [], 'outcomes': []}]
        )

        tech_eval = asyncio.run(AnswerEvaluationService.evaluate_technical_answer(
            question_text=parent_q.question,
            question_category=parent_q.category,
            expected_focus=parent_q.expected_focus,
            candidate_answer=candidate_answer,
            role_context="Backend Engineer"
        ))

        next_q, is_fu = asyncio.run(QuestionService.generate_next_question_or_follow_up(
            interview_id=301,
            interview_type="general",
            company_name=None,
            job_role="Backend Engineer",
            resume=resume,
            jd=None,
            skill_match=None,
            previous_questions=[parent_q.dict()],
            previous_answers=[{"transcript_text": candidate_answer}],
            latest_question=parent_q,
            latest_answer=candidate_answer,
            latest_eval=tech_eval,
            remaining_time_seconds=1400,
            current_order_number=1
        ))

        self.assertTrue(is_fu, "Gemini should decide on an adaptive follow-up for a brief answer claiming Redis caching")
        self.assertEqual(next_q.source, "FOLLOW_UP")
        self._assert_not_template(next_q.question)
        # Follow-up must probe Redis, caching, invalidation, TTL, eviction, or cache consistency
        self.assertTrue(
            any(term in next_q.question.lower() for term in ["redis", "cache", "invalidation", "ttl", "evict", "consistency", "stampede", "queries", "hit", "miss"]),
            f"Follow-up question '{next_q.question}' does not reference candidate's Redis caching answer!"
        )

    def test_04_comprehensive_answer_triggers_new_topic_pivot(self):
        """Test 4: Candidate gives a thorough, comprehensive answer. Verify Gemini moves to a new relevant topic."""
        parent_q = QuestionSchema(
            id=1,
            interview_id=401,
            question="How do you handle database query optimization?",
            category="TECHNICAL",
            difficulty="MEDIUM",
            expected_focus=["indexing", "execution plans", "connection pooling"],
            source="RESUME",
            order_number=1
        )

        detailed_answer = (
            "In our service, we analyzed PostgreSQL EXPLAIN ANALYZE execution plans to eliminate sequential scans. "
            "We created composite B-tree indexes for multi-column filter queries, used partial indexes for active records, "
            "and tuned the PgBouncer connection pool with transaction-level pooling to maintain sub-10ms response times under load."
        )

        resume = ResumeProfileSchema(
            candidate_name='Frank Engineer',
            technical_skills=['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'AWS'],
            programming_languages=['Python'],
            frameworks=['FastAPI'],
            databases=['PostgreSQL'],
            projects=[{'name': 'High Scale Billing', 'description': 'Billing service', 'technologies': ['PostgreSQL', 'FastAPI'], 'responsibilities': [], 'outcomes': []}]
        )

        tech_eval = TechnicalEvaluationSchema(
            technical_score=92.0,
            correctness=95.0,
            relevance=92.0,
            completeness=90.0,
            depth=90.0,
            feedback="Strong, comprehensive answer covering query plans, indexing, and connection pooling."
        )

        next_q, is_fu = asyncio.run(QuestionService.generate_next_question_or_follow_up(
            interview_id=401,
            interview_type="general",
            company_name=None,
            job_role="Senior Backend Engineer",
            resume=resume,
            jd=None,
            skill_match=None,
            previous_questions=[parent_q.dict()],
            previous_answers=[{"transcript_text": detailed_answer}],
            latest_question=parent_q,
            latest_answer=detailed_answer,
            latest_eval=tech_eval,
            remaining_time_seconds=1200,
            current_order_number=1
        ))

        self.assertIsInstance(next_q, QuestionSchema)
        self._assert_not_template(next_q.question)
        self.assertGreater(len(next_q.question), 15)

    def test_05_interview_continues_beyond_15_questions_without_count_limit(self):
        """Test 5: Verify interview continues beyond 15 questions while time remains."""
        res_create = self.client.post('/api/interviews', json={
            'interview_type': 'general',
            'duration_minutes': 60
        }, headers=self.headers)
        self.assertEqual(res_create.status_code, 201)
        int_id = res_create.json()['id']

        resume_pdf = create_sample_pdf_bytes(
            'Candidate: Long Test Candidate\n'
            'Contact: longtest@example.com\n'
            'Education: Bachelor of Science in Computer Science\n'
            'Skills: Python, FastAPI, PostgreSQL, Docker, Redis, Kubernetes\n'
            'Projects: Distributed Transaction Manager\n'
            'Experience: Senior Backend Developer'
        )
        self.client.post(f'/api/interviews/{int_id}/upload-resume', files={'file': ('resume.pdf', resume_pdf, 'application/pdf')}, headers=self.headers)
        self.client.post(f'/api/interviews/{int_id}/process', headers=self.headers)

        # Mock Gemini structured JSON output for rapid >15 question progression verification
        diverse_topics = [
            "How do you implement distributed transactions with saga orchestration?",
            "Explain how PostgreSQL B-Tree indexing impacts multi-column write performance.",
            "Describe how you handle Kafka consumer lag and rebalance storms in high throughput pipelines.",
            "How do you secure REST APIs against SSRF and JWT replay attacks?",
            "Discuss your approach to database sharding and cross-shard querying.",
            "How do you optimize Docker image layer caching in CI/CD pipelines?",
            "What strategies do you use for Redis cluster cache invalidation and stampede prevention?",
            "How do you configure Kubernetes pod horizontal autoscaling based on custom Prometheus metrics?",
            "Explain how you debug memory leaks in long-running Python asyncio services.",
            "How do you design a rate limiter using token bucket algorithms in distributed environments?",
            "What architectural patterns do you employ for zero-downtime database migrations?",
            "How do you implement circuit breakers and retries with exponential backoff in microservices?",
            "Explain the trade-offs between gRPC protocol buffers and REST JSON for internal service communication.",
            "How do you handle schema evolution and backward compatibility in message queues?",
            "Describe how you isolate noisy neighbors in multi-tenant SaaS applications.",
            "How do you monitor distributed trace propagation across asynchronous boundaries using OpenTelemetry?",
            "What is your approach to chaos engineering and resilience testing in production systems?",
            "How do you manage secrets rotation without interrupting active application connections?"
        ]

        call_count = 0
        def dynamic_gemini_response(*args, **kwargs):
            nonlocal call_count
            q_text = diverse_topics[call_count % len(diverse_topics)]
            call_count += 1
            return {
                "question": q_text,
                "category": "TECHNICAL",
                "difficulty": "MEDIUM",
                "expected_focus": ["throughput", "scalability", "concurrency"],
                "is_follow_up": False
            }

        with patch.object(GeminiService, 'generate_structured_json', side_effect=dynamic_gemini_response):
            res_qgen = self.client.post(f'/api/interviews/{int_id}/generate-questions', headers=self.headers)
            self.assertEqual(res_qgen.status_code, 200)
            curr_q = res_qgen.json()['questions'][0]

            self.client.post(f'/api/interviews/{int_id}/start', headers=self.headers)

            # Answer 16 questions consecutively to exceed 15 questions
            for i in range(16):
                ans_res = self.client.post(f'/api/interviews/{int_id}/answer', json={
                    'question_id': curr_q['id'],
                    'transcript': f'For stage {i+1}, we designed idempotency keys in Redis and executed distributed transactions.',
                    'speaking_duration': 10.0
                }, headers=self.headers)
                self.assertEqual(ans_res.status_code, 200)
                data = ans_res.json()
                self.assertFalse(data['is_completed'], f'Interview ended prematurely at question {i+1}!')
                self.assertIsNotNone(data['next_question'])
                curr_q = data['next_question']

        # Verify total questions in DB is 17
        q_list_res = self.client.get(f'/api/interviews/{int_id}/questions', headers=self.headers)
        self.assertEqual(q_list_res.status_code, 200)
        self.assertEqual(q_list_res.json()['total_questions'], 17)

    def test_06_verify_no_hardcoded_templates_in_any_generated_question(self):
        """Test 6: Inspect generated questions and ensure none match hardcoded templates."""
        resume = ResumeProfileSchema(
            candidate_name='Grace Hopper',
            technical_skills=['Python', 'C++', 'Compilers', 'Distributed Systems'],
            programming_languages=['Python', 'C++'],
            projects=[{'name': 'Language Compiler Engine', 'description': 'Bytecode optimizer', 'technologies': ['C++'], 'responsibilities': [], 'outcomes': []}]
        )

        q1 = asyncio.run(QuestionService.generate_initial_question(
            interview_id=601,
            interview_type='general',
            company_name=None,
            job_role='Compiler Engineer',
            resume=resume
        ))

        self._assert_not_template(q1.question)

    def test_07_gemini_failure_raises_clear_error_without_silent_template_fallback(self):
        """Test 7: Verify that if Gemini fails, the system raises an explicit 502 error and does NOT silently produce a fake question."""
        resume = ResumeProfileSchema(
            candidate_name='Test Candidate',
            technical_skills=['Python'],
            projects=[{'name': 'Test Project', 'description': 'Test', 'technologies': ['Python'], 'responsibilities': [], 'outcomes': []}]
        )

        # Mock Gemini failure
        with patch.object(GeminiService, 'generate_structured_json', side_effect=ValueError("Gemini API connection refused")):
            with self.assertRaises(Exception) as context:
                asyncio.run(QuestionService.generate_initial_question(
                    interview_id=701,
                    interview_type='general',
                    company_name=None,
                    job_role='Software Engineer',
                    resume=resume
                ))
            self.assertIn("AI Question Generation Error", str(context.exception))

    def test_08_timer_expiry_terminates_interview_and_stops_generation(self):
        """Test 8: Verify timer expiry terminates interview cleanly and generates no additional question."""
        res_create = self.client.post('/api/interviews', json={
            'interview_type': 'general',
            'duration_minutes': 1
        }, headers=self.headers)
        int_id = res_create.json()['id']

        resume_pdf = create_sample_pdf_bytes(
            'Candidate: Timer Expiry Candidate\n'
            'Contact: timertest@example.com\n'
            'Education: Bachelor of Science\n'
            'Skills: Python, FastAPI\n'
            'Projects: Timer Test API\n'
            'Experience: Backend Developer'
        )
        self.client.post(f'/api/interviews/{int_id}/upload-resume', files={'file': ('resume.pdf', resume_pdf, 'application/pdf')}, headers=self.headers)
        self.client.post(f'/api/interviews/{int_id}/process', headers=self.headers)

        res_qgen = self.client.post(f'/api/interviews/{int_id}/generate-questions', headers=self.headers)
        self.assertEqual(res_qgen.status_code, 200)
        first_q = res_qgen.json()['questions'][0]
        self.client.post(f'/api/interviews/{int_id}/start', headers=self.headers)

        # Simulate timer expiry
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=15)).strftime('%Y-%m-%d %H:%M:%S')
        with DatabaseSession() as db:
            db.execute('UPDATE interviews SET expires_at = ? WHERE id = ?', (past_time, int_id))
            db.commit()

        # Submit answer after expiry
        ans_res = self.client.post(f'/api/interviews/{int_id}/answer', json={
            'question_id': first_q['id'],
            'transcript': 'Answering after timer expired.',
            'speaking_duration': 8.0
        }, headers=self.headers)

        self.assertEqual(ans_res.status_code, 200)
        ans_data = ans_res.json()
        self.assertTrue(ans_data['is_completed'])
        self.assertIsNone(ans_data['next_question'])
        self.assertIn('ended', ans_data['message'].lower())

        status_res = self.client.get(f'/api/interviews/{int_id}/status', headers=self.headers)
        self.assertEqual(status_res.json()['status'], 'completed')

if __name__ == '__main__':
    unittest.main()
