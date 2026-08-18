from app.database.session import get_connection


def ensure_column_exists(conn, table_name: str, column_name: str, column_definition: str):
    """Safely add a missing column to an existing SQLite table without dropping data."""
    try:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
    except Exception:
        # The table may not exist yet; caller can create it before migration runs.
        pass


def init_db():
    """Initializes SQLite database tables and schema indexes."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. User table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
    );
    """)

    # 2. Interview table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        interview_type TEXT NOT NULL CHECK(interview_type IN ('company', 'general')),
        company_name TEXT,
        job_role TEXT,
        jd_filename TEXT,
        jd_original_name TEXT,
        jd_text TEXT,
        resume_filename TEXT,
        resume_original_name TEXT,
        resume_text TEXT,
        resume_analysis_json TEXT,
        jd_analysis_json TEXT,
        skill_match_json TEXT,
        ats_analysis_json TEXT,
        status TEXT NOT NULL DEFAULT 'setup' CHECK(status IN ('setup', 'processing', 'ready', 'in_progress', 'completed', 'failed')),
        overall_score REAL,
        technical_score REAL,
        communication_score REAL,
        facial_score REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Safe migration for older SQLite databases that were created before ats_analysis_json existed.
    ensure_column_exists(conn, "interviews", "ats_analysis_json", "TEXT")

    # 3. InterviewQuestion table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        question_category TEXT NOT NULL DEFAULT 'TECHNICAL',
        difficulty TEXT NOT NULL DEFAULT 'MEDIUM',
        expected_focus_json TEXT,
        source TEXT NOT NULL DEFAULT 'GENERAL',
        order_num INTEGER NOT NULL DEFAULT 1,
        parent_question_id INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_question_id) REFERENCES interview_questions(id) ON DELETE SET NULL
    );
    """)

    # 4. InterviewAnswer table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        transcript_text TEXT,
        audio_filename TEXT,
        duration_seconds REAL DEFAULT 0.0,
        word_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE
    );
    """)

    # 5. AnswerAnalysis table (NLP & Technical Evaluation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS answer_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        answer_id INTEGER NOT NULL,
        technical_score REAL DEFAULT 0.0,
        correctness REAL DEFAULT 0.0,
        relevance REAL DEFAULT 0.0,
        completeness REAL DEFAULT 0.0,
        depth REAL DEFAULT 0.0,
        technical_feedback TEXT,
        fluency_score REAL DEFAULT 0.0,
        wpm REAL DEFAULT 0.0,
        speaking_duration REAL DEFAULT 0.0,
        filler_word_count INTEGER DEFAULT 0,
        filler_words_json TEXT,
        repeated_words_json TEXT,
        grammar_score REAL DEFAULT 0.0,
        vocabulary_score REAL DEFAULT 0.0,
        clarity_score REAL DEFAULT 0.0,
        communication_score REAL DEFAULT 0.0,
        communication_feedback TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE,
        FOREIGN KEY (answer_id) REFERENCES interview_answers(id) ON DELETE CASCADE
    );
    """)

    # 6. BehaviorAnalysis table (MediaPipe Face & Posture & CNN Emotion)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS behavior_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_id INTEGER,
        answer_id INTEGER,
        face_detected INTEGER DEFAULT 0,
        camera_facing_ratio REAL DEFAULT 0.0,
        eye_contact_proxy_score REAL DEFAULT 0.0,
        posture_score REAL DEFAULT 0.0,
        head_stability_score REAL DEFAULT 0.0,
        dominant_emotion TEXT DEFAULT 'Neutral',
        emotion_probabilities_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE,
        FOREIGN KEY (answer_id) REFERENCES interview_answers(id) ON DELETE CASCADE
    );
    """)

    # 7. InterviewScore table (Master Prompt 3 Multi-modal Weighted Scores)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL UNIQUE,
        overall_score REAL NOT NULL DEFAULT 0.0,
        technical_score REAL NOT NULL DEFAULT 0.0,
        communication_score REAL NOT NULL DEFAULT 0.0,
        fluency_score REAL NOT NULL DEFAULT 0.0,
        eye_contact_score REAL NOT NULL DEFAULT 0.0,
        posture_score REAL NOT NULL DEFAULT 0.0,
        expression_score REAL DEFAULT 0.0,
        confidence_indicator REAL NOT NULL DEFAULT 0.0,
        readiness_level TEXT NOT NULL DEFAULT 'Good',
        weights_json TEXT,
        available_weights_sum REAL DEFAULT 1.0,
        unavailable_modalities_json TEXT,
        contributions_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE
    );
    """)

    # 8. InterviewReport table (Master Prompt 3 Performance Report)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interview_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        overall_score REAL NOT NULL DEFAULT 0.0,
        readiness_level TEXT NOT NULL DEFAULT 'Good',
        summary_text TEXT,
        strengths_json TEXT,
        weaknesses_json TEXT,
        mistakes_json TEXT,
        skill_gaps_json TEXT,
        category_ratings_json TEXT,
        question_breakdowns_json TEXT,
        resume_review_json TEXT,
        jd_match_json TEXT,
        roadmap_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 9. Roadmap table (Master Prompt 3 5-Phase Personalized Milestones)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roadmaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        phases_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_user_id ON interviews(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_interview ON interview_questions(interview_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_answers_interview ON interview_answers(interview_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_interview ON answer_analyses(interview_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON interview_reports(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id);")

    conn.commit()
    conn.close()

def reset_db():
    """Drops all tables and re-initializes schema (for test isolation)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("DROP TABLE IF EXISTS roadmaps;")
    cursor.execute("DROP TABLE IF EXISTS interview_reports;")
    cursor.execute("DROP TABLE IF EXISTS interview_scores;")
    cursor.execute("DROP TABLE IF EXISTS behavior_analyses;")
    cursor.execute("DROP TABLE IF EXISTS answer_analyses;")
    cursor.execute("DROP TABLE IF EXISTS interview_answers;")
    cursor.execute("DROP TABLE IF EXISTS interview_questions;")
    cursor.execute("DROP TABLE IF EXISTS interviews;")
    cursor.execute("DROP TABLE IF EXISTS users;")
    conn.commit()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.close()
    init_db()
