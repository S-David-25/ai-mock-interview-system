from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, root_validator

class InterviewCreate(BaseModel):
    interview_type: str = Field(..., description="'company' or 'general'")
    company_name: Optional[str] = Field(None, max_length=150)
    job_role: Optional[str] = Field(None, max_length=150)

    @root_validator(skip_on_failure=True)
    def validate_interview_fields(cls, values):
        itype = (values.get("interview_type") or "").strip().lower()
        if itype not in ("company", "general"):
            raise ValueError("Interview type must be either 'company' or 'general'.")
        values["interview_type"] = itype

        if itype == "company":
            cname = values.get("company_name")
            jrole = values.get("job_role")
            if not cname or not cname.strip():
                raise ValueError("Company name is required for company-specific mock interviews.")
            if not jrole or not jrole.strip():
                raise ValueError("Job role is required for company-specific mock interviews.")
            values["company_name"] = cname.strip()
            values["job_role"] = jrole.strip()
        else:
            values["company_name"] = None
            values["job_role"] = None
        return values

class ResumeProfileSchema(BaseModel):
    candidate_name: str = ""
    contact_information: Dict[str, Any] = {}
    education: List[str] = []
    technical_skills: List[str] = []
    programming_languages: List[str] = []
    frameworks: List[str] = []
    databases: List[str] = []
    tools: List[str] = []
    projects: List[Dict[str, Any]] = []  # Each project: {name, description, technologies, responsibilities, outcomes}
    certifications: List[str] = []
    achievements: List[str] = []
    experience: List[Dict[str, Any]] = []  # Each experience: {company, role, duration, responsibilities, technologies, achievements}
    internships: List[Dict[str, Any]] = []
    areas_of_expertise: List[str] = []
    soft_skills: List[str] = []
    languages_known: List[str] = []

class JDProfileSchema(BaseModel):
    company: str = ""
    job_role: str = ""
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities: List[str] = []
    technologies: List[str] = []
    experience_requirements: List[str] = []
    soft_skills: List[str] = []
    important_keywords: List[str] = []

class SkillMatchSchema(BaseModel):
    matched_skills: List[str] = []
    skill_gaps: List[str] = []
    related_skills: List[str] = []
    priority_skills: List[str] = []
    match_percentage: float = 0.0

class InterviewResponse(BaseModel):
    id: int
    user_id: int
    interview_type: str
    company_name: Optional[str] = None
    job_role: Optional[str] = None
    jd_filename: Optional[str] = None
    jd_original_name: Optional[str] = None
    resume_filename: Optional[str] = None
    resume_original_name: Optional[str] = None
    status: str
    overall_score: Optional[float] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    facial_score: Optional[float] = None
    created_at: str
    updated_at: str
    is_resume_uploaded: bool
    is_jd_uploaded: bool
    resume_analysis: Optional[Dict[str, Any]] = None
    jd_analysis: Optional[Dict[str, Any]] = None
    skill_match: Optional[Dict[str, Any]] = None
    ats_analysis: Optional[Dict[str, Any]] = None

class InterviewStats(BaseModel):
    total_interviews: int
    average_score: Optional[float] = None
    latest_score: Optional[float] = None
    completed_count: int = 0
    ready_count: int = 0
    setup_count: int = 0

class InterviewListResponse(BaseModel):
    interviews: List[InterviewResponse]
    stats: InterviewStats

class InterviewStatusResponse(BaseModel):
    id: int
    status: str
    interview_type: str
    is_resume_uploaded: bool
    is_jd_uploaded: bool
    is_ready: bool
    message: str

class FileUploadResponse(BaseModel):
    message: str
    interview_id: int
    file_type: str
    filename: str
    original_name: str
    word_count: int
    interview_status: str

class QuestionSchema(BaseModel):
    id: Optional[int] = None
    interview_id: int
    question: str
    category: str
    difficulty: str
    expected_focus: List[str] = []
    source: str
    order_number: int
    status: str = "pending"

class QuestionListResponse(BaseModel):
    interview_id: int
    total_questions: int
    questions: List[QuestionSchema]

class DocumentProcessResponse(BaseModel):
    status: str
    interview_id: int
    resume_validation: Optional[Dict[str, Any]] = None
    jd_validation: Optional[Dict[str, Any]] = None
    resume_analysis: Optional[ResumeProfileSchema] = None
    jd_analysis: Optional[JDProfileSchema] = None
    skill_match: Optional[SkillMatchSchema] = None
    ats_analysis: Optional[Dict[str, Any]] = None

class AnswerSubmitRequest(BaseModel):
    question_id: int
    transcript: str
    speaking_duration: Optional[float] = 0.0
    audio_filename: Optional[str] = None

class TechnicalEvaluationSchema(BaseModel):
    technical_score: float
    correctness: float
    relevance: float
    completeness: float
    depth: float
    feedback: str

