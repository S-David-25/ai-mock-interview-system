import unittest
import os
import tempfile
from starlette.testclient import TestClient
from app.main import app
from app.database.base import init_db, reset_db

class TestInterviewEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

        # Register User A
        res_a = cls.client.post("/api/auth/register", json={
            "name": "Alice Developer",
            "email": "alice@company.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token_a = res_a.json()["access_token"]

        # Register User B
        res_b = cls.client.post("/api/auth/register", json={
            "name": "Bob Analyst",
            "email": "bob@company.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cls.token_b = res_b.json()["access_token"]

    def test_01_create_general_interview(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        payload = {
            "interview_type": "general"
        }
        res = self.client.post("/api/interviews", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["interview_type"], "general")
        self.assertEqual(data["status"], "setup")
        self.assertFalse(data["is_resume_uploaded"])
        self.assertFalse(data["is_jd_uploaded"])
        self.assertIn("id", data)

    def test_02_create_company_interview(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        payload = {
            "interview_type": "company",
            "company_name": "Google",
            "job_role": "Software Engineer II"
        }
        res = self.client.post("/api/interviews", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["interview_type"], "company")
        self.assertEqual(data["company_name"], "Google")
        self.assertEqual(data["job_role"], "Software Engineer II")
        self.assertEqual(data["status"], "setup")

    def test_03_create_company_interview_validation(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        # Missing company_name and job_role for company interview
        payload = {
            "interview_type": "company"
        }
        res = self.client.post("/api/interviews", json=payload, headers=headers)
        self.assertEqual(res.status_code, 422)

    def test_04_list_interviews_and_stats(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/api/interviews", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("interviews", data)
        self.assertIn("stats", data)
        self.assertGreaterEqual(len(data["interviews"]), 2)
        self.assertGreaterEqual(data["stats"]["total_interviews"], 2)

    def test_05_user_isolation(self):
        # Alice creates an interview
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        res_create = self.client.post("/api/interviews", json={"interview_type": "general"}, headers=headers_a)
        alice_interview_id = res_create.json()["id"]

        # Bob attempts to access Alice's interview
        headers_b = {"Authorization": f"Bearer {self.token_b}"}
        res_bob = self.client.get(f"/api/interviews/{alice_interview_id}", headers=headers_b)
        self.assertEqual(res_bob.status_code, 404)

    def test_06_get_interview_status(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res_create = self.client.post("/api/interviews", json={
            "interview_type": "company",
            "company_name": "Microsoft",
            "job_role": "Cloud Architect"
        }, headers=headers)
        int_id = res_create.json()["id"]

        res_status = self.client.get(f"/api/interviews/{int_id}/status", headers=headers)
        self.assertEqual(res_status.status_code, 200)
        data = res_status.json()
        self.assertEqual(data["status"], "setup")
        self.assertFalse(data["is_ready"])
        self.assertIn("required", data["message"].lower())

if __name__ == "__main__":
    unittest.main()
