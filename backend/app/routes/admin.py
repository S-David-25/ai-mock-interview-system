import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.session import DatabaseSession, get_db
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.auth import TokenResponse, UserRegister, UserResponse
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.progress_service import ProgressAnalyticsService

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid account role."
        )
    return current_user


def _normalize_email(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _otp_error_result(result: Dict[str, Any]) -> HTTPException:
    reason = result.get("reason")
    if reason == "expired":
        return HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if reason == "too_many_attempts":
        return HTTPException(status_code=400, detail="Too many verification attempts. Please request a new OTP.")
    if reason == "invalid_otp":
        remaining = result.get("remaining_attempts", 0)
        return HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempts remaining.")
    return HTTPException(status_code=400, detail="Invalid or missing OTP for this email.")


@router.post("/send-otp")
def send_admin_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    email = _normalize_email(payload.get("email"))
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Name is required.")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")

    existing = AuthService.get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    result = OTPService.send_otp(db, name, email, purpose="admin_register")
    if not result.get("sent"):
        if result.get("error") == "failed_to_send":
            raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again later.")
        next_in = result.get("next_resend_seconds", 30)
        raise HTTPException(status_code=429, detail=f"Please wait {next_in} seconds before resending OTP.")

    return {"status": "ok", "message": "OTP sent.", "next_resend_seconds": result.get("next_resend_seconds", 30)}


@router.post("/verify-otp")
def verify_admin_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    email = _normalize_email(payload.get("email"))
    otp = (payload.get("otp") or "").strip()
    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP are required.")

    result = OTPService.verify_otp(db, email, otp, purpose="admin_register")
    if result.get("ok"):
        return {"status": "ok", "message": "Email verified."}
    raise _otp_error_result(result)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_admin(data: UserRegister, db: DatabaseSession = Depends(get_db)):
    verified = OTPService.is_email_verified(db, data.email, purpose="admin_register")
    if not verified and not os.environ.get("TESTING"):
        raise HTTPException(status_code=400, detail="Email has not been verified. Please verify your email before creating an admin account.")

    user, token = AuthService.register_user(db, data, role="admin")
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            created_at=user.created_at
        )
    )


@router.post("/forgot-password/send-otp")
def admin_forgot_password_send_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    email = _normalize_email(payload.get("email"))
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")

    user = AuthService.get_user_by_email(db, email)
    if user and user.role != "admin":
        return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}

    if user is None:
        return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}

    result = OTPService.send_otp(db, user.name, email, purpose="admin_forgot_password")
    if not result.get("sent"):
        return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent."}
    return {"status": "ok", "message": "If the email is registered, a password reset OTP has been sent.", "next_resend_seconds": result.get("next_resend_seconds", 30)}


@router.post("/forgot-password/verify-otp")
def admin_forgot_password_verify_otp(payload: dict, db: DatabaseSession = Depends(get_db)):
    email = _normalize_email(payload.get("email"))
    otp = (payload.get("otp") or "").strip()
    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP are required.")

    result = OTPService.verify_otp(db, email, otp, purpose="admin_forgot_password")
    if result.get("ok"):
        return {"status": "ok", "message": "OTP verified."}
    raise _otp_error_result(result)


@router.post("/forgot-password/reset")
def admin_reset_password(payload: dict, db: DatabaseSession = Depends(get_db)):
    email = _normalize_email(payload.get("email"))
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or ""
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not new_password:
        raise HTTPException(status_code=400, detail="Password is required.")
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    verified = OTPService.is_email_verified(db, email, purpose="admin_forgot_password")
    if not verified:
        raise HTTPException(status_code=400, detail="Email has not been verified for password reset. Please verify the OTP first.")

    AuthService.reset_password(db, email, new_password, role="admin")
    db.execute("UPDATE email_verifications SET used = 1 WHERE email = ? AND purpose = ?", (email.lower(), "admin_forgot_password"))
    db.commit()
    return {"status": "ok", "message": "Password reset successfully."}


@router.post("/login", response_model=TokenResponse)
def login_admin(data: dict, db: DatabaseSession = Depends(get_db)):
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user, token = AuthService.authenticate_user(db, email, password, required_role="admin")
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            created_at=user.created_at
        )
    )


