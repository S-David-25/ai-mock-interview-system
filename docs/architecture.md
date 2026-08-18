# AI Mock Interview System – Complete System Architecture (Master Prompts 1, 2 & 3)

## 1. End-to-End System Pipeline

```
                     ┌────────────────────────────────┐
                     │   Candidate Registration/Login │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │       Student Dashboard        │
                     │  (Metrics & Progress Trends)   │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │    Interview Setup & Upload    │
                     │ (Company/Role/JD & Resume PDF) │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │  Document Intelligence Engine  │
                     │  - Resume Profile Extraction   │
                     │  - JD Requirements Extraction  │
                     │  - Alias Normalized Matching   │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │  Question Battery Generator    │
                     │  (Personalized 7 Categories)   │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │   Interactive Voice Session    │
                     │  - TTS Spoken Questions        │
                     │  - MediaRecorder Spoken Answer │
                     │  - Whisper Speech-to-Text      │
                     │  - NLP Multi-Modal Evaluation  │
                     │  - Computer Vision Face Proxy  │
                     │  - Adaptive Dynamic Follow-ups │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │ Weighted Multi-Modal Scoring   │
                     │ (Deterministic 6-D Algorithm   │
                     │  + Missing-Modality Normal.)   │
                     └───────────────┬────────────────┘
                                     │
                                     ▼
                     ┌────────────────────────────────┐
                     │ Comprehensive Placement Report │
                     │  - Overall Score & Readiness   │
                     │  - Strengths & Weaknesses      │
                     │  - Frequently Observed Mistakes│
                     │  - 5-Phase Personalized Roadmap│
                     │  - Progress Trends & Comparison│
                     └────────────────────────────────┘
```

## 2. Decoupled Service Layer Architecture

- `backend/app/services/`:
  - `scoring_service.py`: Weighted Multi-Modal Interview Scoring Algorithm.
  - `report_service.py`: Performance report generator & mistake detector.
  - `roadmap_service.py`: 5-Phase personalized improvement roadmap synthesizer.
  - `progress_service.py`: Longitudinal progress tracking and comparison engine.
  - `gemini_service.py`: Centralized Google GenAI SDK wrapper with schema validation.
  - `resume_service.py`: Resume entity & competency extractor.
  - `jd_service.py`: Job description requirement extractor.
  - `matching_service.py`: Deterministic skill normalization and gap analyzer.
  - `question_service.py`: Question battery & adaptive follow-up generator.
  - `transcription_service.py`: Audio storage & Whisper speech-to-text pipeline.
  - `fluency_service.py`: Speech tempo (WPM) and filler word analytics.
  - `communication_service.py`: Grammar, vocabulary, and articulation analyzer.
  - `answer_evaluation_service.py`: Technical conceptual depth evaluator.
  - `vision_service.py`: OpenCV face tracking, eye-contact proxy, and posture evaluator.
  - `emotion_service.py`: FER2013 7-class CNN facial expression interface.
