# app/utils/file_utils.py
import os
import uuid
from typing import List, Optional

def get_allowed_file_extensions() -> List[str]:
    """Get list of allowed file extensions"""
    return ["png", "jpg", "jpeg", "svg"]

def allowed_file(filename: str, allowed_extensions: Optional[List[str]] = None) -> bool:
    """Check if a file has an allowed extension"""
    if allowed_extensions is None:
        allowed_extensions = get_allowed_file_extensions()
    
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

def generate_unique_filename(filename: str) -> str:
    """Generate a unique filename preserving the original extension"""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    new_filename = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}"
    return new_filename

def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    return os.path.getsize(file_path)