from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.database.session import DatabaseSession, get_db
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.utils.security import decode_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_current_user(
    authorization: str = Header(None),
    db: DatabaseSession = Depends(get_db)
) -> User:
    """Dependency to extract and validate JWT from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired access token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User belonging to this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


@router.post("/register/send-otp")
def send_registration_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    """Initiate registration by sending an OTP to the provided email + name.

    Expected payload: { "name": "...", "email": "..." }
    """
    name = payload.get('name')
    email = payload.get('email')
    if not name or not name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required.")
    if not email or not email.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required.")

    # Prevent sending OTP for emails that already have verified accounts
    existing = AuthService.get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists. Please log in.")

    result = OTPService.send_otp(db, name.strip(), email.strip(), purpose='register')
    if not result.get('sent'):
        if result.get('error') == 'failed_to_send':
            raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again later.")
        else:
            # cooldown
            next_in = result.get('next_resend_seconds', 30)
            raise HTTPException(status_code=429, detail=f"Please wait {next_in} seconds before resending OTP.")
    return {"status": "ok", "message": "OTP sent.", "next_resend_seconds": result.get('next_resend_seconds', 30)}


# --- Forgot Password endpoints ---
@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    """Send password reset OTP to an email. Always returns a generic success message to avoid user enumeration."""
    email = (payload.get('email') or '').strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required.")

    try:
        user = AuthService.get_user_by_email(db, email)
        if user:
            # send OTP for purpose 'forgot_password'
            result = OTPService.send_otp(db, user.name, email, purpose='forgot_password')
            if not result.get('sent'):
                # Don't leak whether email exists; return generic success
                return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}
            return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent.", "next_resend_seconds": result.get('next_resend_seconds', 30)}
        else:
            # Do not reveal that email is not registered. Optionally, could create a dummy delay.
            return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}
    except Exception:
        # On any internal error, still return generic success
        return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}


@router.post("/register/verify-otp")
def verify_registration_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    """Verify the OTP for a registration.

    Expected payload: { "email": "...", "otp": "..." }
    """
    email = payload.get('email')
    otp = payload.get('otp')
    if not email or not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and OTP are required.")

    # registration OTP verify
    result = OTPService.verify_otp(db, email.strip(), otp.strip(), purpose='register')
    if result.get('ok'):
        return {"status": "ok", "message": "Email verified."}

    reason = result.get('reason')
    if reason == 'expired':
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if reason == 'too_many_attempts':
        raise HTTPException(status_code=400, detail="Too many verification attempts. Please request a new OTP.")
    if reason == 'invalid_otp':
        remaining = result.get('remaining_attempts', 0)
        raise HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempts remaining.")

    raise HTTPException(status_code=400, detail="Invalid or missing OTP for this email.")


@router.post("/forgot-password/verify-otp")
def forgot_password_verify_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    """Verify a forgot-password OTP. Exposes user-friendly errors for OTP failures but not for email existence."""
    email = (payload.get('email') or '').strip()
    otp = (payload.get('otp') or '').strip()
    if not email or not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and OTP are required.")

    result = OTPService.verify_otp(db, email, otp, purpose='forgot_password')
    if result.get('ok'):
        return {"status": "ok", "message": "OTP verified."}

    reason = result.get('reason')
    if reason == 'expired':
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if reason == 'too_many_attempts':
        raise HTTPException(status_code=400, detail="Too many verification attempts. Please request a new OTP.")
    if reason == 'invalid_otp':
        remaining = result.get('remaining_attempts', 0)
        raise HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempts remaining.")

    raise HTTPException(status_code=400, detail="Invalid or missing OTP for this email.")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: DatabaseSession = Depends(get_db)):
    """Register a new student user. Requires prior successful email verification for this email.

    The endpoint enforces that the email has a verified OTP stored for the 'register' purpose.
    """
    # Ensure email was verified through OTP
    verified = OTPService.is_email_verified(db, data.email, purpose='register')
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email has not been verified. Please verify your email before creating an account.")

    user, token = AuthService.register_user(db, data)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at
        )
    )


@router.post("/forgot-password/reset")
def forgot_password_reset(payload: dict, db: DatabaseSession = Depends(get_db)):
    """Reset password after successful forgot-password OTP verification.

    Expected payload: { "email": "...", "new_password": "...", "confirm_password": "..." }
    """
    email = (payload.get('email') or '').strip()
    new_password = payload.get('new_password') or ''
    confirm_password = payload.get('confirm_password') or ''

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required.")
    if not new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required.")
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")
    if len(new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters long.")

    # Ensure OTP was verified for forgot_password purpose
    verified = OTPService.is_email_verified(db, email, purpose='forgot_password')
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email has not been verified for password reset. Please verify the OTP first.")

    # Perform password reset
    AuthService.reset_password(db, email, new_password)

    # Mark any used/verified OTPs consumed for this purpose
    db.execute("UPDATE email_verifications SET used = 1 WHERE email = ? AND purpose = ?", (email.lower(), 'forgot_password'))
    db.commit()

    return {"status": "ok", "message": "Password reset successfully."}


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: DatabaseSession = Depends(get_db)):
    """Authenticate student and return JWT access token."""
    user, token = AuthService.authenticate_user(db, data.email, data.password)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at
        )
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve details for current authenticated student."""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        created_at=current_user.created_at
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout current user session."""
    return {"status": "success", "message": "Successfully logged out."}
