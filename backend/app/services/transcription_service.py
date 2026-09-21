import os
import uuid
import wave
import logging
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from app.config import AUDIO_UPLOAD_DIR, ALLOWED_AUDIO_EXTENSIONS, WHISPER_MODEL
from app.schemas.interview import TranscriptionResponse

logger = logging.getLogger("transcription_service")

# Attempt Whisper import
_whisper_model = None
_whisper_available = False
try:
    import whisper
    # Default to base or tiny model if available
    _whisper_available = True
    logger.info("OpenAI Whisper package is available.")
except Exception as e:
    logger.info(f"OpenAI Whisper package not loaded: {e}. Audio ingestion will operate with graceful audio metadata extraction.")

class TranscriptionService:
    """
    Speech-to-Text transcription service wrapping Whisper with robust file validation,
    duration estimation, word counting, and offline error resilience.
    """

    @staticmethod
    async def save_and_transcribe_audio(
        upload_file: UploadFile,
        fallback_text: str = "",
        question_context: str = ""
    ) -> TranscriptionResponse:
        filename = upload_file.filename or "recording.webm"
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ".webm"

        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format '{ext}'. Supported formats: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
            )

        content = await upload_file.read()
        file_size = len(content)
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Received empty audio recording (0 bytes)."
            )

        unique_id = uuid.uuid4().hex[:12]
        secure_filename = f"{unique_id}_audio{ext}"
        dest_path = AUDIO_UPLOAD_DIR / secure_filename

        try:
            with open(dest_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save audio file to disk: {str(e)}"
            )

        # Estimate duration from WAV headers or file size ratio
        duration_seconds = TranscriptionService._estimate_duration(dest_path, ext, file_size)
        logger.info("Audio received: format=%s bytes=%d estimated_duration=%.2fs", ext, file_size, duration_seconds)

        # Transcribe
        transcript = ""
        transcription_error = None
        if _whisper_available:
            try:
                global _whisper_model
                if _whisper_model is None:
                    import whisper
                    _whisper_model = whisper.load_model(WHISPER_MODEL)
                vocabulary = "Python, Java, JavaScript, TypeScript, C++, C#, SQL, PostgreSQL, MongoDB, React, Node.js, FastAPI, Spring Boot, REST API, HTTP, JSON, Docker, Kubernetes, AWS, Azure, Redis, GraphQL, JWT, OAuth, OOP, DSA, algorithm, recursion, dynamic programming, binary search, hashing, palindrome, polynomial, concurrency, asynchronous."
                initial_prompt = f"Technical interview vocabulary: {vocabulary}"
                if question_context:
                    initial_prompt += f" Interview question context: {question_context[:500]}"
                logger.info("Whisper transcription started: model=%s language=en", WHISPER_MODEL)
                res = _whisper_model.transcribe(
                    str(dest_path),
                    language="en",
                    task="transcribe",
                    initial_prompt=initial_prompt,
                    temperature=0,
                    condition_on_previous_text=False,
                    fp16=False,
                )
                transcript = res.get("text", "").strip()
                logger.info("Whisper transcription completed: words=%d", len(transcript.split()))
            except Exception as e:
                transcription_error = f"Whisper transcription failed: {e}"
                logger.exception(transcription_error)
        else:
            transcription_error = "Whisper is unavailable in the backend runtime."

        if not transcript:
            # Keep failed audio explicit; caller-supplied text is never treated as audio transcription.
            transcription_error = transcription_error or "Whisper produced no usable transcript."

        word_count = len(transcript.split()) if transcript else 0

        return TranscriptionResponse(
            transcript=transcript,
            duration_seconds=duration_seconds,
            word_count=word_count,
            audio_filename=secure_filename,
            transcription_status="completed" if transcript else "failed",
            transcription_error=None if transcript else transcription_error
        )

    @staticmethod
    def _estimate_duration(file_path: Path, ext: str, size_bytes: int) -> float:
        if ext == ".wav":
            try:
                with wave.open(str(file_path), 'rb') as w:
                    frames = w.getnframes()
                    rate = w.getframerate()
                    if rate > 0:
                        return round(frames / float(rate), 2)
            except Exception:
                pass
        # Approximate byte-rate for compressed webm/mp3 voice (~32 kbps = 4000 bytes/sec)
        estimated = round(size_bytes / 4000.0, 1)
        return max(1.0, min(estimated, 300.0))
