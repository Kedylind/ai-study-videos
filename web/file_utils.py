"""Utilities for extracting text from uploaded files and converting to paper.json format."""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime

import PyPDF2

logger = logging.getLogger(__name__)

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.txt'}


class FileExtractionError(Exception):
    """Raised when file extraction fails."""
    pass


def validate_uploaded_file(file_path: Path) -> Tuple[bool, str]:
    """
    Validate uploaded file.

    Args:
        file_path: Path to the uploaded file

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file exists
    if not file_path.exists():
        return False, "File not found"

    # Check file size
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return False, f"File is too large (max {MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"

    if file_size == 0:
        return False, "File is empty"

    # Check file extension
    extension = file_path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type. Supported: {', '.join(ALLOWED_EXTENSIONS)}"

    return True, ""


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text content

    Raises:
        FileExtractionError: If extraction fails
    """
    try:
        text_content = []

        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            if len(pdf_reader.pages) == 0:
                raise FileExtractionError("PDF has no pages")

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue

        if not text_content:
            raise FileExtractionError("No text could be extracted from PDF")

        return "\n".join(text_content)

    except FileExtractionError:
        raise
    except Exception as e:
        raise FileExtractionError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_file(file_path: Path) -> str:
    """
    Extract text from an uploaded file.

    Args:
        file_path: Path to the file

    Returns:
        Extracted text content

    Raises:
        FileExtractionError: If extraction fails
    """
    extension = file_path.suffix.lower()

    if extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif extension == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise FileExtractionError(f"Failed to read text file: {str(e)}")
    else:
        raise FileExtractionError(f"Unsupported file type: {extension}")


def create_paper_json(text_content: str, filename: str, output_path: Path) -> Dict:
    """
    Convert extracted text to paper.json format (matches PubMed structure).

    Args:
        text_content: Extracted text from the file
        filename: Original filename (used for title)
        output_path: Path to save the paper.json file

    Returns:
        Dictionary containing paper metadata
    """
    # Create basic paper structure
    paper_data = {
        "title": filename.replace('_', ' ').replace('-', ' '),
        "abstract": text_content[:500] if text_content else "",  # First 500 chars as abstract
        "full_text": text_content,
        "authors": ["Unknown"],
        "publication_date": datetime.now().isoformat(),
        "source": "local_file",
        "filename": filename,
    }

    # Save to paper.json
    json_path = output_path / "paper.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(paper_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Created paper.json at {json_path}")
    return paper_data


def process_uploaded_file(file_path: Path, output_dir: Path) -> Tuple[bool, str, Dict]:
    """
    Process an uploaded file: validate, extract text, and create paper.json.

    Args:
        file_path: Path to the uploaded file
        output_dir: Directory to save paper.json

    Returns:
        Tuple of (success, error_message, paper_data)
    """
    # Validate file
    is_valid, error_msg = validate_uploaded_file(file_path)
    if not is_valid:
        return False, error_msg, {}

    try:
        # Extract text
        text_content = extract_text_from_file(file_path)

        # Create paper.json
        paper_data = create_paper_json(text_content, file_path.stem, output_dir)

        logger.info(f"Successfully processed uploaded file: {file_path.name}")
        return True, "", paper_data

    except FileExtractionError as e:
        error_msg = f"File processing error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}
    except Exception as e:
        error_msg = f"Unexpected error processing file: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}
