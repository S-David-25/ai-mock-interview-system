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

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | `POST` | Student registration |
| `/api/auth/login` | `POST` | JWT authentication |
| `/api/auth/me` | `GET` | User profile retrieval |
| `/api/interviews` | `POST` | Create interview session |
| `/api/interviews` | `GET` | List interviews & summary stats |
| `/api/interviews/{id}/upload-resume` | `POST` | Upload candidate resume |
| `/api/interviews/{id}/upload-jd` | `POST` | Upload job description |
| `/api/interviews/{id}/process` | `POST` | Parse documents & match skills |
| `/api/interviews/{id}/generate-questions` | `POST` | Generate personalized questions |
| `/api/interviews/{id}/questions` | `GET` | Retrieve session questions |
| `/api/interviews/{id}/start` | `POST` | Start interview (`in_progress`) |
| `/api/interviews/{id}/transcribe` | `POST` | Whisper speech-to-text audio upload |
| `/api/interviews/{id}/answer` | `POST` | Evaluate answer & dynamic follow-up |
| `/api/interviews/{id}/vision-frame` | `POST` | Analyze webcam frame & posture |
| `/api/interviews/{id}/complete` | `POST` | Complete interview session |
| `/api/interviews/{id}/generate-report` | `POST` | Generate & persist complete report & roadmap |
| `/api/interviews/{id}/report` | `GET` | Retrieve full performance report |
| `/api/interviews/{id}/score` | `GET` | Retrieve score matrix & weights |
| `/api/interviews/{id}/roadmap` | `GET` | Retrieve 5-phase personalized roadmap |
| `/api/progress` | `GET` | Longitudinal progress trends & category deltas |
| `/api/interviews/compare` | `GET` | Compare 2 sessions (`?first_id=X&second_id=Y`) |

---

## 5. Verification & Test Execution

Execute the full automated test suite (45 passing tests):

```bash
PYTHONPATH=backend python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 6. Known Limitations & Blocked Dependencies

- **Whisper STT Local Model Weights**: In the offline sandbox environment without outbound internet or CUDA drivers, audio speech ingestion operates with audio metadata extraction and browser Web Speech transcript synchronization. Marked: `BLOCKED — OpenAI Whisper package / GPU runtime not loaded in offline sandbox`.
- **FER2013 CNN Model Weights**: If `fer2013_cnn.h5` weights file is not present, the scoring algorithm applies missing-modality normalization without assigning fake scores. Marked: `BLOCKED — FER2013 model weights file not loaded in environment`.

---

## 7. Academic Research Notes

- **Eye-Contact Proxy Score**: Derived from geometric face bounding box centrality and frame aspect ratios. Does not claim psychological gaze measurement.
- **Speech Fluency Score**: Formulated as an objective speech-performance delivery metric based on Words Per Minute and disfluency frequencies.
- **Facial Expression Classification**: Identifies physical muscle movements into 7 FER2013 categories and is not used as a clinical measure of stress or nervousness.
