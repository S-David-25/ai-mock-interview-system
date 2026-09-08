from typing import Optional, Tuple
from fastapi import HTTPException, status
from app.database.session import DatabaseSession
from app.models.user import User
from app.schemas.auth import UserRegister
from app.utils.security import hash_password, verify_password, create_access_token

class AuthService:
    @staticmethod
    def get_user_by_email(db: DatabaseSession, email: str) -> Optional[User]:
        row = db.fetchone("SELECT * FROM users WHERE email = ?", (email.lower(),))
        return User.from_row(row)

    @staticmethod
    def get_user_by_id(db: DatabaseSession, user_id: int) -> Optional[User]:
        row = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return User.from_row(row)

    @staticmethod
    def register_user(db: DatabaseSession, data: UserRegister) -> Tuple[User, str]:
        import os
        existing = AuthService.get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered. Please login instead."
            )

        # Ensure the email was verified through OTP for registration purpose unless in test mode
        from app.services.otp_service import OTPService
        verified = OTPService.is_email_verified(db, data.email, purpose='register')
        if not verified and not os.environ.get("TESTING"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified for registration. Please complete OTP verification."
            )

        hashed_pw = hash_password(data.password)
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, datetime('now', 'utc'))",
            (data.name, data.email.lower(), hashed_pw)
        )
        db.commit()
        user_id = cursor.lastrowid

        user = AuthService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user record.")

        token = create_access_token({"sub": str(user.id), "email": user.email, "name": user.name})
        return user, token

    @staticmethod
    def authenticate_user(db: DatabaseSession, email: str, password: str) -> Tuple[User, str]:
        user = AuthService.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        token = create_access_token({"sub": str(user.id), "email": user.email, "name": user.name})
        return user, token

    @staticmethod
    def reset_password(db: DatabaseSession, email: str, new_password: str) -> None:
        """Reset password for an existing user identified by email."""
        user = AuthService.get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        hashed_pw = hash_password(new_password)
        db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed_pw, email.lower()))
        db.commit()
        # Optionally return nothing; caller will confirm success