class CommunicationEvaluationSchema(BaseModel):
    grammar_score: float
    vocabulary_score: float
    clarity_score: float
    communication_score: float
    feedback: str

class FluencyEvaluationSchema(BaseModel):
    fluency_score: float
    wpm: float
    speaking_duration: float
    filler_word_count: int
    filler_words: List[str] = []
    repeated_words: List[str] = []

class AnswerSubmitResponse(BaseModel):
    interview_id: int
    question_id: int
    answer_id: int
    technical_evaluation: TechnicalEvaluationSchema
    communication_evaluation: CommunicationEvaluationSchema
    fluency_evaluation: FluencyEvaluationSchema
    is_follow_up: bool
    next_question: Optional[QuestionSchema] = None
    is_completed: bool = False
    message: str

class TranscriptionResponse(BaseModel):
    transcript: str
    duration_seconds: float
    word_count: int
    audio_filename: str

class VisionFrameRequest(BaseModel):
    question_id: Optional[int] = None
    image_base64: str

class VisionFrameResponse(BaseModel):
    face_detected: bool
    camera_facing_ratio: float
    eye_contact_proxy_score: float
    posture_score: float
    head_stability_score: float
    dominant_emotion: str
    emotion_probabilities: Dict[str, float]
    status: str

# ----------------- MASTER PROMPT 3 SCHEMAS -----------------

class DimensionScoreSchema(BaseModel):
    raw_score: float
    weight: float
    contribution: float
    is_available: bool = True
    status_note: Optional[str] = None

class InterviewScoreResponse(BaseModel):
    interview_id: int
    overall_score: float
    readiness_level: str
    confidence_indicator: float
    dimensions: Dict[str, DimensionScoreSchema]
    weights_used: Dict[str, float]
    available_weights_sum: float
    unavailable_modalities: List[str] = []

class CategoryRatingSchema(BaseModel):
    category_name: str
    score: float
    level: str
    strengths: str
    weaknesses: str
    recommendation: str

class MistakeItemSchema(BaseModel):
    mistake_type: str
    description: str
    frequency: int
    severity: str # High, Medium, Low
    remediation_tip: str

class QuestionBreakdownSchema(BaseModel):
    order_number: int
    question: str
    category: str
    difficulty: str
    candidate_answer: str
    technical_score: float
    communication_score: float
    fluency_score: float
    feedback: str
    strengths: str
    weaknesses: str

class RoadmapItemSchema(BaseModel):
    area: str
    problem: str
    recommended_action: str
    practice_task: str
    priority: str # High, Medium, Low
    estimated_duration: str
    measurable_target: str

class RoadmapPhaseSchema(BaseModel):
    phase_number: int
    phase_title: str
    focus_objective: str
    items: List[RoadmapItemSchema]

class RoadmapResponse(BaseModel):
    interview_id: int
    user_id: int
    overall_score: float
    readiness_level: str
    phases: List[RoadmapPhaseSchema]
    created_at: str

class PerformanceReportResponse(BaseModel):
    interview_id: int
    user_id: int
    interview_type: str
    company_name: Optional[str] = None
    job_role: Optional[str] = None
    overall_score: float
    readiness_level: str
    confidence_indicator: float
    summary_text: str
    score_breakdown: InterviewScoreResponse
    category_ratings: List[CategoryRatingSchema]
    strengths: List[str]
    weaknesses: List[str]
    frequently_observed_mistakes: List[MistakeItemSchema]
    skill_gaps: List[str]
    matched_skills: List[str]
    match_percentage: float
    question_breakdowns: List[QuestionBreakdownSchema]
    roadmap: RoadmapResponse
    created_at: str

class ProgressTrendPointSchema(BaseModel):
    interview_id: int
    date: str
    interview_type: str
    company_name: Optional[str] = None
    overall_score: float
    technical_score: float
    communication_score: float
    fluency_score: float
    confidence_indicator: float

class CategoryTrendSchema(BaseModel):
    category_name: str
    initial_score: float
    latest_score: float
    delta: float

class ProgressResponse(BaseModel):
    interview_count: int
    average_score: Optional[float]
    best_score: Optional[float]
    latest_score: Optional[float]
    total_score_improvement: Optional[float]
    trend_data: List[ProgressTrendPointSchema]
    category_trends: List[CategoryTrendSchema]

class DimensionComparisonSchema(BaseModel):
    dimension_name: str
    first_score: float
    second_score: float
    delta: float
    status: str # Improved, Declined, Unchanged

class InterviewComparisonResponse(BaseModel):
    first_interview_id: int
    first_interview_date: str
    first_overall_score: float
    second_interview_id: int
    second_interview_date: str
    second_overall_score: float
    overall_delta: float
    overall_status: str
    dimension_comparisons: List[DimensionComparisonSchema]
    improved_areas: List[str]
    declined_areas: List[str]
    unchanged_areas: List[str]
