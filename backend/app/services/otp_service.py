import hashlib
import hmac
import secrets
import time
from typing import Optional
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES

# OTP configuration
OTP_LENGTH = 6
OTP_EXPIRE_SECONDS = int(5 * 60)  # 5 minutes
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30  # seconds


class OTPService:
    """Simple OTP management using the existing SQLite DatabaseSession."""

    @staticmethod
    def ensure_table(db):
        # Create the email_verifications table if it does not exist.
        # Note: we embed the default max attempts as a literal to avoid parameterized DDL issues.
        sql = f"""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT,
            purpose TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            otp_salt TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT {OTP_MAX_ATTEMPTS},
            verified INTEGER NOT NULL DEFAULT 0,
            used INTEGER NOT NULL DEFAULT 0,
            resend_count INTEGER NOT NULL DEFAULT 0,
            last_sent_at INTEGER,
            created_at INTEGER NOT NULL
        )
        """
        db.execute(sql)

    @staticmethod
    def _make_otp():
        num = secrets.randbelow(10 ** OTP_LENGTH)
        return str(num).zfill(OTP_LENGTH)

    @staticmethod
    def _hash_otp(salt: str, otp: str) -> str:
        return hashlib.sha256((salt + otp).encode('utf-8')).hexdigest()

    @staticmethod
    def send_otp(db, name: str, email: str, purpose: str = 'register') -> dict:
        """Generates and stores an OTP, enforcing resend cooldowns.

        Returns metadata (next_resend_seconds) but never returns the raw OTP.
        """
        OTPService.ensure_table(db)
        now = int(time.time())

        # Check for existing latest record
        row = db.fetchone(
            "SELECT * FROM email_verifications WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
            (email.lower(), purpose)
        )

        if row and row.get('last_sent_at'):
            last_sent = int(row.get('last_sent_at') or 0)
            if now - last_sent < RESEND_COOLDOWN_SECONDS:
                return {"sent": False, "next_resend_seconds": RESEND_COOLDOWN_SECONDS - (now - last_sent)}

        otp = OTPService._make_otp()
        salt = secrets.token_hex(8)
        otp_hash = OTPService._hash_otp(salt, otp)
        expires_at = now + OTP_EXPIRE_SECONDS

        # Invalidate previous un-used OTPs for the same email/purpose
        db.execute(
            "UPDATE email_verifications SET used = 1 WHERE email = ? AND purpose = ? AND used = 0",
            (email.lower(), purpose)
        )

        cursor = db.execute(
            "INSERT INTO email_verifications (email, name, purpose, otp_hash, otp_salt, expires_at, attempt_count, max_attempts, verified, used, resend_count, last_sent_at, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, 0, 0, ?, ?)",
            (email.lower(), name, purpose, otp_hash, salt, expires_at, OTP_MAX_ATTEMPTS, now, now)
        )
        db.commit()

        # Send email via email service (import here to avoid cycles)
        try:
            from app.services.email_service import EmailService
            if purpose == 'forgot_password':
                EmailService.send_password_reset_email(to_email=email, otp=otp)
            else:
                EmailService.send_verification_email(to_email=email, otp=otp)
        except Exception:
            # If email fails, still store OTP, but return error to caller
            return {"sent": False, "error": "failed_to_send"}

        return {"sent": True, "next_resend_seconds": RESEND_COOLDOWN_SECONDS}

    @staticmethod
    def verify_otp(db, email: str, otp: str, purpose: str = 'register') -> dict:
        OTPService.ensure_table(db)
        now = int(time.time())

        row = db.fetchone(
            "SELECT * FROM email_verifications WHERE email = ? AND purpose = ? AND used = 0 ORDER BY created_at DESC LIMIT 1",
            (email.lower(), purpose)
        )
        if not row:
            return {"ok": False, "reason": "no_otp_found"}

        if int(row.get('verified') or 0) == 1:
            return {"ok": False, "reason": "already_verified"}

        if int(row.get('expires_at') or 0) < now:
            # mark used
            db.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (row.get('id'),))
            db.commit()
            return {"ok": False, "reason": "expired"}

        if int(row.get('attempt_count') or 0) >= int(row.get('max_attempts') or OTP_MAX_ATTEMPTS):
            db.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (row.get('id'),))
            db.commit()
            return {"ok": False, "reason": "too_many_attempts"}

        salt = row.get('otp_salt')
        expected_hash = row.get('otp_hash')
        candidate_hash = OTPService._hash_otp(salt, otp)

        if hmac.compare_digest(candidate_hash, expected_hash):
            db.execute("UPDATE email_verifications SET verified = 1, used = 1 WHERE id = ?", (row.get('id'),))
            db.commit()
            return {"ok": True}

        # incorrect OTP
        db.execute("UPDATE email_verifications SET attempt_count = attempt_count + 1 WHERE id = ?", (row.get('id'),))
        db.commit()
        remaining = int(row.get('max_attempts') or OTP_MAX_ATTEMPTS) - (int(row.get('attempt_count') or 0) + 1)
        if remaining <= 0:
            db.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (row.get('id'),))
            db.commit()
            return {"ok": False, "reason": "too_many_attempts"}

        return {"ok": False, "reason": "invalid_otp", "remaining_attempts": remaining}

    @staticmethod
    def is_email_verified(db, email: str, purpose: str = 'register') -> bool:
        OTPService.ensure_table(db)
        row = db.fetchone(
            "SELECT * FROM email_verifications WHERE email = ? AND purpose = ? AND verified = 1 ORDER BY created_at DESC LIMIT 1",
            (email.lower(), purpose)
        )
        return bool(row)
