import unittest
import time
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)
from app.utils.file_helpers import (
    sanitize_filename,
    generate_secure_filename,
    validate_file_extension,
    validate_file_size
)

class TestSecurity(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        password = "SecurePassword123!"
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)

        # Salt ensures distinct hashes
        self.assertNotEqual(hashed1, hashed2)
        self.assertTrue(verify_password(password, hashed1))
        self.assertTrue(verify_password(password, hashed2))
        self.assertFalse(verify_password("WrongPassword!", hashed1))
        self.assertFalse(verify_password("", hashed1))

    def test_jwt_token_flow(self):
        payload = {"sub": "42", "email": "test@example.com", "name": "Student Tester"}
        token = create_access_token(payload, expires_delta_minutes=10)

        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "42")
        self.assertEqual(decoded["email"], "test@example.com")
        self.assertEqual(decoded["name"], "Student Tester")
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_jwt_tampering_rejected(self):
        payload = {"sub": "42", "email": "test@example.com"}
        token = create_access_token(payload, expires_delta_minutes=10)

        parts = token.split('.')
        tampered_token = f"{parts[0]}.{parts[1]}tampered.{parts[2]}"
        with self.assertRaises(ValueError):
            decode_access_token(tampered_token)

    def test_jwt_expiration_rejected(self):
        payload = {"sub": "42"}
        # Create token that expired 5 minutes ago
        token = create_access_token(payload, expires_delta_minutes=-5)
        with self.assertRaises(ValueError) as ctx:
            decode_access_token(token)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_filename_sanitization_and_path_traversal(self):
        malicious_names = [
            "../../../etc/passwd.pdf",
            "..\\..\\windows\\system32\\config.docx",
            "/absolute/path/to/resume.pdf",
            "normal resume (1) [final].pdf"
        ]
        for name in malicious_names:
            sanitized = sanitize_filename(name)
            self.assertNotIn("/", sanitized)
            self.assertNotIn("\\", sanitized)
            self.assertNotIn("..", sanitized)

            secure_name, orig = generate_secure_filename(name)
            self.assertNotIn("/", secure_name)
            self.assertNotIn("\\", secure_name)

    def test_file_extension_validation(self):
        self.assertTrue(validate_file_extension("resume.pdf"))
        self.assertTrue(validate_file_extension("RESUME.PDF"))
        self.assertTrue(validate_file_extension("job_description.docx"))
        self.assertFalse(validate_file_extension("script.py"))
        self.assertFalse(validate_file_extension("payload.exe"))
        self.assertFalse(validate_file_extension("image.png"))

if __name__ == "__main__":
    unittest.main()
