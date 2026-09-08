import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Interview:
    id: Optional[int] = None
    user_id: int = 0
    interview_type: str = "general" # "company" or "general"
    company_name: Optional[str] = None
    job_role: Optional[str] = None
    jd_filename: Optional[str] = None
    jd_original_name: Optional[str] = None
    jd_text: Optional[str] = None
    resume_filename: Optional[str] = None
    resume_original_name: Optional[str] = None
    resume_text: Optional[str] = None
    resume_analysis_json: Optional[str] = None
    jd_analysis_json: Optional[str] = None
    skill_match_json: Optional[str] = None
    ats_analysis_json: Optional[str] = None
    duration_minutes: int = 30
    started_at: Optional[str] = None
    expires_at: Optional[str] = None
    status: str = "setup" # setup, processing, ready, in_progress, completed, failed
    overall_score: Optional[float] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    facial_score: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        return cls(
            id=row.get("id"),
            user_id=row.get("user_id"),
            interview_type=row.get("interview_type"),
            company_name=row.get("company_name"),
            job_role=row.get("job_role"),
            jd_filename=row.get("jd_filename"),
            jd_original_name=row.get("jd_original_name"),
            jd_text=row.get("jd_text"),
            resume_filename=row.get("resume_filename"),
            resume_original_name=row.get("resume_original_name"),
            resume_text=row.get("resume_text"),
            resume_analysis_json=row.get("resume_analysis_json"),
            jd_analysis_json=row.get("jd_analysis_json"),
            skill_match_json=row.get("skill_match_json"),
            ats_analysis_json=row.get("ats_analysis_json"),
            duration_minutes=int(row.get("duration_minutes") or 30),
            started_at=row.get("started_at"),
            expires_at=row.get("expires_at"),
            status=row.get("status"),
            overall_score=row.get("overall_score"),
            technical_score=row.get("technical_score"),
            communication_score=row.get("communication_score"),
            facial_score=row.get("facial_score"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def to_dict(self, include_text: bool = False, include_analysis: bool = True) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "interview_type": self.interview_type,
            "company_name": self.company_name,
            "job_role": self.job_role,
            "jd_filename": self.jd_filename,
            "jd_original_name": self.jd_original_name,
            "resume_filename": self.resume_filename,
            "resume_original_name": self.resume_original_name,
            "duration_minutes": self.duration_minutes,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "overall_score": self.overall_score,
            "technical_score": self.technical_score,
            "communication_score": self.communication_score,
            "facial_score": self.facial_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_resume_uploaded": bool(self.resume_filename or self.resume_text),
            "is_jd_uploaded": bool(self.jd_filename or self.jd_text),
        }
        if include_text:
            data["jd_text"] = self.jd_text
            data["resume_text"] = self.resume_text
        if include_analysis:
            data["resume_analysis"] = json.loads(self.resume_analysis_json) if self.resume_analysis_json else None
            data["jd_analysis"] = json.loads(self.jd_analysis_json) if self.jd_analysis_json else None
            data["skill_match"] = json.loads(self.skill_match_json) if self.skill_match_json else None
            data["ats_analysis"] = json.loads(self.ats_analysis_json) if getattr(self, 'ats_analysis_json', None) else None
        return data

@dataclass
class InterviewQuestion:
    id: Optional[int] = None
    interview_id: int = 0
    question_text: str = ""
    question_category: str = "TECHNICAL" # TECHNICAL, RESUME, PROJECT, SKILL_GAP, BEHAVIORAL, HR, SITUATIONAL
    difficulty: str = "MEDIUM" # EASY, MEDIUM, HARD
    expected_focus: List[str] = field(default_factory=list)
    source: str = "GENERAL" # RESUME, JD, FOLLOW_UP, GENERAL
    order_num: int = 1
    parent_question_id: Optional[int] = None
    status: str = "pending" # pending, answered, skipped
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        expected_focus_raw = row.get("expected_focus_json")
        try:
            focus_list = json.loads(expected_focus_raw) if expected_focus_raw else []
        except Exception:
            focus_list = []

        return cls(
            id=row.get("id"),
            interview_id=row.get("interview_id"),
            question_text=row.get("question_text"),
            question_category=row.get("question_category", "TECHNICAL"),
            difficulty=row.get("difficulty", "MEDIUM"),
            expected_focus=focus_list,
            source=row.get("source", "GENERAL"),
            order_num=row.get("order_num", 1),
            parent_question_id=row.get("parent_question_id"),
            status=row.get("status", "pending"),
            created_at=row.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "question_text": self.question_text,
            "question_category": self.question_category,
            "difficulty": self.difficulty,
            "expected_focus": self.expected_focus,
            "source": self.source,
            "order_num": self.order_num,
            "parent_question_id": self.parent_question_id,
            "status": self.status,
            "created_at": self.created_at,
        }

@dataclass
class InterviewAnswer:
    id: Optional[int] = None
    interview_id: int = 0
    question_id: int = 0
    transcript_text: str = ""
    audio_filename: Optional[str] = None
    duration_seconds: float = 0.0
    word_count: int = 0
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        return cls(
            id=row.get("id"),
            interview_id=row.get("interview_id"),
            question_id=row.get("question_id"),
            transcript_text=row.get("transcript_text", ""),
            audio_filename=row.get("audio_filename"),
            duration_seconds=float(row.get("duration_seconds") or 0.0),
            word_count=int(row.get("word_count") or 0),
            created_at=row.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "question_id": self.question_id,
            "transcript_text": self.transcript_text,
            "audio_filename": self.audio_filename,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "created_at": self.created_at,
        }

@dataclass
class AnswerAnalysis:
    id: Optional[int] = None
    interview_id: int = 0
    question_id: int = 0
    answer_id: int = 0
    technical_score: float = 0.0
    correctness: float = 0.0
    relevance: float = 0.0
    completeness: float = 0.0
    depth: float = 0.0
    technical_feedback: str = ""
    fluency_score: float = 0.0
    wpm: float = 0.0
    speaking_duration: float = 0.0
    filler_word_count: int = 0
    filler_words: List[str] = field(default_factory=list)
    repeated_words: List[str] = field(default_factory=list)
    grammar_score: float = 0.0
    vocabulary_score: float = 0.0
    clarity_score: float = 0.0
    communication_score: float = 0.0
    communication_feedback: str = ""
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        fillers = []
        repeats = []
        try:
            fillers = json.loads(row.get("filler_words_json") or "[]")
            repeats = json.loads(row.get("repeated_words_json") or "[]")
        except Exception:
            pass

        return cls(
            id=row.get("id"),
            interview_id=row.get("interview_id"),
            question_id=row.get("question_id"),
            answer_id=row.get("answer_id"),
            technical_score=float(row.get("technical_score") or 0.0),
            correctness=float(row.get("correctness") or 0.0),
            relevance=float(row.get("relevance") or 0.0),
            completeness=float(row.get("completeness") or 0.0),
            depth=float(row.get("depth") or 0.0),
            technical_feedback=row.get("technical_feedback") or "",
            fluency_score=float(row.get("fluency_score") or 0.0),
            wpm=float(row.get("wpm") or 0.0),
            speaking_duration=float(row.get("speaking_duration") or 0.0),
            filler_word_count=int(row.get("filler_word_count") or 0),
            filler_words=fillers,
            repeated_words=repeats,
            grammar_score=float(row.get("grammar_score") or 0.0),
            vocabulary_score=float(row.get("vocabulary_score") or 0.0),
            clarity_score=float(row.get("clarity_score") or 0.0),
            communication_score=float(row.get("communication_score") or 0.0),
            communication_feedback=row.get("communication_feedback") or "",
            created_at=row.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "question_id": self.question_id,
            "answer_id": self.answer_id,
            "technical_score": self.technical_score,
            "correctness": self.correctness,
            "relevance": self.relevance,
            "completeness": self.completeness,
            "depth": self.depth,
            "technical_feedback": self.technical_feedback,
            "fluency_score": self.fluency_score,
            "wpm": self.wpm,
            "speaking_duration": self.speaking_duration,
            "filler_word_count": self.filler_word_count,
            "filler_words": self.filler_words,
            "repeated_words": self.repeated_words,
            "grammar_score": self.grammar_score,
            "vocabulary_score": self.vocabulary_score,
            "clarity_score": self.clarity_score,
            "communication_score": self.communication_score,
            "communication_feedback": self.communication_feedback,
            "created_at": self.created_at,
        }

@dataclass
class BehaviorAnalysis:
    id: Optional[int] = None
    interview_id: int = 0
    question_id: Optional[int] = None
    answer_id: Optional[int] = None
    face_detected: bool = False
    camera_facing_ratio: float = 0.0
    eye_contact_proxy_score: float = 0.0
    posture_score: float = 0.0
    head_stability_score: float = 0.0
    dominant_emotion: str = "Neutral"
    emotion_probabilities: Dict[str, float] = field(default_factory=dict)
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        emotions = {}
        try:
            emotions = json.loads(row.get("emotion_probabilities_json") or "{}")
        except Exception:
            pass

        return cls(
            id=row.get("id"),
            interview_id=row.get("interview_id"),
            question_id=row.get("question_id"),
            answer_id=row.get("answer_id"),
            face_detected=bool(row.get("face_detected")),
            camera_facing_ratio=float(row.get("camera_facing_ratio") or 0.0),
            eye_contact_proxy_score=float(row.get("eye_contact_proxy_score") or 0.0),
            posture_score=float(row.get("posture_score") or 0.0),
            head_stability_score=float(row.get("head_stability_score") or 0.0),
            dominant_emotion=row.get("dominant_emotion") or "Neutral",
            emotion_probabilities=emotions,
            created_at=row.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interview_id": self.interview_id,
            "question_id": self.question_id,
            "answer_id": self.answer_id,
            "face_detected": self.face_detected,
            "camera_facing_ratio": self.camera_facing_ratio,
            "eye_contact_proxy_score": self.eye_contact_proxy_score,
            "posture_score": self.posture_score,
            "head_stability_score": self.head_stability_score,
            "dominant_emotion": self.dominant_emotion,
            "emotion_probabilities": self.emotion_probabilities,
            "created_at": self.created_at,
        }
