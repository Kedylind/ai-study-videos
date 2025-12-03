"""PDF extraction utilities for uploaded papers."""

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


def validate_pdf(pdf_file_path: Path) -> tuple[bool, str]:
    """
    Validate that a file is a valid PDF.
    
    Args:
        pdf_file_path: Path to the PDF file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file exists
    if not pdf_file_path.exists():
        return False, "File does not exist"
    
    # Check file size
    file_size = pdf_file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        return False, f"File size ({size_mb:.1f}MB) exceeds maximum allowed size (50MB)"
    
    if file_size == 0:
        return False, "File is empty"
    
    # Try to open with pdfplumber to validate structure
    try:
        with pdfplumber.open(pdf_file_path) as pdf:
            if len(pdf.pages) == 0:
                return False, "PDF has no pages"
    except Exception as e:
        return False, f"Invalid PDF file: {str(e)}"
    
    return True, ""


def extract_text(pdf_file_path: Path) -> str:
    """
    Extract full text from all pages of a PDF.
    
    Args:
        pdf_file_path: Path to the PDF file
        
    Returns:
        Full text content as a single string
    """
    full_text = []
    
    try:
        num_pages = 0
        with pdfplumber.open(pdf_file_path) as pdf:
            num_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text()
                    if text:
                        full_text.append(text.strip())
                        logger.debug(f"Extracted {len(text)} characters from page {page_num}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue
        
        combined_text = "\n\n".join(full_text)
        logger.info(f"Extracted {len(combined_text)} total characters from {num_pages} pages")
        return combined_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}", exc_info=True)
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_title(pdf_pages: list, filename: str) -> str:
    """
    Extract paper title from PDF.
    
    Strategy:
    1. Look for text in top 30% of first page (title is usually at top)
    2. Find first significant text line (not too short, reasonable length)
    3. Fallback to filename (without extension)
    
    Args:
        pdf_pages: List of pdfplumber Page objects
        filename: Original filename (for fallback)
        
    Returns:
        Extracted title string
    """
    if not pdf_pages:
        # Fallback to filename
        return Path(filename).stem.replace("_", " ").replace("-", " ")
    
    try:
        first_page = pdf_pages[0]
        page_height = first_page.height
        
        # Get all words from the page
        words = first_page.extract_words()
        if not words:
            return Path(filename).stem.replace("_", " ").replace("-", " ")
        
        # Look for text in top 30% of page (title is usually at the top)
        # In PDF coordinates, top increases downward, so top 30% means top < page_height * 0.3
        top_words = [w for w in words if w['top'] < page_height * 0.3]
        
        if not top_words:
            # If no words in top 30%, try top 50%
            top_words = [w for w in words if w['top'] < page_height * 0.5]
        
        if top_words:
            # Group words by approximate y-position (same line)
            # Sort by y-position (top to bottom) to get lines in order
            lines = {}
            for word in top_words:
                y = round(word['top'], 1)  # Round to group nearby words on same line
                if y not in lines:
                    lines[y] = []
                lines[y].append((word['x0'], word['text']))  # Store x-position for sorting
            
            # Sort lines by y-position (top to bottom)
            sorted_lines = sorted(lines.items(), key=lambda x: x[0])
            
            # Find first significant line that looks like a title
            # Title should be: not too short (at least 5 words), not too long (max 30 words)
            for y_pos, line_words in sorted_lines:
                # Sort words by x-position (left to right) to reconstruct line
                line_words_sorted = sorted(line_words, key=lambda x: x[0])
                line_text = " ".join([w[1] for w in line_words_sorted])
                line_text = re.sub(r'\s+', ' ', line_text).strip()
                
                # Check if this looks like a title
                word_count = len(line_text.split())
                if 5 <= word_count <= 30 and 20 <= len(line_text) <= 200:
                    # This looks like a title
                    return line_text
            
            # If no perfect match, take the first line that's not too short
            for y_pos, line_words in sorted_lines:
                line_words_sorted = sorted(line_words, key=lambda x: x[0])
                line_text = " ".join([w[1] for w in line_words_sorted])
                line_text = re.sub(r'\s+', ' ', line_text).strip()
                
                if len(line_text) >= 10:  # At least 10 characters
                    return line_text
        
        # If still no title found, try extracting first few lines from top of page text
        first_page_text = first_page.extract_text()
        if first_page_text:
            lines = first_page_text.split('\n')
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if len(line) >= 10 and 5 <= len(line.split()) <= 30:
                    return line
        
    except Exception as e:
        logger.warning(f"Failed to extract title from PDF: {e}")
    
    # Fallback to filename
    return Path(filename).stem.replace("_", " ").replace("-", " ")


def extract_authors(pdf_pages: list, full_text: str) -> list:
    """
    Extract author names from PDF.
    
    Strategy:
    1. Look for common author patterns in first page
    2. Look for "Author:", "By:", etc.
    3. Return empty list if not found
    
    Args:
        pdf_pages: List of pdfplumber Page objects
        full_text: Full extracted text
        
    Returns:
        List of author name strings
    """
    authors = []
    
    if not pdf_pages:
        return authors
    
    try:
        # Get first page text
        first_page_text = ""
        if pdf_pages:
            first_page_text = pdf_pages[0].extract_text() or ""
        
        # Look for common author patterns
        author_patterns = [
            r'(?:Authors?|By|Written by)[:\s]+([^\n]+)',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+et\s+al\.)?)',
        ]
        
        # Check first 2000 characters of first page
        search_text = first_page_text[:2000] if first_page_text else full_text[:2000]
        
        for pattern in author_patterns:
            matches = re.findall(pattern, search_text, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Take first match and split by common delimiters
                author_line = matches[0].strip()
                # Split by comma, semicolon, or "and"
                author_list = re.split(r'[,;]|\s+and\s+', author_line)
                authors = [a.strip() for a in author_list if a.strip()]
                if authors:
                    break
        
        # Limit to reasonable number of authors
        if len(authors) > 10:
            authors = authors[:10]
            authors.append("et al.")
            
    except Exception as e:
        logger.warning(f"Failed to extract authors from PDF: {e}")
    
    return authors


def generate_paper_id(filename: str, use_hash: bool = False) -> str:
    """
    Generate a unique paper ID.
    
    Args:
        filename: Original filename
        use_hash: If True, use content hash (deterministic). If False, use UUID (unique).
        
    Returns:
        Unique paper ID string
    """
    if use_hash:
        # Generate hash from filename (deterministic)
        # Note: For true content hash, would need to hash file content
        content = filename.encode('utf-8')
        hash_obj = hashlib.sha256(content)
        return f"UPLOAD_{hash_obj.hexdigest()[:16].upper()}"
    else:
        # Generate UUID (unique every time)
        return f"UPLOAD_{uuid.uuid4().hex[:16].upper()}"


def extract_pdf_content(pdf_file_path: Path, filename: Optional[str] = None) -> dict:
    """
    Extract text and metadata from PDF and return paper.json structure.
    
    Args:
        pdf_file_path: Path to the PDF file
        filename: Original filename (for fallback title)
        
    Returns:
        Dictionary matching paper.json structure:
        {
            "pmid": "...",
            "pmcid": None,
            "title": "...",
            "full_text": "...",
            "figures": []
        }
        
    Raises:
        ValueError: If PDF extraction fails
    """
    if filename is None:
        filename = pdf_file_path.name
    
    # Validate PDF first
    is_valid, error_msg = validate_pdf(pdf_file_path)
    if not is_valid:
        raise ValueError(error_msg)
    
    logger.info(f"Extracting content from PDF: {pdf_file_path}")
    
    # Extract full text
    full_text = extract_text(pdf_file_path)
    if not full_text or len(full_text.strip()) < 100:
        raise ValueError("PDF appears to be empty or contains too little text (< 100 characters)")
    
    # Open PDF again for metadata extraction
    with pdfplumber.open(pdf_file_path) as pdf:
        pages = pdf.pages
        
        # Extract title
        title = extract_title(pages, filename)
        
        # Extract authors
        authors = extract_authors(pages, full_text)
    
    # Generate unique paper ID
    paper_id = generate_paper_id(filename, use_hash=False)
    
    # Build paper.json structure
    paper_data = {
        "pmid": paper_id,
        "pmcid": None,  # Not available for uploaded files
        "title": title,
        "full_text": full_text.strip(),
        "figures": [],  # Skip figure extraction for MVP
    }
    
    # Add authors if found (not in standard structure, but useful)
    if authors:
        paper_data["authors"] = authors
    
    logger.info(f"Successfully extracted PDF content: title='{title[:50]}...', text_length={len(full_text)}")
    
    return paper_data

