import unittest
import io
import math
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch
from fpdf import FPDF
from starlette.testclient import TestClient
from app.main import app
from app.database.base import reset_db

def create_sample_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for line in text.split('\n'):
        try:
            pdf.cell(w=200, h=10, txt=line, ln=1)
        except TypeError:
            pdf.cell(w=200, h=10, text=line)
    try:
        out = pdf.output(dest='S')
    except Exception:
        out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return out.encode('latin-1')


def create_test_wav_bytes(duration_seconds: float = 1.0) -> bytes:
    sample_rate = 16000
    frames = int(sample_rate * duration_seconds)
    samples = (struct.pack('<h', int(5000 * math.sin(2 * math.pi * 440 * index / sample_rate))) for index in range(frames))
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(samples))
    return audio.getvalue()

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

        # 4. Question Generation Endpoint (Generates Question 1 dynamically)
        res_qgen = self.client.post(f"/api/interviews/{int_id}/generate-questions", headers=self.headers1)
        self.assertEqual(res_qgen.status_code, 200)
        q_data = res_qgen.json()
        self.assertEqual(q_data["total_questions"], 1)
        questions = q_data["questions"]
        first_q = questions[0]
        self.assertIn("id", first_q)
        self.assertEqual(first_q["order_number"], 1)
        self.assertEqual(first_q["status"], "pending")

        # 5. List Questions Endpoint
        res_qlist = self.client.get(f"/api/interviews/{int_id}/questions", headers=self.headers1)
        self.assertEqual(res_qlist.status_code, 200)
        self.assertEqual(res_qlist.json()["total_questions"], 1)

        # 6. Start Interview Session
        res_start = self.client.post(f"/api/interviews/{int_id}/start", headers=self.headers1)
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.json()["status"], "in_progress")

        # 7. Test Audio Transcription Endpoint
        sample_audio = io.BytesIO(b"fake wav audio header and speech data")
        class FakeWhisper:
            def transcribe(self, path, **kwargs):
                return {"text": "I utilized FastAPI for the backend architecture with asynchronous endpoints."}

        with patch("app.services.transcription_service._whisper_available", True), patch("app.services.transcription_service._whisper_model", FakeWhisper()):
            res_trans = self.client.post(
                f"/api/interviews/{int_id}/transcribe",
                files={"file": ("recording.wav", sample_audio, "audio/wav")},
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

    def test_03_empty_whisper_result_does_not_use_submitted_fallback_text(self):
        res_create = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=self.headers1)
        interview_id = res_create.json()["id"]
        fallback_text = "I designed the service using FastAPI and deployed the API with Docker on AWS."

        class EmptyWhisper:
            def transcribe(self, path, **kwargs):
                return {"text": ""}

        with tempfile.TemporaryDirectory() as audio_dir:
            with patch("app.services.transcription_service.AUDIO_UPLOAD_DIR", Path(audio_dir)), \
                 patch("app.services.transcription_service._whisper_available", True), \
                 patch("app.services.transcription_service._whisper_model", EmptyWhisper()):
                resp = self.client.post(
                    f"/api/interviews/{interview_id}/transcribe",
                    data={"fallback_text": fallback_text, "question_context": "Explain your architecture."},
                    files={"file": ("recording.wav", create_test_wav_bytes(), "audio/wav")},
                    headers=self.headers1,
                )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["transcript"], "")
        self.assertEqual(resp.json()["transcription_status"], "failed")
        self.assertEqual(resp.json()["word_count"], 0)

    def test_04_whisper_transcript_is_untranslated_and_preserved_verbatim(self):
        res_create = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=self.headers1)
        interview_id = res_create.json()["id"]
        expected_transcript = "I built a REST API with Python, FastAPI, and PostgreSQL in 2025."

        class FaithfulWhisper:
            def transcribe(self, path, **kwargs):
                self.kwargs = kwargs
                with wave.open(path, 'rb') as wav_file:
                    self.duration = wav_file.getnframes() / wav_file.getframerate()
                return {"text": expected_transcript}

        recognizer = FaithfulWhisper()
        with tempfile.TemporaryDirectory() as audio_dir:
            with patch("app.services.transcription_service.AUDIO_UPLOAD_DIR", Path(audio_dir)), \
                 patch("app.services.transcription_service._whisper_available", True), \
                 patch("app.services.transcription_service._whisper_model", recognizer):
                response = self.client.post(
                    f"/api/interviews/{interview_id}/transcribe",
                    data={"question_context": "Explain a Java system."},
                    files={"file": ("recording.wav", create_test_wav_bytes(2.5), "audio/wav")},
                    headers=self.headers1,
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transcript"], expected_transcript)
        self.assertEqual(response.json()["transcription_status"], "completed")
        self.assertEqual(response.json()["duration_seconds"], 2.5)
        self.assertEqual(response.json()["word_count"], len(expected_transcript.split()))
        self.assertEqual(recognizer.kwargs["language"], "en")
        self.assertEqual(recognizer.kwargs["task"], "transcribe")
        self.assertNotIn("initial_prompt", recognizer.kwargs)

    def test_05_canonical_transcript_is_stored_and_used_for_all_evaluations(self):
        from app.database.session import DatabaseSession
        from app.schemas.interview import (
            CommunicationEvaluationSchema,
            FluencyEvaluationSchema,
            QuestionSchema,
            TechnicalEvaluationSchema,
        )

        created = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=self.headers1)
        interview_id = created.json()["id"]
        with DatabaseSession() as db:
            db.execute("UPDATE interviews SET status = 'in_progress' WHERE id = ?", (interview_id,))
            question_cursor = db.execute(
                "INSERT INTO interview_questions (interview_id, question_text, expected_focus_json, order_num) VALUES (?, ?, '[]', 1)",
                (interview_id, "Describe your project."),
            )
            question_id = question_cursor.lastrowid

        expected_transcript = "I built a REST API with Python, FastAPI, and PostgreSQL in 2025."
        evaluated_transcripts = {}

        async def evaluate_technical(**kwargs):
            evaluated_transcripts["technical"] = kwargs["candidate_answer"]
            return TechnicalEvaluationSchema(technical_score=80, correctness=80, relevance=80, completeness=80, depth=80, feedback="Evaluated")

        async def evaluate_communication(**kwargs):
            evaluated_transcripts["communication"] = kwargs["transcript"]
            return CommunicationEvaluationSchema(grammar_score=80, vocabulary_score=80, clarity_score=80, communication_score=80, feedback="Evaluated")

        def analyze_fluency(**kwargs):
            evaluated_transcripts["fluency"] = kwargs["transcript"]
            return FluencyEvaluationSchema(fluency_score=80, wpm=120, speaking_duration=8, filler_word_count=0)

        async def generate_next_question(**kwargs):
            evaluated_transcripts["question_context"] = kwargs["latest_answer"]
            return QuestionSchema(
                interview_id=interview_id,
                question="What challenge did you solve?",
                category="TECHNICAL",
                difficulty="MEDIUM",
                expected_focus=[],
                source="GENERAL",
                order_number=2,
            ), False

        with patch("app.services.interview_service.AnswerEvaluationService.evaluate_technical_answer", new=evaluate_technical), \
             patch("app.services.interview_service.CommunicationService.evaluate_communication", new=evaluate_communication), \
             patch("app.services.interview_service.FluencyService.analyze_fluency", new=analyze_fluency), \
             patch("app.services.interview_service.QuestionService.generate_next_question_or_follow_up", new=generate_next_question):
            response = self.client.post(
                f"/api/interviews/{interview_id}/answer",
                json={"question_id": question_id, "transcript": expected_transcript, "speaking_duration": 8},
                headers=self.headers1,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(evaluated_transcripts.values()), {expected_transcript})
        with DatabaseSession() as db:
            saved_answer = db.fetchone(
                "SELECT transcript_text FROM interview_answers WHERE interview_id = ? AND question_id = ?",
                (interview_id, question_id),
            )
            saved_analysis = db.fetchone(
                "SELECT technical_score, communication_score, fluency_score FROM answer_analyses WHERE interview_id = ? AND question_id = ?",
                (interview_id, question_id),
            )
        self.assertEqual(saved_answer["transcript_text"], expected_transcript)
        self.assertEqual(saved_analysis, {"technical_score": 80.0, "communication_score": 80.0, "fluency_score": 80.0})

    def test_06_whisper_provider_error_does_not_create_fallback_transcript(self):
        res_create = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=self.headers1)
        interview_id = res_create.json()["id"]

        class FailedWhisper:
            def transcribe(self, path, **kwargs):
                raise RuntimeError("decoder failed")

        with tempfile.TemporaryDirectory() as audio_dir:
            with patch("app.services.transcription_service.AUDIO_UPLOAD_DIR", Path(audio_dir)), \
                 patch("app.services.transcription_service._whisper_available", True), \
                 patch("app.services.transcription_service._whisper_model", FailedWhisper()):
                response = self.client.post(
                    f"/api/interviews/{interview_id}/transcribe",
                    data={"fallback_text": "This answer was not spoken."},
                    files={"file": ("recording.wav", create_test_wav_bytes(), "audio/wav")},
                    headers=self.headers1,
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transcript"], "")
        self.assertEqual(response.json()["transcription_status"], "failed")
        self.assertIn("Whisper transcription failed", response.json()["transcription_error"])

if __name__ == "__main__":
    unittest.main()
