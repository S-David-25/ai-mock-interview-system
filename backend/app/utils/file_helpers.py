import re
import uuid
from pathlib import Path
from typing import Tuple
import pypdf
import docx
from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES

def sanitize_filename(filename: str) -> str:
    """Removes path separators and invalid characters from filename."""
    # Normalize both forward and backward slashes
    clean_name = filename.replace("\\", "/").split("/")[-1]
    # Remove any leading dots and replace dangerous characters
    clean_name = re.sub(r'^\.+', '', clean_name)
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_name)
    # Remove any double dots
    clean_name = re.sub(r'\.{2,}', '.', clean_name)
    if not clean_name:
        clean_name = "unnamed_document"
    return clean_name

def generate_secure_filename(original_filename: str) -> Tuple[str, str]:
    """
    Generates a unique stored filename while preserving the sanitized original name and extension.
    Returns: (secure_unique_filename, sanitized_original_name)
    """
    sanitized = sanitize_filename(original_filename)
    unique_prefix = uuid.uuid4().hex[:12]
    secure_name = f"{unique_prefix}_{sanitized}"
    return secure_name, sanitized

def validate_file_extension(filename: str) -> bool:
    """Checks if the file has an approved extension (.pdf, .docx)."""
    clean = sanitize_filename(filename)
    ext = Path(clean).suffix.lower()
    return ext in ALLOWED_EXTENSIONS

def validate_file_size(size_in_bytes: int) -> bool:
    """Checks if file size is within limits."""
    return 0 < size_in_bytes <= MAX_FILE_SIZE_BYTES

def extract_text_from_file(file_path: Path) -> Tuple[str, int]:
    """
    Extracts plain text from PDF or DOCX file.
    Returns: (extracted_text, word_count)
    """
    ext = file_path.suffix.lower()
    text = ""

    if ext == ".pdf":
        try:
            reader = pypdf.PdfReader(str(file_path))
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            text = "\n".join(pages_text).strip()
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

    elif ext == ".docx":
        try:
            doc = docx.Document(str(file_path))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paras).strip()
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    word_count = len(text.split()) if text else 0
    return text, word_count
