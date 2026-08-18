# AI Mock Interview System – Complete REST API Specification

All protected endpoints require the HTTP Authorization Header: `Authorization: Bearer <JWT_TOKEN>`.

---

## 1. Authentication (`/api/auth`)

| Method | Endpoint | Description | Payload |
|---|---|---|---|
| `POST` | `/api/auth/register` | Student registration | `{ name, email, password, confirm_password }` |
| `POST` | `/api/auth/login` | Student login & JWT token issue | `{ email, password }` |
| `GET` | `/api/auth/me` | Current user profile | None |
| `POST` | `/api/auth/logout` | Terminate session | None |

---

## 2. Interview Management & Setup (`/api/interviews`)

| Method | Endpoint | Description | Payload |
|---|---|---|---|
| `POST` | `/api/interviews` | Create interview session | `{ interview_type, company_name?, job_role? }` |
| `GET` | `/api/interviews` | List all sessions & summary stats | None |
| `GET` | `/api/interviews/{id}` | Session details & file status | None |
| `POST` | `/api/interviews/{id}/upload-resume` | Upload & parse Resume (PDF/DOCX) | `multipart/form-data` (`file`) |
| `POST` | `/api/interviews/{id}/upload-jd` | Upload & parse JD (PDF/DOCX) | `multipart/form-data` (`file`) |
| `GET` | `/api/interviews/{id}/status` | Readiness & file checklist | None |

---

## 3. AI Interview Engine & Session (`/api/interviews`)

| Method | Endpoint | Description | Payload |
|---|---|---|---|
| `POST` | `/api/interviews/{id}/process` | Document parsing & skill matching | None |
| `POST` | `/api/interviews/{id}/generate-questions` | Generate personalized questions | None |
| `GET` | `/api/interviews/{id}/questions` | List session questions | None |
| `POST` | `/api/interviews/{id}/start` | Start interview session | None |
| `POST` | `/api/interviews/{id}/transcribe` | Audio file ingestion & Whisper STT | `multipart/form-data` (`file`) |
| `POST` | `/api/interviews/{id}/answer` | Submit answer & dynamic follow-up | `{ question_id, transcript, speaking_duration?, audio_filename? }` |
| `POST` | `/api/interviews/{id}/vision-frame` | Webcam frame & posture evaluation | `{ question_id?, image_base64 }` |
| `POST` | `/api/interviews/{id}/complete` | Complete interview session | None |

---

## 4. Multi-Modal Scoring, Reports & Intelligence (`/api`)

| Method | Endpoint | Description | Payload |
|---|---|---|---|
| `POST` | `/api/interviews/{id}/generate-report` | Generate and persist complete report & roadmap | None |
| `GET` | `/api/interviews/{id}/report` | Retrieve full multi-modal performance report | None |
| `GET` | `/api/interviews/{id}/score` | Retrieve mathematical score matrix & weights | None |
| `GET` | `/api/interviews/{id}/roadmap` | Retrieve 5-phase personalized roadmap | None |
| `GET` | `/api/progress` | Longitudinal progress trends & category deltas | None |
| `GET` | `/api/interviews/compare` | Compare 2 sessions (`?first_id=X&second_id=Y`) | Query Parameters |
