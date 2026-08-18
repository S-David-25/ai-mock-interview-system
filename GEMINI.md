# GEMINI.md – AI Mock Interview System (Complete Engineering Specification)

## 1. System Overview

The **AI Mock Interview System – An Intelligent Virtual Interview Coach** is an academic software project for placement preparation, empirical testing, and research demonstration.

### System Progression Across Master Prompts:
- **Master Prompt 1**: User registration, login, JWT authorization, SQLite database, Student Dashboard, Interview Setup (Company vs General), Document Ingestion & Text Extraction (PDF/DOCX).
- **Master Prompt 2**: Google Gemini integration, Resume Analysis, JD Analysis, Deterministic Skill Normalization & Gap Analysis, Personalized Question Generation (7 Categories), Adaptive Dynamic Follow-ups, Audio Ingestion, Multi-Modal Answer Evaluation (Technical, Communication, Fluency), OpenCV Vision Tracking, and Interactive Voice Interview Room.
- **Master Prompt 3**: Weighted Multi-Modal Interview Scoring Algorithm, Missing-Modality Normalization, Readiness Level Classification, Confidence Indicator, Comprehensive Performance Reporting, 5-Phase Personalized Roadmap Synthesis, Longitudinal Progress Tracking, and Interview Comparison Analytics.

---

## 2. Mathematical Scoring Specification

### 2.1 Formula
$$\text{Overall Score } S_{overall} = \frac{\sum_{i \in \mathcal{A}} \left( S_i \times w_i \right)}{\sum_{i \in \mathcal{A}} w_i}$$

- $w_T = 0.40$ (Technical Knowledge)
- $w_C = 0.20$ (Communication)
- $w_F = 0.15$ (Speech Fluency)
- $w_E = 0.10$ (Eye-Contact Proxy)
- $w_P = 0.10$ (Posture & Behaviour)
- $w_X = 0.05$ (Facial Expression)

### 2.2 Missing-Modality Normalization
When modality $m \notin \mathcal{A}$ is unavailable (e.g. $X$ when FER2013 weights are absent), $\sum_{i \in \mathcal{A}} w_i = 0.95$, and the remaining scores are normalized by $0.95$ so the candidate is evaluated fairly.

---

## 3. Packaging & File Structure

```
ai-mock-interview/
├── frontend/                     # React 18 + Vite SPA
│   ├── src/
│   │   ├── pages/                # Login, Register, Dashboard, InterviewSetup, InterviewDetail, InterviewSession, InterviewReport, InterviewCompare
│   │   ├── components/
│   │   ├── services/
│   │   ├── context/
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
│
├── backend/                      # FastAPI Python Application
│   ├── app/
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── database/
│   │   ├── schemas/
│   │   ├── static/               # Standalone interactive SPA bundle
│   │   ├── main.py
│   │   └── config.py
│   ├── uploads/
│   ├── requirements.txt
│   └── .env.example
│
├── docs/
│   ├── algorithms.md             # Mathematical formulations
│   ├── architecture.md           # Pipeline architecture
│   ├── api.md                    # REST API specifications
│   └── testing.md                # Test execution report
│
├── tests/
│   ├── test_auth.py
│   ├── test_interviews.py
│   ├── test_file_upload.py
│   ├── test_security.py
│   ├── test_ai_engine.py
│   ├── test_engine_endpoints.py
│   ├── test_scoring_and_report.py
│   └── test_report_endpoints.py
│
├── README.md
└── GEMINI.md
```
