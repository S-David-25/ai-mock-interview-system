import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR = BASE_DIR / "uploads"
RESUME_UPLOAD_DIR = UPLOAD_DIR / "resumes"
JD_UPLOAD_DIR = UPLOAD_DIR / "jds"
AUDIO_UPLOAD_DIR = UPLOAD_DIR / "audio"

# Ensure upload directories exist
RESUME_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Security & Authentication
SECRET_KEY = os.getenv("SECRET_KEY", "ai-mock-interview-academic-secret-key-2026-secure-jwt")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24 hours

# Database Configuration
default_db = Path("/tmp/mock_interview.db") if os.path.exists("/tmp") else (BASE_DIR / "mock_interview.db")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(default_db)))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Storage Limits & Formats
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024))) # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".webm", ".m4a", ".ogg"}

# AI Service Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Interview Logic Parameters
MAX_TOTAL_QUESTIONS = int(os.getenv("MAX_TOTAL_QUESTIONS", "15"))
MAX_FOLLOW_UPS_PER_TOPIC = int(os.getenv("MAX_FOLLOW_UPS_PER_TOPIC", "3"))
INITIAL_QUESTIONS_COUNT = int(os.getenv("INITIAL_QUESTIONS_COUNT", "5"))

# Weighted Multi-Modal Interview Scoring Dimension Weights (Default: 40/20/15/10/10/5 = 100%)
TECHNICAL_WEIGHT = float(os.getenv("TECHNICAL_WEIGHT", "0.40"))
COMMUNICATION_WEIGHT = float(os.getenv("COMMUNICATION_WEIGHT", "0.20"))
FLUENCY_WEIGHT = float(os.getenv("FLUENCY_WEIGHT", "0.15"))
EYE_CONTACT_WEIGHT = float(os.getenv("EYE_CONTACT_WEIGHT", "0.10"))
POSTURE_WEIGHT = float(os.getenv("POSTURE_WEIGHT", "0.10"))
EXPRESSION_WEIGHT = float(os.getenv("EXPRESSION_WEIGHT", "0.05"))

# Readiness Level Thresholds
READINESS_EXCELLENT_MIN = float(os.getenv("READINESS_EXCELLENT_MIN", "90.0"))
READINESS_VERY_GOOD_MIN = float(os.getenv("READINESS_VERY_GOOD_MIN", "80.0"))
READINESS_GOOD_MIN = float(os.getenv("READINESS_GOOD_MIN", "70.0"))
READINESS_NEEDS_IMPROVEMENT_MIN = float(os.getenv("READINESS_NEEDS_IMPROVEMENT_MIN", "60.0"))

# CORS
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "*",
]