@router.post("/logout")
def logout_admin(current_user: User = Depends(get_current_admin_user)):
    return {"status": "success", "message": "Successfully logged out."}


@router.get("/dashboard")
def get_admin_dashboard(current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    candidate_rows = db.fetchall(
        "SELECT id, name, email, created_at FROM users WHERE role = 'candidate' ORDER BY created_at DESC",
        ()
    )

    total_candidates = len(candidate_rows)
    total_interviews = db.fetchone(
        "SELECT COUNT(*) as count FROM interviews i JOIN users u ON u.id = i.user_id WHERE u.role = 'candidate'",
        ()
    )
    total_interviews = int((total_interviews or {}).get("count", 0) or 0)

    avg_score_row = db.fetchone(
        "SELECT AVG(COALESCE(s.overall_score, i.overall_score)) as avg_score FROM interviews i JOIN users u ON u.id = i.user_id AND u.role = 'candidate' LEFT JOIN interview_scores s ON s.interview_id = i.id WHERE i.status = 'completed' AND COALESCE(s.overall_score, i.overall_score) IS NOT NULL",
        ()
    )
    average_score = round(float(avg_score_row["avg_score"]), 1) if avg_score_row and avg_score_row.get("avg_score") is not None else None

    highest_score_row = db.fetchone(
        "SELECT MAX(COALESCE(s.overall_score, i.overall_score)) as max_score FROM interviews i JOIN users u ON u.id = i.user_id AND u.role = 'candidate' LEFT JOIN interview_scores s ON s.interview_id = i.id WHERE i.status = 'completed' AND COALESCE(s.overall_score, i.overall_score) IS NOT NULL",
        ()
    )
    highest_score = round(float(highest_score_row["max_score"]), 1) if highest_score_row and highest_score_row.get("max_score") is not None else None

    active_candidates = 0
    for candidate in candidate_rows:
        progress = ProgressAnalyticsService.get_user_progress(db, candidate["id"])
        if progress.interview_count > 0:
            active_candidates += 1

    candidate_summaries = []
    for candidate in candidate_rows:
        candidate_id = candidate["id"]
        interviews = db.fetchall(
            "SELECT * FROM interviews WHERE user_id = ? ORDER BY created_at DESC",
            (candidate_id,)
        )
        score_rows = db.fetchall(
            "SELECT i.id, COALESCE(s.overall_score, i.overall_score) AS overall_score, i.created_at FROM interviews i LEFT JOIN interview_scores s ON s.interview_id = i.id WHERE i.user_id = ? AND i.status = 'completed' AND COALESCE(s.overall_score, i.overall_score) IS NOT NULL ORDER BY i.created_at ASC",
            (candidate_id,)
        )
        completed_count = db.fetchone(
            "SELECT COUNT(*) AS count FROM interviews WHERE user_id = ? AND status = 'completed'",
            (candidate_id,)
        )
        avg_score_value = round(sum(float(r["overall_score"]) for r in score_rows) / len(score_rows), 1) if score_rows else None
        best_score_value = round(max(float(r["overall_score"]) for r in score_rows), 1) if score_rows else None
        candidate_summaries.append({
            "id": candidate_id,
            "name": candidate["name"],
            "email": candidate["email"],
            "interviews": len(interviews),
            "completed_interviews": int((completed_count or {}).get("count", 0) or 0),
            "avg_score": avg_score_value,
            "best_score": best_score_value,
            "improvement": round(float(score_rows[-1]["overall_score"]) - float(score_rows[0]["overall_score"]), 1) if len(score_rows) > 1 else None,
            "last_interview": interviews[0]["created_at"] if interviews else None,
        })

    completed_scores = db.fetchall(
        """
        SELECT i.id AS interview_id, i.user_id AS candidate_id, u.name AS candidate_name,
               i.created_at, COALESCE(s.overall_score, i.overall_score) AS overall_score,
               s.technical_score, s.communication_score, s.fluency_score,
               s.eye_contact_score, s.posture_score, s.expression_score
        FROM interviews i
        JOIN users u ON u.id = i.user_id AND u.role = 'candidate'
        LEFT JOIN interview_scores s ON s.interview_id = i.id
        WHERE i.status = 'completed' AND COALESCE(s.overall_score, i.overall_score) IS NOT NULL
        ORDER BY i.created_at ASC, i.id ASC
        """,
        ()
    )

    score_ranges = [
        {"range": "0-20", "count": 0},
        {"range": "21-40", "count": 0},
        {"range": "41-60", "count": 0},
        {"range": "61-80", "count": 0},
        {"range": "81-100", "count": 0},
    ]
    category_fields = [
        ("Technical", "technical_score"),
        ("Communication", "communication_score"),
        ("Fluency", "fluency_score"),
        ("Eye Contact", "eye_contact_score"),
        ("Posture", "posture_score"),
        ("Expression", "expression_score"),
    ]
    category_totals = {field: [] for _, field in category_fields}
    interview_activity = {}
    progression_counts = {}
    score_progression = []
    candidate_scores = {}

    completed_activity_rows = db.fetchall(
        "SELECT i.created_at FROM interviews i JOIN users u ON u.id = i.user_id AND u.role = 'candidate' WHERE i.status = 'completed'",
        ()
    )
    for row in completed_activity_rows:
        date = str(row.get("created_at") or "")[:10]
        if date:
            interview_activity[date] = interview_activity.get(date, 0) + 1

    for row in completed_scores:
        overall = float(row["overall_score"] or 0.0)
        if overall <= 20:
            score_bucket = 0
        elif overall <= 40:
            score_bucket = 1
        elif overall <= 60:
            score_bucket = 2
        elif overall <= 80:
            score_bucket = 3
        else:
            score_bucket = 4
        score_ranges[score_bucket]["count"] += 1

        date = str(row.get("created_at") or "")[:10]
        candidate_id = int(row["candidate_id"])
        progression_counts[candidate_id] = progression_counts.get(candidate_id, 0) + 1
        candidate_scores.setdefault(candidate_id, []).append(overall)
        score_progression.append({
            "candidate_id": candidate_id,
            "candidate_name": row["candidate_name"],
            "interview_number": progression_counts[candidate_id],
            "date": date,
            "score": round(overall, 1),
        })

        for _, field in category_fields:
            value = row.get(field)
            if value is not None:
                category_totals[field].append(float(value))

    category_performance = [
        {
            "dimension": label,
            "score": round(sum(category_totals[field]) / len(category_totals[field]), 1),
        }
        for label, field in category_fields
        if category_totals[field]
    ]
    improvement_values = [scores[-1] - scores[0] for scores in candidate_scores.values() if len(scores) > 1]
    average_improvement = round(sum(improvement_values) / len(improvement_values), 1) if improvement_values else None

    return {
        "total_candidates": total_candidates,
        "total_interviews": total_interviews,
        "average_score": average_score,
        "highest_score": highest_score,
        "average_improvement": average_improvement,
        "active_candidates": active_candidates,
        "candidates": candidate_summaries,
        "score_distribution": score_ranges,
        "score_progression": score_progression,
        "category_performance": category_performance,
        "interview_activity": [
            {"date": date, "completed_interviews": count}
            for date, count in sorted(interview_activity.items())
        ],
    }


@router.get("/candidates")
def get_admin_candidates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_admin_user),
    db: DatabaseSession = Depends(get_db),
):
    search_term = (search or "").strip().lower()
    if search_term:
        candidate_rows = db.fetchall(
            "SELECT id, name, email, created_at FROM users WHERE role = 'candidate' AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ?) ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (f"%{search_term}%", f"%{search_term}%", limit, (page - 1) * limit)
        )
        total = db.fetchone(
            "SELECT COUNT(*) as count FROM users WHERE role = 'candidate' AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ?)",
            (f"%{search_term}%", f"%{search_term}%")
        )
    else:
        candidate_rows = db.fetchall(
            "SELECT id, name, email, created_at FROM users WHERE role = 'candidate' ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, (page - 1) * limit)
        )
        total = db.fetchone("SELECT COUNT(*) as count FROM users WHERE role = 'candidate'", ())

    total_count = int((total or {}).get("count", 0) or 0)
    summaries = []
    for candidate in candidate_rows:
        candidate_id = candidate["id"]
        interviews = db.fetchall(
            "SELECT i.id, i.created_at, i.status, COALESCE(s.overall_score, i.overall_score) AS overall_score FROM interviews i LEFT JOIN interview_scores s ON s.interview_id = i.id WHERE i.user_id = ? ORDER BY i.created_at DESC",
            (candidate_id,)
        )
        raw_scores = [float(i["overall_score"]) for i in interviews if i["status"] == "completed" and i.get("overall_score") is not None]
        summaries.append({
            "id": candidate_id,
            "name": candidate["name"],
            "email": candidate["email"],
            "interviews": len(interviews),
            "avg_score": round(sum(raw_scores) / len(raw_scores), 1) if raw_scores else None,
            "best_score": round(max(raw_scores), 1) if raw_scores else None,
            "improvement": round(raw_scores[-1] - raw_scores[0], 1) if len(raw_scores) > 1 else None,
            "last_interview": interviews[0]["created_at"] if interviews else None,
        })

    return {
        "items": summaries,
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": (total_count + limit - 1) // limit if total_count else 0,
    }


