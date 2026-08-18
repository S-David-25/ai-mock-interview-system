from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import RESUME_UPLOAD_DIR, JD_UPLOAD_DIR, MAX_FILE_SIZE_BYTES
from app.database.session import DatabaseSession
from app.models.interview import Interview
from app.services.interview_service import InterviewService
from app.utils.file_helpers import (
    validate_file_extension,
    validate_file_size,
    generate_secure_filename,
    extract_text_from_file,
)

class FileService:
    @staticmethod
    async def process_and_save_file(
        upload_file: UploadFile,
        target_dir: Path
    ) -> Tuple[str, str, str, int]:
        """
        Validates file, writes safely to disk, and extracts plain text.
        Returns: (secure_filename, sanitized_original_name, extracted_text, word_count)
        """
        filename = upload_file.filename or "uploaded_document"
        if not validate_file_extension(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Only PDF (.pdf) and Word documents (.docx) are supported."
            )

        content = await upload_file.read()
        file_size = len(content)

        if not validate_file_size(file_size):
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed size of {max_mb} MB or is empty."
            )

        secure_name, original_name = generate_secure_filename(filename)
        dest_path = target_dir / secure_name

        try:
            with open(dest_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to securely save file to storage: {str(e)}"
            )

        # Extract text
        try:
            extracted_text, word_count = extract_text_from_file(dest_path)
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error extracting text from document: {str(e)}"
            )

        if word_count == 0:
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded document appears to be empty or unreadable text."
            )

        return secure_name, original_name, extracted_text, word_count

    @staticmethod
    async def upload_resume(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        file: UploadFile
    ) -> Tuple[Interview, int]:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        secure_name, original_name, text, word_count = await FileService.process_and_save_file(
            file, RESUME_UPLOAD_DIR
        )

        db.execute(
            """
            UPDATE interviews
            SET resume_filename = ?,
                resume_original_name = ?,
                resume_text = ?,
                updated_at = datetime('now', 'utc')
            WHERE id = ?
            """,
            (secure_name, original_name, text, interview.id)
        )
        db.commit()

        updated_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        InterviewService.evaluate_and_update_status(db, updated_interview)
        refreshed_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        return refreshed_interview, word_count

    @staticmethod
    async def upload_jd(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        file: UploadFile
    ) -> Tuple[Interview, int]:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        if interview.interview_type != "company":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description upload is only applicable for Company-specific interviews."
            )

        secure_name, original_name, text, word_count = await FileService.process_and_save_file(
            file, JD_UPLOAD_DIR
        )

        db.execute(
            """
            UPDATE interviews
            SET jd_filename = ?,
                jd_original_name = ?,
                jd_text = ?,
                updated_at = datetime('now', 'utc')
            WHERE id = ?
            """,
            (secure_name, original_name, text, interview.id)
        )
        db.commit()

        updated_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        InterviewService.evaluate_and_update_status(db, updated_interview)
        refreshed_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        return refreshed_interview, word_count

    @staticmethod
    async def submit_jd_text(
        db: DatabaseSession,
        interview_id: int,
        user_id: int,
        jd_text: str,
        original_name: str = "pasted"
    ) -> Interview:
        interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        if interview.interview_type != "company":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description submission is only applicable for Company-specific interviews."
            )

        # Persist jd_text
        db.execute(
            """
            UPDATE interviews
            SET jd_original_name = ?,
                jd_text = ?,
                updated_at = datetime('now', 'utc')
            WHERE id = ?
            """,
            (original_name, jd_text, interview.id)
        )
        db.commit()

        updated_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        InterviewService.evaluate_and_update_status(db, updated_interview)
        refreshed_interview = InterviewService.get_interview_by_id(db, interview_id, user_id)
        return refreshed_interview
