import unittest
from starlette.testclient import TestClient
from app.main import app
from app.database.base import reset_db


class TestAdminAuthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

    def test_admin_registration_and_login_flow(self):
        payload = {
            "name": "Admin User",
            "email": "admin@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }

        send = self.client.post("/api/admin/send-otp", json={"name": payload["name"], "email": payload["email"]})
        self.assertEqual(send.status_code, 200)
        self.assertEqual(send.json()["status"], "ok")

        # Poll the stored OTP from the DB via a direct DB call is simple and deterministic for tests.
        from app.database.session import DatabaseSession
        with DatabaseSession() as db:
            row = db.fetchone(
                "SELECT otp_hash, otp_salt FROM email_verifications WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
                (payload["email"].lower(), "admin_register")
            )
            self.assertIsNotNone(row)
            import hashlib
            import hmac
            otp = "000000"
            for candidate in [str(i).zfill(6) for i in range(1000000)]:
                candidate_hash = hashlib.sha256((row["otp_salt"] + candidate).encode("utf-8")).hexdigest()
                if hmac.compare_digest(candidate_hash, row["otp_hash"]):
                    otp = candidate
                    break

        verify = self.client.post("/api/admin/verify-otp", json={"email": payload["email"], "otp": otp})
        self.assertEqual(verify.status_code, 200)

        register = self.client.post("/api/admin/register", json=payload)
        self.assertEqual(register.status_code, 201)
        body = register.json()
        self.assertIn("access_token", body)
        self.assertEqual(body["user"]["email"], payload["email"].lower())

        admin_login = self.client.post("/api/admin/login", json={"email": payload["email"], "password": payload["password"]})
        self.assertEqual(admin_login.status_code, 200)
        self.assertEqual(admin_login.json()["user"]["role"], "admin")
        self.__class__.admin_token = admin_login.json()["access_token"]

        candidate_login = self.client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
        self.assertEqual(candidate_login.status_code, 403)
        self.assertEqual(candidate_login.json()["detail"], "Access denied. Invalid account role.")

        candidate_api = self.client.get("/api/interviews", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(candidate_api.status_code, 403)
        self.assertEqual(candidate_api.json()["detail"], "Access denied. Invalid account role.")

    def test_candidate_cannot_access_admin_dashboard(self):
        register = self.client.post(
            "/api/auth/register",
            json={
                "name": "Candidate User",
                "email": "candidate@example.com",
                "password": "Password123!",
                "confirm_password": "Password123!"
            }
        )
        self.assertEqual(register.status_code, 201)
        token = register.json()["access_token"]

        response = self.client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Access denied. Invalid account role.")

        admin_login = self.client.post("/api/admin/login", json={
            "email": "candidate@example.com",
            "password": "Password123!"
        })
        self.assertEqual(admin_login.status_code, 403)
        self.assertEqual(admin_login.json()["detail"], "Access denied. Invalid account role.")

    def test_admin_dashboard_chart_metrics_come_from_database(self):
        admin = self.client.post("/api/admin/register", json={
            "name": "Analytics Admin",
            "email": "analytics-admin@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(admin.status_code, 201)

        candidate = self.client.post("/api/auth/register", json={
            "name": "Analytics Candidate",
            "email": "analytics@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(candidate.status_code, 201)

        from app.database.session import DatabaseSession
        with DatabaseSession() as db:
            cursor = db.execute(
                "INSERT INTO interviews (user_id, interview_type, status, overall_score, created_at) VALUES (?, 'general', 'completed', ?, ?)",
                (candidate.json()["user"]["id"], 65.1, "2026-05-14 12:00:00")
            )
            db.execute(
                "INSERT INTO interview_scores (interview_id, overall_score, technical_score, communication_score, fluency_score, eye_contact_score, posture_score, expression_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (cursor.lastrowid, 65.1, 66, 70, 60, 62, 80, 55)
            )
            db.execute(
                "INSERT INTO interviews (user_id, interview_type, status, overall_score, created_at) VALUES (?, 'general', 'completed', 99, ?)",
                (admin.json()["user"]["id"], "2026-05-15 12:00:00")
            )
            db.commit()

        response = self.client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {admin.json()['access_token']}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_interviews"], 1)
        self.assertEqual(data["average_score"], 65.1)
        self.assertEqual(data["highest_score"], 65.1)
        candidate_summary = next(item for item in data["candidates"] if item["id"] == candidate.json()["user"]["id"])
        self.assertEqual(candidate_summary["avg_score"], 65.1)
        self.assertEqual(candidate_summary["best_score"], 65.1)
        self.assertEqual(data["score_distribution"][3], {"range": "61-80", "count": 1})
        self.assertEqual(data["score_progression"], [{
            "candidate_id": candidate.json()["user"]["id"],
            "candidate_name": "Analytics Candidate",
            "interview_number": 1,
            "date": "2026-05-14",
            "score": 65.1,
        }])
        self.assertEqual(data["interview_activity"], [{"date": "2026-05-14", "completed_interviews": 1}])
        self.assertEqual(data["category_performance"][0], {"dimension": "Technical", "score": 66.0})

        candidates = self.client.get("/api/admin/candidates", headers={"Authorization": f"Bearer {admin.json()['access_token']}"})
        candidate_row = next(item for item in candidates.json()["items"] if item["id"] == candidate.json()["user"]["id"])
        self.assertEqual(candidate_row["avg_score"], 65.1)
        self.assertEqual(candidate_row["best_score"], 65.1)


if __name__ == "__main__":
    unittest.main()