@router.get("/candidates/{candidate_id}")
def get_admin_candidate_detail(candidate_id: int, current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    candidate = db.fetchone("SELECT * FROM users WHERE id = ? AND role = 'candidate'", (candidate_id,))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    progress = ProgressAnalyticsService.get_user_progress(db, candidate_id)
    interviews = db.fetchall("SELECT * FROM interviews WHERE user_id = ? ORDER BY created_at DESC", (candidate_id,))
    raw_scores = [float(i["overall_score"]) for i in interviews if i.get("overall_score") is not None]
    analytics_interviews = db.fetchall(
        """
        SELECT i.id AS interview_id, i.created_at AS date,
               COALESCE(s.overall_score, i.overall_score) AS overall_score,
               s.technical_score, s.communication_score, s.fluency_score,
               s.eye_contact_score, s.posture_score, s.expression_score
        FROM interviews i
        LEFT JOIN interview_scores s ON s.interview_id = i.id
        WHERE i.user_id = ? AND i.status = 'completed'
        ORDER BY i.created_at ASC, i.id ASC
        """,
        (candidate_id,)
    )
    question_rows = db.fetchall(
        """
        SELECT q.interview_id, q.id AS question_id, q.order_num,
               AVG(an.technical_score) AS technical_score,
               AVG(an.communication_score) AS communication_score,
               AVG(an.fluency_score) AS fluency_score
        FROM interview_questions q
        JOIN interviews i ON i.id = q.interview_id
        LEFT JOIN interview_answers a ON a.question_id = q.id
        LEFT JOIN answer_analyses an ON an.answer_id = a.id
        WHERE i.user_id = ? AND i.status = 'completed'
        GROUP BY q.interview_id, q.id, q.order_num
        ORDER BY q.interview_id ASC, q.order_num ASC
        """,
        (candidate_id,)
    )
    questions_by_interview = {}
    for row in question_rows:
        question = {
            "question_id": row["question_id"],
            "order_num": row["order_num"],
            "technical_score": row.get("technical_score"),
            "communication_score": row.get("communication_score"),
            "fluency_score": row.get("fluency_score"),
        }
        if any(question[key] is not None for key in ("technical_score", "communication_score", "fluency_score")):
            questions_by_interview.setdefault(row["interview_id"], []).append(question)

    interview_numbers = {row["interview_id"]: index for index, row in enumerate(analytics_interviews, start=1)}
    for interview in analytics_interviews:
        interview["interview_number"] = interview_numbers[interview["interview_id"]]
        interview["question_scores"] = questions_by_interview.get(interview["interview_id"], [])
    scored_analytics_interviews = [item for item in analytics_interviews if item.get("overall_score") is not None]
    completed_scores = [float(item["overall_score"]) for item in scored_analytics_interviews]

    return {
        "candidate": {
            "id": candidate["id"],
            "name": candidate["name"],
            "email": candidate["email"],
            "registration_date": candidate["created_at"],
            "role": "candidate",
        },
        "performance": {
            "interviews": len(analytics_interviews),
            "average_score": round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else None,
            "best_score": round(max(completed_scores), 1) if completed_scores else None,
            "latest_score": completed_scores[-1] if completed_scores else None,
            "improvement": round(completed_scores[-1] - completed_scores[0], 1) if len(completed_scores) > 1 else None,
            "last_interview_date": interviews[0]["created_at"] if interviews else None,
            "trend_data": [t.model_dump() if hasattr(t, "model_dump") else t.__dict__ for t in progress.trend_data],
            "category_trends": [t.model_dump() if hasattr(t, "model_dump") else t.__dict__ for t in progress.category_trends],
            "analytics_interviews": analytics_interviews,
        },
    }


@router.get("/candidates/{candidate_id}/interviews")
def get_admin_candidate_interviews(candidate_id: int, current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    candidate = db.fetchone("SELECT id FROM users WHERE id = ? AND role = 'candidate'", (candidate_id,))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    interviews = db.fetchall(
        "SELECT i.*, s.overall_score, s.technical_score, s.communication_score, s.fluency_score, s.eye_contact_score, s.posture_score, s.expression_score FROM interviews i LEFT JOIN interview_scores s ON i.id = s.interview_id WHERE i.user_id = ? ORDER BY i.created_at DESC",
        (candidate_id,)
    )
    return {"items": interviews}


@router.get("/interviews/{interview_id}")
def get_admin_interview_detail(interview_id: int, current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    interview = db.fetchone(
        "SELECT i.*, s.overall_score, s.technical_score, s.communication_score, s.fluency_score, s.eye_contact_score, s.posture_score, s.expression_score, s.confidence_indicator FROM interviews i LEFT JOIN interview_scores s ON i.id = s.interview_id WHERE i.id = ?",
        (interview_id,)
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    report = db.fetchone("SELECT * FROM interview_reports WHERE interview_id = ?", (interview_id,))
    question_count = db.fetchone("SELECT COUNT(*) as count FROM interview_questions WHERE interview_id = ?", (interview_id,))
    evaluated_count = db.fetchone("SELECT COUNT(*) as count FROM answer_analyses WHERE interview_id = ?", (interview_id,))

    return {
        "interview": interview,
        "report": report,
        "question_count": int((question_count or {}).get("count", 0) or 0),
        "evaluated_questions": int((evaluated_count or {}).get("count", 0) or 0),
    }


@router.get("/interviews/{interview_id}/questions")
def get_admin_interview_questions(interview_id: int, current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    interview = db.fetchone("SELECT id, user_id FROM interviews WHERE id = ?", (interview_id,))
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    rows = db.fetchall(
        """
        SELECT q.id, q.question_text, q.order_num, q.question_category,
               a.transcript_text, an.technical_score, an.communication_score, an.fluency_score,
               an.created_at
        FROM interview_questions q
        LEFT JOIN interview_answers a ON a.question_id = q.id
        LEFT JOIN answer_analyses an ON an.answer_id = a.id
        WHERE q.interview_id = ?
        ORDER BY q.order_num ASC
        """,
        (interview_id,)
    )
    return {"items": rows}


@router.get("/candidates/{candidate_id}/comparison")
def get_admin_candidate_comparison(candidate_id: int, current_user: User = Depends(get_current_admin_user), db: DatabaseSession = Depends(get_db)):
    interviews = db.fetchall(
        "SELECT id, created_at, overall_score FROM interviews WHERE user_id = ? AND overall_score IS NOT NULL ORDER BY created_at DESC",
        (candidate_id,)
    )
    if len(interviews) < 2:
        return {"interviews": interviews, "comparison": []}

    previous = interviews[1]
    current = interviews[0]
    previous_score = float(previous["overall_score"] or 0.0)
    current_score = float(current["overall_score"] or 0.0)

    return {
        "interviews": interviews,
        "comparison": {
            "previous": {"interview_id": previous["id"], "date": previous["created_at"], "score": previous_score},
            "current": {"interview_id": current["id"], "date": current["created_at"], "score": current_score},
            "change": round(current_score - previous_score, 1),
        },
    }


@router.get("/me")
def get_admin_me(current_user: User = Depends(get_current_admin_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
    }
