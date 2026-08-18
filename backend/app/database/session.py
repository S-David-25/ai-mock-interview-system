import sqlite3
import threading
from typing import Generator
from app.config import DATABASE_PATH

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection."""
    conn = sqlite3.connect(
        str(DATABASE_PATH),
        check_same_thread=False,
        timeout=30.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

class DatabaseSession:
    """
    Lightweight, robust Database Session wrapper providing ORM-style operations
    over SQLite for high speed and zero external dependencies.
    """
    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or get_connection()
        self._is_managed = conn is None

    def execute(self, query: str, params: tuple = ()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor

    def fetchone(self, query: str, params: tuple = ()):
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()):
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        if self._is_managed and self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

def get_db() -> Generator[DatabaseSession, None, None]:
    """FastAPI Dependency for database session."""
    session = DatabaseSession()
    try:
        yield session
    finally:
        session.close()
