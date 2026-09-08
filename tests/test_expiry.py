import os
import unittest
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient
from app.main import app
from app.database.session import DatabaseSession
from app.database.base import reset_db
from app.services.interview_service import parse_utc_timestamp

class TestInterviewExpiry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

        # Register User
        res = cls.client.post("/api/auth/register", json={
            "name": "Test Candidate",
            "email": "candidate@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_create_with_duration_options(self):
        durations = [1, 20, 30, 45, 60, 90]
        for dur in durations:
            res = self.client.post("/api/interviews", json={
                "interview_type": "general",
                "duration_minutes": dur
            }, headers=self.headers)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertEqual(data["duration_minutes"], dur)
            self.assertIsNone(data["started_at"])
            self.assertIsNone(data["expires_at"])

    def test_02_start_calculates_utc_timestamps(self):
        res = self.client.post("/api/interviews", json={
            "interview_type": "general",
            "duration_minutes": 1
        }, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        interview_id = res.json()["id"]

        # Start interview
        start_res = self.client.post(f"/api/interviews/{interview_id}/start", headers=self.headers)
        self.assertEqual(start_res.status_code, 200)
        data = start_res.json()
        self.assertEqual(data["status"], "in_progress")
        self.assertIsNotNone(data["started_at"])
        self.assertIsNotNone(data["expires_at"])

        started_dt = parse_utc_timestamp(data["started_at"])
        expires_dt = parse_utc_timestamp(data["expires_at"])
        self.assertIsNotNone(started_dt)
        self.assertIsNotNone(expires_dt)

        diff = expires_dt - started_dt
        self.assertAlmostEqual(diff.total_seconds(), 60, delta=2)

    def test_03_expired_session_auto_completes_on_fetch(self):
        res = self.client.post("/api/interviews", json={
            "interview_type": "general",
            "duration_minutes": 1
        }, headers=self.headers)
        interview_id = res.json()["id"]

        # Start interview
        self.client.post(f"/api/interviews/{interview_id}/start", headers=self.headers)

        # Manually backdate expires_at in DB to simulate expiry
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseSession() as db:
            db.execute("UPDATE interviews SET expires_at = ? WHERE id = ?", (past_time, interview_id))
            db.commit()

        # Fetch session detail
        get_res = self.client.get(f"/api/interviews/{interview_id}", headers=self.headers)
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["status"], "completed")

    def test_04_submit_answer_on_expired_session_gracefully_completes(self):
        res = self.client.post("/api/interviews", json={
            "interview_type": "general",
            "duration_minutes": 1
        }, headers=self.headers)
        interview_id = res.json()["id"]

        # Start interview
        self.client.post(f"/api/interviews/{interview_id}/start", headers=self.headers)

        # Manually backdate expires_at in DB to simulate expiry
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseSession() as db:
            db.execute("UPDATE interviews SET expires_at = ? WHERE id = ?", (past_time, interview_id))
            db.commit()

        # Submit answer
        ans_res = self.client.post(f"/api/interviews/{interview_id}/answer", json={
            "question_id": 1,
            "transcript": "My response to question",
            "speaking_duration": 10.0
        }, headers=self.headers)
        self.assertEqual(ans_res.status_code, 200)
        ans_data = ans_res.json()
        self.assertTrue(ans_data["is_completed"])
        self.assertIn("ended", ans_data["message"].lower())

    def test_05_explicit_complete_is_idempotent(self):
        res = self.client.post("/api/interviews", json={
            "interview_type": "general",
            "duration_minutes": 30
        }, headers=self.headers)
        interview_id = res.json()["id"]

        # Start and then complete
        self.client.post(f"/api/interviews/{interview_id}/start", headers=self.headers)
        comp_res1 = self.client.post(f"/api/interviews/{interview_id}/complete", headers=self.headers)
        self.assertEqual(comp_res1.status_code, 200)
        self.assertEqual(comp_res1.json()["status"], "completed")

        # Second complete call
        comp_res2 = self.client.post(f"/api/interviews/{interview_id}/complete", headers=self.headers)
        self.assertEqual(comp_res2.status_code, 200)
        self.assertEqual(comp_res2.json()["status"], "completed")

if __name__ == "__main__":
    unittest.main()
