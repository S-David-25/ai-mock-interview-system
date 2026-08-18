import unittest
from fpdf import FPDF
from starlette.testclient import TestClient
from app.main import app
from app.database.base import reset_db

def create_sample_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for line in text.split('\n'):
        pdf.cell(w=200, h=10, text=line, new_x="LMARGIN", new_y="NEXT")
    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return out.encode('latin-1')

class TestReportAndProgressEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

        # Register User A
        res1 = cls.client.post("/api/auth/register", json={
            "name": "Report Candidate",
            "email": "report.candidate@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token_a = res1.json()["access_token"]
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        # Register User B (for tenant isolation)
        res2 = cls.client.post("/api/auth/register", json={
            "name": "Unauthorized Candidate",
            "email": "unauthorized@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token_b = res2.json()["access_token"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    def _setup_completed_interview(self, company: str, role: str, score_val: float = 80.0):
        # 1. Create interview
        res_create = self.client.post("/api/interviews", json={
            "interview_type": "company",
            "company_name": company,
            "job_role": role
        }, headers=self.headers_a)
        int_id = res_create.json()["id"]

        # 2. Upload resume & JD
        resume_pdf = create_sample_pdf_bytes(
            "Candidate: Report Candidate\n"
            "Education: B.Tech Computer Science\n"
            "Skills: Python, FastAPI, React, PostgreSQL, Docker\n"
            "Projects: AI Smart Placement Engine"
        )
        jd_pdf = create_sample_pdf_bytes(
            f"Company: {company}\nRole: {role}\nRequirements: Python, FastAPI, Microservices, PostgreSQL, Spring Boot"
        )

        self.client.post(f"/api/interviews/{int_id}/upload-resume", files={"file": ("resume.pdf", resume_pdf, "application/pdf")}, headers=self.headers_a)
        self.client.post(f"/api/interviews/{int_id}/upload-jd", files={"file": ("jd.pdf", jd_pdf, "application/pdf")}, headers=self.headers_a)

        # 3. Process & Generate questions
        self.client.post(f"/api/interviews/{int_id}/process", headers=self.headers_a)
        q_res = self.client.post(f"/api/interviews/{int_id}/generate-questions", headers=self.headers_a)
        questions = q_res.json()["questions"]

        # 4. Start & Answer
        self.client.post(f"/api/interviews/{int_id}/start", headers=self.headers_a)
        for q in questions[:2]:
            self.client.post(f"/api/interviews/{int_id}/answer", json={
                "question_id": q["id"],
                "transcript": f"In our {company} preparation project, we implemented clean microservices architecture with PostgreSQL database indexing.",
                "speaking_duration": 15.0
            }, headers=self.headers_a)

        # Complete
        self.client.post(f"/api/interviews/{int_id}/complete", headers=self.headers_a)
        return int_id

    def test_01_generate_and_get_performance_report(self):
        int_id = self._setup_completed_interview("Amazon", "Cloud Developer")

        # 1. Generate Report
        res_rep = self.client.post(f"/api/interviews/{int_id}/generate-report", headers=self.headers_a)
        self.assertEqual(res_rep.status_code, 200)
        rep_data = res_rep.json()

        self.assertGreater(rep_data["overall_score"], 0.0)
        self.assertIn(rep_data["readiness_level"], ["Excellent", "Very Good", "Good", "Needs Improvement", "Requires Significant Improvement"])
        self.assertTrue(len(rep_data["strengths"]) > 0)
        self.assertTrue(len(rep_data["weaknesses"]) > 0)
        self.assertTrue(len(rep_data["roadmap"]["phases"]) == 5)

        # 2. Get Report
        res_get_rep = self.client.get(f"/api/interviews/{int_id}/report", headers=self.headers_a)
        self.assertEqual(res_get_rep.status_code, 200)
        self.assertEqual(res_get_rep.json()["overall_score"], rep_data["overall_score"])

        # 3. Get Score
        res_score = self.client.get(f"/api/interviews/{int_id}/score", headers=self.headers_a)
        self.assertEqual(res_score.status_code, 200)
        self.assertIn("dimensions", res_score.json())

        # 4. Get Roadmap
        res_road = self.client.get(f"/api/interviews/{int_id}/roadmap", headers=self.headers_a)
        self.assertEqual(res_road.status_code, 200)
        self.assertEqual(len(res_road.json()["phases"]), 5)

    def test_02_progress_tracking_and_comparison(self):
        # Create Interview 1
        id1 = self._setup_completed_interview("TCS", "Software Engineer")
        self.client.post(f"/api/interviews/{id1}/generate-report", headers=self.headers_a)

        # Create Interview 2
        id2 = self._setup_completed_interview("Google", "Backend Engineer")
        self.client.post(f"/api/interviews/{id2}/generate-report", headers=self.headers_a)

        # 1. Progress endpoint
        res_prog = self.client.get("/api/progress", headers=self.headers_a)
        self.assertEqual(res_prog.status_code, 200)
        prog_data = res_prog.json()
        self.assertGreaterEqual(prog_data["interview_count"], 2)
        self.assertIsNotNone(prog_data["average_score"])
        self.assertIsNotNone(prog_data["best_score"])
        self.assertTrue(len(prog_data["trend_data"]) >= 2)
        self.assertTrue(len(prog_data["category_trends"]) > 0)

        # 2. Comparison endpoint (Interview 1 vs Interview 2)
        res_comp = self.client.get(f"/api/interviews/compare?first_id={id1}&second_id={id2}", headers=self.headers_a)
        self.assertEqual(res_comp.status_code, 200)
        comp_data = res_comp.json()
        self.assertEqual(comp_data["first_interview_id"], id1)
        self.assertEqual(comp_data["second_interview_id"], id2)
        self.assertIn("dimension_comparisons", comp_data)
        self.assertIn(comp_data["overall_status"], ["Improved", "Declined", "Unchanged"])

    def test_03_tenant_isolation_on_reports_and_progress(self):
        id_a = self._setup_completed_interview("Microsoft", "Full Stack")
        self.client.post(f"/api/interviews/{id_a}/generate-report", headers=self.headers_a)

        # User B attempts to access User A's report, score, roadmap
        res_rep_b = self.client.get(f"/api/interviews/{id_a}/report", headers=self.headers_b)
        self.assertEqual(res_rep_b.status_code, 404)

        res_score_b = self.client.get(f"/api/interviews/{id_a}/score", headers=self.headers_b)
        self.assertEqual(res_score_b.status_code, 404)

        res_road_b = self.client.get(f"/api/interviews/{id_a}/roadmap", headers=self.headers_b)
        self.assertEqual(res_road_b.status_code, 404)

        # User B attempts to compare User A's interview
        res_comp_b = self.client.get(f"/api/interviews/compare?first_id={id_a}&second_id={id_a}", headers=self.headers_b)
        self.assertEqual(res_comp_b.status_code, 404)

if __name__ == "__main__":
    unittest.main()
