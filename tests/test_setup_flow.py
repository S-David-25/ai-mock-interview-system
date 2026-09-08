import unittest
from starlette.testclient import TestClient
from app.main import app
from app.database.session import DatabaseSession

class TestInterviewSetupFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = DatabaseSession()

        # Register and login test user
        cls.email = "setup_tester@example.com"
        cls.password = "SecurePass123!"
        cls.client.post("/api/auth/register", json={
            "name": "Setup Tester",
            "email": cls.email,
            "password": cls.password,
            "confirm_password": cls.password
        })
        login_res = cls.client.post("/api/auth/login", json={
            "email": cls.email,
            "password": cls.password
        })
        assert login_res.status_code == 200
        cls.token = login_res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_complete_setup_to_launch_flow(self):
        """
        Tests the entire end-to-end user journey:
        Setup -> Upload -> Process -> Check ATS Data Persistence -> Launch Session -> Verify Readiness.
        """
        # 1. Create Interview
        create_res = self.client.post(
            "/api/interviews",
            json={
                "interview_type": "company",
                "company_name": "Google",
                "job_role": "Backend Engineer",
                "duration_minutes": 30
            },
            headers=self.headers
        )
        self.assertEqual(create_res.status_code, 201)
        int_data = create_res.json()
        int_id = int_data["id"]
        self.assertEqual(int_data["status"], "setup")

        # 2. Submit JD Text
        jd_sample = """
        Company: Google
        Role: Backend Engineer
        Required Skills: Python, FastAPI, PostgreSQL, Redis, Distributed Systems, Docker, Kubernetes
        Experience Requirements: Bachelor's degree in Computer Science or related field. 3+ years backend experience.
        Responsibilities: Build scalable high-throughput microservices, design database schemas, and optimize low-latency APIs.
        """
        jd_res = self.client.post(
            f"/api/interviews/{int_id}/submit-jd",
            data={"jd_text": jd_sample},
            headers=self.headers
        )
        self.assertEqual(jd_res.status_code, 200)

        # 3. Upload Resume
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        resume_text = "Candidate: Setup Tester\nEmail: setup.tester@example.com\nPhone: +1-555-0188\nEducation: Bachelor of Technology in Computer Science\nSkills: Python, FastAPI, PostgreSQL, Redis, Docker, Git, REST APIs\nProjects: Scalable API Gateway built with FastAPI, PostgreSQL, and Redis caching.\nExperience: Backend Developer at CloudTech developing distributed services in Python."
        for line in resume_text.split('\n'):
            pdf.cell(w=200, h=10, txt=line, ln=1)
        pdf_bytes = pdf.output(dest='S').encode('latin-1')

        resume_res = self.client.post(
            f"/api/interviews/{int_id}/upload-resume",
            files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
            headers=self.headers
        )
        self.assertEqual(resume_res.status_code, 200)

        # 4. Check initial detail load (Before processing)
        detail_res_1 = self.client.get(f"/api/interviews/{int_id}", headers=self.headers)
        self.assertEqual(detail_res_1.status_code, 200)
        d1 = detail_res_1.json()
        self.assertTrue(d1["is_resume_uploaded"])
        self.assertTrue(d1["is_jd_uploaded"])
        self.assertIsNone(d1["resume_analysis"])
        self.assertIsNone(d1["ats_analysis"])

        # 5. Process Documents (/api/interviews/{id}/process)
        proc_res = self.client.post(f"/api/interviews/{int_id}/process", headers=self.headers)
        self.assertEqual(proc_res.status_code, 200)
        proc_data = proc_res.json()
        self.assertEqual(proc_data["status"], "processed")
        self.assertIsNotNone(proc_data["resume_analysis"])
        self.assertIsNotNone(proc_data["jd_analysis"])
        self.assertIsNotNone(proc_data["ats_analysis"])

        ats = proc_data["ats_analysis"]
        self.assertIn("ats_score", ats)
        self.assertIn("matched_skills", ats)
        self.assertIn("missing_skills", ats)
        self.assertIn("keyword_coverage", ats)
        self.assertGreater(ats["ats_score"], 0)

        # 6. Verify Persistent Refresh / Direct URL loading (GET /api/interviews/{id})
        detail_res_2 = self.client.get(f"/api/interviews/{int_id}", headers=self.headers)
        self.assertEqual(detail_res_2.status_code, 200)
        d2 = detail_res_2.json()
        self.assertEqual(d2["status"], "ready")
        self.assertIsNotNone(d2["resume_analysis"])
        self.assertIsNotNone(d2["ats_analysis"])
        self.assertEqual(d2["ats_analysis"]["ats_score"], ats["ats_score"])

        # 7. Check Status Endpoint
        status_res = self.client.get(f"/api/interviews/{int_id}/status", headers=self.headers)
        self.assertEqual(status_res.status_code, 200)
        s_data = status_res.json()
        self.assertTrue(s_data["is_ready"])
        self.assertEqual(s_data["status"], "ready")

        # 8. Generate Questions & Start Interview (Simulating Launch button)
        gen_res = self.client.post(f"/api/interviews/{int_id}/generate-questions", headers=self.headers)
        self.assertEqual(gen_res.status_code, 200)
        questions = gen_res.json()["questions"]
        self.assertGreaterEqual(len(questions), 1)

        start_res = self.client.post(f"/api/interviews/{int_id}/start", headers=self.headers)
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.json()["status"], "in_progress")
        self.assertIsNotNone(start_res.json()["expires_at"])

if __name__ == "__main__":
    unittest.main()
