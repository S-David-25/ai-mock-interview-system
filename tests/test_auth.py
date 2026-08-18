import unittest
import os
from starlette.testclient import TestClient
from app.main import app
from app.database.base import init_db, reset_db

class TestAuthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.client = TestClient(app)

    def test_01_register_success(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane.doe@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["email"], "jane.doe@university.edu")
        self.assertEqual(data["user"]["name"], "Jane Doe")
        self.assertNotIn("password_hash", data["user"])

    def test_02_register_duplicate_email(self):
        payload = {
            "name": "Jane Duplicate",
            "email": "jane.doe@university.edu",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("already registered", res.json()["detail"].lower())

    def test_03_register_password_mismatch(self):
        payload = {
            "name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword!"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_04_register_short_password(self):
        payload = {
            "name": "Short Pw",
            "email": "short@example.com",
            "password": "123",
            "confirm_password": "123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_05_login_success(self):
        payload = {
            "email": "jane.doe@university.edu",
            "password": "Password123!"
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["name"], "Jane Doe")

    def test_06_login_invalid_password(self):
        payload = {
            "email": "jane.doe@university.edu",
            "password": "WrongPassword!"
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertIn("invalid email or password", res.json()["detail"].lower())

    def test_07_login_nonexistent_email(self):
        payload = {
            "email": "ghost@university.edu",
            "password": "Password123!"
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 401)

    def test_08_get_me_success(self):
        login_res = self.client.post("/api/auth/login", json={
            "email": "jane.doe@university.edu",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]

        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "jane.doe@university.edu")

    def test_09_get_me_unauthorized(self):
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

        res = self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.structure"})
        self.assertEqual(res.status_code, 401)

    def test_10_logout(self):
        login_res = self.client.post("/api/auth/login", json={
            "email": "jane.doe@university.edu",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]
        res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

if __name__ == "__main__":
    unittest.main()
