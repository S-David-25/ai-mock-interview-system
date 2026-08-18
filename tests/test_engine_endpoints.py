import unittest
import io
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

class TestInterviewEngineEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

        # Register User 1
        res1 = cls.client.post("/api/auth/register", json={
            "name": "Engine Candidate",
            "email": "engine.candidate@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token1 = res1.json()["access_token"]
        cls.headers1 = {"Authorization": f"Bearer {cls.token1}"}

        # Register User 2 (for tenant isolation tests)
        res2 = cls.client.post("/api/auth/register", json={
            "name": "Other Candidate",
            "email": "other.candidate@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token2 = res2.json()["access_token"]
        cls.headers2 = {"Authorization": f"Bearer {cls.token2}"}

    def test_01_full_interview_engine_workflow(self):
        # 1. Create company mock interview
        res_create = self.client.post("/api/interviews", json={
            "interview_type": "company",
            "company_name": "Microsoft",
            "job_role": "Cloud Software Engineer"
        }, headers=self.headers1)
        self.assertEqual(res_create.status_code, 201)
        int_id = res_create.json()["id"]

        # 2. Upload Resume & JD
        resume_pdf = create_sample_pdf_bytes(
            "Candidate: Alex Johnson\n"
            "Education: BS in Information Technology\n"
            "Skills: Python, FastAPI, Docker, PostgreSQL, React, Git\n"
            "Projects: Cloud Monitoring System using FastAPI and React."
        )
        self.client.post(
            f"/api/interviews/{int_id}/upload-resume",
            files={"file": ("resume.pdf", resume_pdf, "application/pdf")},
            headers=self.headers1
        )

        jd_pdf = create_sample_pdf_bytes(
            "Company: Microsoft\n"
            "Role: Cloud Software Engineer\n"
            "Requirements: Python, Azure, Kubernetes, Microservices, PostgreSQL, CI/CD.\n"
            "Strong team collaboration and technical problem solving."
        )
        self.client.post(
            f"/api/interviews/{int_id}/upload-jd",
            files={"file": ("microsoft_jd.pdf", jd_pdf, "application/pdf")},
            headers=self.headers1
        )

        # 3. Document Processing Endpoint
        res_proc = self.client.post(f"/api/interviews/{int_id}/process", headers=self.headers1)
        self.assertEqual(res_proc.status_code, 200)
        proc_data = res_proc.json()
        self.assertEqual(proc_data["status"], "processed")
        self.assertIn("Python", proc_data["resume_analysis"]["technical_skills"])
        self.assertIn("Azure", proc_data["skill_match"]["skill_gaps"])

        # 4. Question Generation Endpoint
        res_qgen = self.client.post(f"/api/interviews/{int_id}/generate-questions", headers=self.headers1)
        self.assertEqual(res_qgen.status_code, 200)
        q_data = res_qgen.json()
        self.assertEqual(q_data["total_questions"], 5)
        questions = q_data["questions"]
        first_q = questions[0]
        self.assertIn("id", first_q)
        self.assertIn(first_q["category"], ["PROJECT", "TECHNICAL", "SKILL_GAP", "BEHAVIORAL", "SITUATIONAL"])

        # 5. List Questions Endpoint
        res_qlist = self.client.get(f"/api/interviews/{int_id}/questions", headers=self.headers1)
        self.assertEqual(res_qlist.status_code, 200)
        self.assertEqual(res_qlist.json()["total_questions"], 5)

        # 6. Start Interview Session
        res_start = self.client.post(f"/api/interviews/{int_id}/start", headers=self.headers1)
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.json()["status"], "in_progress")

        # 7. Test Audio Transcription Endpoint
        sample_audio = io.BytesIO(b"fake wav audio header and speech data")
        res_trans = self.client.post(
            f"/api/interviews/{int_id}/transcribe",
            files={"file": ("recording.wav", sample_audio, "audio/wav")},
            data={"fallback_text": "I utilized FastAPI for the backend architecture with asynchronous endpoints."},
            headers=self.headers1
        )
        self.assertEqual(res_trans.status_code, 200)
        self.assertIn("FastAPI", res_trans.json()["transcript"])

        # 8. Submit Answer & Receive Dynamic Follow-up
        answer_payload = {
            "question_id": first_q["id"],
            "transcript": "In our Cloud Monitoring project, we chose FastAPI and PostgreSQL because of high async throughput and relational ACID transactions.",
            "speaking_duration": 12.5,
            "audio_filename": res_trans.json()["audio_filename"]
        }
        res_ans = self.client.post(f"/api/interviews/{int_id}/answer", json=answer_payload, headers=self.headers1)
        self.assertEqual(res_ans.status_code, 200)
        ans_data = res_ans.json()
        self.assertIn("technical_evaluation", ans_data)
        self.assertIn("communication_evaluation", ans_data)
        self.assertIn("fluency_evaluation", ans_data)
        self.assertGreater(ans_data["technical_evaluation"]["technical_score"], 0.0)
        self.assertGreater(ans_data["fluency_evaluation"]["fluency_score"], 0.0)
        self.assertIsNotNone(ans_data["next_question"])

        # 9. Vision Frame Analysis Endpoint
        res_vision = self.client.post(
            f"/api/interviews/{int_id}/vision-frame",
            json={"question_id": first_q["id"], "image_base64": ""},
            headers=self.headers1
        )
        self.assertEqual(res_vision.status_code, 200)
        self.assertIn("dominant_emotion", res_vision.json())

        # 10. Complete Interview Session
        res_comp = self.client.post(f"/api/interviews/{int_id}/complete", headers=self.headers1)
        self.assertEqual(res_comp.status_code, 200)
        self.assertEqual(res_comp.json()["status"], "completed")

    def test_02_tenant_isolation_on_engine_endpoints(self):
        # User 1 creates interview
        res_create = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=self.headers1)
        u1_int_id = res_create.json()["id"]

        # User 2 attempts to process or access User 1's interview
        res_unauth_proc = self.client.post(f"/api/interviews/{u1_int_id}/process", headers=self.headers2)
        self.assertEqual(res_unauth_proc.status_code, 404)

        res_unauth_q = self.client.get(f"/api/interviews/{u1_int_id}/questions", headers=self.headers2)
        self.assertEqual(res_unauth_q.status_code, 404)

        res_unauth_ans = self.client.post(f"/api/interviews/{u1_int_id}/answer", json={
            "question_id": 1,
            "transcript": "Attempted cross tenant answer"
        }, headers=self.headers2)
        self.assertEqual(res_unauth_ans.status_code, 404)

if __name__ == "__main__":
    unittest.main()
