from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status
from app.database.session import DatabaseSession, get_db
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.interview import (
    InterviewCreate,
    InterviewResponse,
    InterviewListResponse,
    InterviewStatusResponse,
    FileUploadResponse,
    DocumentProcessResponse,
    QuestionSchema,
    QuestionListResponse,
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    TranscriptionResponse,
    VisionFrameRequest,
    VisionFrameResponse,
    InterviewScoreResponse,
    PerformanceReportResponse,
    RoadmapResponse,
    ProgressResponse,
    InterviewComparisonResponse
)
from app.services.interview_service import InterviewService
from app.services.file_service import FileService
from app.services.transcription_service import TranscriptionService
from app.services.report_service import PerformanceReportService
from app.services.scoring_service import MultiModalScoringService
from app.services.roadmap_service import PersonalizedRoadmapService
from app.services.progress_service import ProgressAnalyticsService

router = APIRouter(prefix="/api", tags=["Interviews & Analytics"])

# ----------------- MASTER PROMPT 1: SETUP & MANAGEMENT -----------------

@router.post("/interviews", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    data: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Create a new mock interview session."""
    interview = InterviewService.create_interview(db, current_user.id, data)
    return InterviewResponse(**interview.to_dict())

@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """List all interviews and summary metrics for the authenticated user."""
    interviews = InterviewService.get_user_interviews(db, current_user.id)
    stats = InterviewService.get_user_interview_stats(db, current_user.id)
    return InterviewListResponse(
        interviews=[InterviewResponse(**i.to_dict()) for i in interviews],
        stats=stats
    )

# ----------------- MASTER PROMPT 3: COMPARISON & PROGRESS -----------------

@router.get("/interviews/compare", response_model=InterviewComparisonResponse)
def compare_interviews(
    first_id: int = Query(..., description="ID of the first/baseline interview"),
    second_id: int = Query(..., description="ID of the second/recent interview"),
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Compares performance metrics across two distinct interview sessions for the authenticated student.
    """
    return ProgressAnalyticsService.compare_interviews(
        db=db,
        user_id=current_user.id,
        first_id=first_id,
        second_id=second_id
    )

@router.get("/progress", response_model=ProgressResponse)
def get_user_progress(
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Fetches longitudinal progress analytics, category improvement deltas, and trend points across all completed sessions.
    """
    return ProgressAnalyticsService.get_user_progress(db, current_user.id)

# ----------------- INTERVIEW DETAILS & UPLOADS -----------------

@router.get("/interviews/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Get details of a specific interview session."""
    interview = InterviewService.get_interview_by_id(db, interview_id, current_user.id)
    return InterviewResponse(**interview.to_dict())

@router.post("/interviews/{interview_id}/upload-resume", response_model=FileUploadResponse)
async def upload_resume(
    interview_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Upload and parse Resume (PDF/DOCX) for the interview."""
    interview, word_count = await FileService.upload_resume(db, interview_id, current_user.id, file)
    return FileUploadResponse(
        message="Resume uploaded and processed successfully.",
        interview_id=interview.id,
        file_type="resume",
        filename=interview.resume_filename,
        original_name=interview.resume_original_name,
        word_count=word_count,
        interview_status=interview.status
    )

@router.post("/interviews/{interview_id}/upload-jd", response_model=FileUploadResponse)
async def upload_jd(
    interview_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Upload and parse Job Description (PDF/DOCX) for Company-specific interview."""
    interview, word_count = await FileService.upload_jd(db, interview_id, current_user.id, file)
    return FileUploadResponse(
        message="Job Description uploaded and processed successfully.",
        interview_id=interview.id,
        file_type="jd",
        filename=interview.jd_filename,
        original_name=interview.jd_original_name,
        word_count=word_count,
        interview_status=interview.status
    )


@router.post("/interviews/{interview_id}/submit-jd", response_model=FileUploadResponse)
async def submit_jd_text(
    interview_id: int,
    jd_text: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Submit JD as plain text (pasted into textarea)."""
    interview = await FileService.submit_jd_text(db, interview_id, current_user.id, jd_text, original_name="pasted")
    word_count = len((interview.jd_text or "").split())
    return FileUploadResponse(
        message="Job Description saved from text input.",
        interview_id=interview.id,
        file_type="jd",
        filename=interview.jd_filename,
        original_name=interview.jd_original_name or 'pasted',
        word_count=word_count,
        interview_status=interview.status
    )

@router.get("/interviews/{interview_id}/status", response_model=InterviewStatusResponse)
def get_interview_status(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Get current readiness and completion status for an interview session."""
    interview = InterviewService.get_interview_by_id(db, interview_id, current_user.id)
    is_ready = False
    message = ""

    if interview.interview_type == "general":
        is_ready = bool(interview.resume_filename or interview.resume_text)
        message = "Ready to start AI voice interview." if is_ready else "Resume upload required."
        if interview.resume_analysis_json:
            try:
                import json as _json
                parsed = _json.loads(interview.resume_analysis_json)
                if isinstance(parsed, dict) and parsed.get('validation'):
                    if not parsed['validation'].get('is_valid', True):
                        is_ready = False
                        message = "Resume validation failed."
            except Exception:
                pass
    elif interview.interview_type == "company":
        has_resume = bool(interview.resume_filename or interview.resume_text)
        has_jd = bool(interview.jd_filename or interview.jd_text)
        is_ready = bool(has_resume and has_jd)
        message = "Ready to start AI voice interview." if is_ready else "Both Resume and Job Description uploads are required."
        if interview.resume_analysis_json and interview.jd_analysis_json:
            try:
                import json as _json
                ra = _json.loads(interview.resume_analysis_json)
                ja = _json.loads(interview.jd_analysis_json)
                if isinstance(ra, dict) and ra.get('validation') and not ra['validation'].get('is_valid', True):
                    is_ready = False
                    message = "Resume validation failed."
                if isinstance(ja, dict) and ja.get('validation') and not ja['validation'].get('is_valid', True):
                    is_ready = False
                    message = "Job description validation failed."
            except Exception:
                pass

    if interview.status == "completed":
        message = "Interview session completed."
    elif interview.status == "in_progress":
        message = "Interview session is in progress."

    return InterviewStatusResponse(
        id=interview.id,
        status=interview.status,
        interview_type=interview.interview_type,
        is_resume_uploaded=bool(interview.resume_filename or interview.resume_text),
        is_jd_uploaded=bool(interview.jd_filename or interview.jd_text),
        is_ready=is_ready,
        message=message
    )

# ----------------- MASTER PROMPT 2: ENGINE & VOICE SESSION -----------------

@router.post("/interviews/{interview_id}/process", response_model=DocumentProcessResponse)
async def process_interview_documents(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Extracts structured Resume and JD profiles and performs skill matching."""
    resume_prof, jd_prof, skill_match, resume_validation, jd_validation, ats_analysis = await InterviewService.process_interview_documents(
        db, interview_id, current_user.id
    )

    # Determine status string
    if resume_validation and not resume_validation.get("is_valid"):
        status_str = "validation_failed"
    elif jd_validation and not jd_validation.get("is_valid"):
        status_str = "validation_failed"
    else:
        status_str = "processed"

    return DocumentProcessResponse(
        status=status_str,
        interview_id=interview_id,
        resume_validation=resume_validation,
        jd_validation=jd_validation,
        resume_analysis=resume_prof,
        jd_analysis=jd_prof,
        skill_match=skill_match,
        ats_analysis=ats_analysis
    )

@router.post("/interviews/{interview_id}/generate-questions", response_model=QuestionListResponse)
async def generate_questions(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Generates personalized interview questions based on candidate profile, target role, and JD."""
    questions = await InterviewService.generate_questions(db, interview_id, current_user.id)
    return QuestionListResponse(
        interview_id=interview_id,
        total_questions=len(questions),
        questions=questions
    )

@router.get("/interviews/{interview_id}/questions", response_model=QuestionListResponse)
def get_questions(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Retrieves all generated questions for this interview session."""
    questions = InterviewService.get_interview_questions(db, interview_id, current_user.id)
    return QuestionListResponse(
        interview_id=interview_id,
        total_questions=len(questions),
        questions=questions
    )

@router.post("/interviews/{interview_id}/start", response_model=InterviewResponse)
def start_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Transitions interview session status to 'in_progress'."""
    interview = InterviewService.start_interview(db, interview_id, current_user.id)
    return InterviewResponse(**interview.to_dict())

@router.post("/interviews/{interview_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    interview_id: int,
    file: UploadFile = File(...),
    fallback_text: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Uploads audio recording and transcribes it into text via Whisper."""
    InterviewService.get_interview_by_id(db, interview_id, current_user.id)
    return await TranscriptionService.save_and_transcribe_audio(file, fallback_text or "")

@router.post("/interviews/{interview_id}/answer", response_model=AnswerSubmitResponse)
async def submit_answer(
    interview_id: int,
    data: AnswerSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Submits candidate answer, evaluates technical accuracy, communication, and speech fluency,
    generates dynamic follow-up questions, and advances session state.
    """
    return await InterviewService.submit_answer(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
        question_id=data.question_id,
        transcript=data.transcript,
        speaking_duration=data.speaking_duration or 0.0,
        audio_filename=data.audio_filename
    )

@router.post("/interviews/{interview_id}/vision-frame", response_model=VisionFrameResponse)
def analyze_vision_frame(
    interview_id: int,
    data: VisionFrameRequest,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Processes a webcam video frame for eye-contact proxy, observable posture indicators,
    and facial expression classification pipeline.
    """
    return InterviewService.process_vision_frame(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
        image_base64=data.image_base64,
        question_id=data.question_id
    )

@router.post("/interviews/{interview_id}/complete", response_model=InterviewResponse)
def complete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """Marks the interview session as completed."""
    interview = InterviewService.complete_interview(db, interview_id, current_user.id)
    return InterviewResponse(**interview.to_dict())

# ----------------- MASTER PROMPT 3: SCORING, REPORT & ROADMAP -----------------

@router.post("/interviews/{interview_id}/generate-report", response_model=PerformanceReportResponse)
def generate_interview_report(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Generates and stores the complete Weighted Multi-Modal Performance Report,
    strengths, weaknesses, frequently observed mistakes, and 5-phase personalized roadmap.
    """
    return PerformanceReportService.generate_and_save_report(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id
    )

@router.get("/interviews/{interview_id}/report", response_model=PerformanceReportResponse)
def get_interview_report(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Retrieves the generated multi-modal performance report for this interview session.
    """
    return PerformanceReportService.get_report(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id
    )

@router.get("/interviews/{interview_id}/score", response_model=InterviewScoreResponse)
def get_interview_score(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Retrieves the detailed mathematical score breakdown, dimensions, weights used, and contributions.
    """
    report = PerformanceReportService.get_report(db, interview_id, current_user.id)
    return report.score_breakdown

@router.get("/interviews/{interview_id}/roadmap", response_model=RoadmapResponse)
def get_interview_roadmap(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db)
):
    """
    Retrieves the personalized 5-phase improvement roadmap for this interview session.
    """
    report = PerformanceReportService.get_report(db, interview_id, current_user.id)
    return report.roadmap
