# AI Mock Interview System – An Intelligent Virtual Interview Coach

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python)](https://python.org)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg?style=flat&logo=sqlite)](https://sqlite.org)

An AI-powered placement preparation platform designed for engineering and technology students. The system simulates realistic placement interviews with adaptive question generation, real-time voice interaction, multi-modal performance analytics (technical depth, fluency, pacing, eye-contact proxy, and posture), and actionable 5-phase improvement roadmaps.

---

## 1. Project Overview & Capabilities

The **AI Mock Interview System** prepares students for technical and placement recruitment drives:

1. **Document Intelligence & Skill Matching**: Extracts structured skills, projects, and education from Resumes and Job Descriptions (PDF/DOCX) and normalizes technology aliases (`JS` $\to$ `JavaScript`, `Postgres` $\to$ `PostgreSQL`, `k8s` $\to$ `Kubernetes`, etc.) to identify skill gaps.
2. **Personalized Question Generation**: Generates placement questions across 7 categories (`TECHNICAL`, `RESUME`, `PROJECT`, `SKILL_GAP`, `BEHAVIORAL`, `HR`, `SITUATIONAL`) tailored to candidate experience and target role.
3. **Adaptive Dynamic Follow-ups**: Analyzes answer depth in real-time and dynamically issues follow-up questions probing architectural trade-offs.
4. **Weighted Multi-Modal Interview Scoring Algorithm**: Deterministically combines 6 performance dimensions ($T=40\%, C=20\%, F=15\%, E=10\%, P=10\%, X=5\%$) with dynamic missing-modality normalization.
5. **Comprehensive Performance Reporting**: Generates strengths, weaknesses, frequently observed mistakes, and transparent score contributions ($S_i \times W_i = C_i$).
6. **5-Phase Personalized Improvement Roadmap**: Connects identified weaknesses and skill gaps to structured practice milestones across 5 phases.
7. **Longitudinal Progress Tracking & Interview Comparison**: Tracks improvement trends across multiple completed sessions with side-by-side comparison analytics.

---

## 2. Technology Stack

### Frontend

- **Framework**: React 18 / Single-Page Application (SPA)
- **Routing**: React Router DOM v6
- **Voice & Speech**: Web Speech Synthesis API (TTS) & MediaRecorder Audio API
- **Styling**: Modern responsive CSS3 with CSS variables, stats grid, and waveform animations

### Backend

- **Framework**: FastAPI (Python 3.11)
- **AI / LLM Service**: Google Gemini API via `from google import genai` / REST API
- **Speech-to-Text**: Whisper STT Architecture (`transcription_service.py`)
- **Computer Vision**: OpenCV (`cv2`) Face Centrality & Posture estimation pipeline
- **Emotion Recognition**: FER2013 7-Class CNN architecture interface (`emotion_service.py`)
- **Document Parsers**: `pypdf` (PDF text extraction), `python-docx` (Word document parsing)
- **Security & Crypto**: PBKDF2-HMAC-SHA256 password hashing, RFC 7519 HMAC-SHA256 JWT tokens

---

## 3. Weighted Multi-Modal Interview Scoring Formula

$$\text{Overall Score } S_{overall} = \frac{\sum_{i \in \mathcal{A}} \left( S_i \times w_i \right)}{\sum_{i \in \mathcal{A}} w_i}$$

Where $\mathcal{A}$ is the set of available modalities:

- **Technical Knowledge ($T$)**: Weight $0.40$ (40%)
- **Communication ($C$)**: Weight $0.20$ (20%)
- **Fluency ($F$)**: Weight $0.15$ (15%)
- **Eye-Contact Proxy ($E$)**: Weight $0.10$ (10%)
- **Posture & Professional Behaviour ($P$)**: Weight $0.10$ (10%)
- **Facial Expression / Behavioural Stability ($X$)**: Weight $0.05$ (5%)

---

## 4. REST API Reference

| Endpoint                                  | Method | Description                                    |
| ----------------------------------------- | ------ | ---------------------------------------------- |
| `/api/auth/register`                      | `POST` | Student registration                           |
| `/api/auth/login`                         | `POST` | JWT authentication                             |
| `/api/auth/me`                            | `GET`  | User profile retrieval                         |
| `/api/interviews`                         | `POST` | Create interview session                       |
| `/api/interviews`                         | `GET`  | List interviews & summary stats                |
| `/api/interviews/{id}/upload-resume`      | `POST` | Upload candidate resume                        |
| `/api/interviews/{id}/upload-jd`          | `POST` | Upload job description                         |
| `/api/interviews/{id}/process`            | `POST` | Parse documents & match skills                 |
| `/api/interviews/{id}/generate-questions` | `POST` | Generate personalized questions                |
| `/api/interviews/{id}/questions`          | `GET`  | Retrieve session questions                     |
| `/api/interviews/{id}/start`              | `POST` | Start interview (`in_progress`)                |
| `/api/interviews/{id}/transcribe`         | `POST` | Whisper speech-to-text audio upload            |
| `/api/interviews/{id}/answer`             | `POST` | Evaluate answer & dynamic follow-up            |
| `/api/interviews/{id}/vision-frame`       | `POST` | Analyze webcam frame & posture                 |
| `/api/interviews/{id}/complete`           | `POST` | Complete interview session                     |
| `/api/interviews/{id}/generate-report`    | `POST` | Generate & persist complete report & roadmap   |
| `/api/interviews/{id}/report`             | `GET`  | Retrieve full performance report               |
| `/api/interviews/{id}/score`              | `GET`  | Retrieve score matrix & weights                |
| `/api/interviews/{id}/roadmap`            | `GET`  | Retrieve 5-phase personalized roadmap          |
| `/api/progress`                           | `GET`  | Longitudinal progress trends & category deltas |
| `/api/interviews/compare`                 | `GET`  | Compare 2 sessions (`?first_id=X&second_id=Y`) |

---

## 5. Architecture and Interview Data Flow

The React/Vite frontend authenticates with the FastAPI backend, creates an interview, uploads the resume and optional JD, and opens the protected session route. The existing session component speaks each AI question, starts the existing MediaRecorder flow after TTS, detects silence, and creates the completed WebM Blob. Camera and audio lifecycle code are intentionally kept separate.

The completed Blob is uploaded to Whisper through `POST /api/interviews/{id}/transcribe`. The backend saves the audio, transcribes it with English decoding and a technical-vocabulary prompt containing the active question context, and returns the actual transcript. The frontend then submits that transcript to `/api/interviews/{id}/answer`; the existing evaluator stores the answer, evaluates technical/communication/fluency dimensions, and sends the same transcript to adaptive follow-up generation.

The report reads the stored question, transcript, answer analysis, behavioural observations, score dimensions, resume/JD match, and history. The roadmap keeps five phases but changes titles and item resources according to the observed weaknesses and role gaps.

## 6. Setup

Prerequisites:

- Python 3.11+ and a project virtual environment
- Node.js and npm
- FFmpeg on `PATH` for WebM/audio decoding
- Browser microphone and camera permissions
- Gemini API key for dynamic questions and AI evaluation
- Whisper model weights downloaded on first use

Backend setup from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Set `GEMINI_API_KEY` in `backend/.env`. `WHISPER_MODEL=base` is the default. Verify dependencies:

```powershell
ffmpeg -version
.\.venv\Scripts\python.exe -c "import whisper; print('Whisper import: OK')"
```

Run the backend with the project interpreter:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

Environment variables are read from `backend/.env`:

| Variable                                                                      |        Required | Purpose                                                |
| ----------------------------------------------------------------------------- | --------------: | ------------------------------------------------------ |
| `SECRET_KEY`                                                                  |      Production | JWT signing secret                                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES`                                                 |              No | Token lifetime                                         |
| `DATABASE_PATH`                                                               |              No | SQLite path; defaults to the configured local database |
| `GEMINI_API_KEY`                                                              | Gemini features | Dynamic question generation and structured evaluation  |
| `GEMINI_MODEL`                                                                |              No | Gemini model name                                      |
| `WHISPER_MODEL`                                                               |              No | Local Whisper model, default `base`                    |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` |       OTP email | Verification/reset email delivery                      |

SQLite tables are created or upgraded additively by `backend/app/database/base.py` during FastAPI startup. No destructive migration is required for the current transcript flow.

## 7. Performance, Roadmap, and Resources

Scoring preserves the weighted multi-modal algorithm and missing-modality normalization. The report builds question-level breakdowns only from the stored candidate transcript and answer analysis; failed transcription does not receive fabricated feedback.

Roadmap content is selected from technical, communication, fluency, behavioural, question-level, mistake, skill-gap, and historical evidence. Each item includes a diagnostic problem, action, practice task, measurable target, evidence summary, and resources selected from a maintained allow-list. Resources are topic-specific official documentation or established educational pages; the UI renders them as safe external links.

## 8. Testing

Use the project interpreter and backend import path:

```powershell
$env:PYTHONPATH='backend'
$env:TESTING='1'
..\.venv\Scripts\python.exe -m pytest -q
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## 9. Troubleshooting and Limitations

- If Whisper cannot be imported, start Uvicorn with `..\.venv\Scripts\python.exe -m uvicorn ...`; a system-Python reload worker may not see the project package.
- If WebM decoding fails, confirm `ffmpeg -version` works from the same shell that starts the backend.
- Technical transcription uses Whisper `initial_prompt`, English decoding, deterministic temperature, and the active question context. It does not blindly replace words such as “palindrome” with “polynomial”.
- Gemini HTTP 429 responses indicate provider quota/rate limits and can prevent dynamic questions or follow-ups.
- Facial-expression scoring depends on optional model weights; unavailable modalities remain excluded through existing normalization.
- The current test suite contains live Gemini-dependent tests, so quota/network availability can affect those tests independently of local transcription and roadmap logic.

---

## 7. Academic Research Notes

- **Eye-Contact Proxy Score**: Derived from geometric face bounding box centrality and frame aspect ratios. Does not claim psychological gaze measurement.
- **Speech Fluency Score**: Formulated as an objective speech-performance delivery metric based on Words Per Minute and disfluency frequencies.
- **Facial Expression Classification**: Identifies physical muscle movements into 7 FER2013 categories and is not used as a clinical measure of stress or nervousness.
