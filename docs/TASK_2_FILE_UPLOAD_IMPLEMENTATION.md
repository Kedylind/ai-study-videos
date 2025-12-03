# Task 2: Complete File Upload Feature - Detailed Implementation Plan

**Feature:** File Upload Processing for PDF Documents  
**Priority:** 🎯 Sprint 1 Core Feature (12 Story Points)  
**Estimated Effort:** 3-4 hours  
**Status:** Ready for Implementation

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Current State Analysis](#current-state-analysis)
3. [Requirements](#requirements)
4. [Architecture Design](#architecture-design)
5. [Detailed Implementation Steps](#detailed-implementation-steps)
6. [Code Implementation](#code-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Error Handling](#error-handling)
9. [Edge Cases](#edge-cases)
10. [File Structure Changes](#file-structure-changes)

---

## Overview

### Feature Description
Allow users to upload PDF files directly instead of requiring a PubMed ID. The system should extract text and metadata from the PDF, convert it to the `paper.json` format that the pipeline expects, and then proceed with video generation.

### User Story
> "As a user, I can upload a PDF or provide a URL so that the system can extract key sections."

### Success Criteria
- ✅ Users can upload PDF files through the web interface
- ✅ PDF text is extracted correctly
- ✅ Metadata (title, authors) is extracted when available
- ✅ `paper.json` is created with correct structure matching PubMed format
- ✅ Pipeline skips `fetch-paper` step when `paper.json` already exists
- ✅ Video generation works identically for uploaded files and PubMed papers
- ✅ File validation prevents invalid uploads
- ✅ User-friendly error messages for all failure cases

---

## Current State Analysis

### What Works
- ✅ Upload form exists at `/upload/` (`web/templates/upload.html`)
- ✅ `PaperUploadForm` accepts file uploads (`web/forms.py`)
- ✅ File is saved to `media/<filename_stem>/uploaded_file` (`web/views.py:1207-1215`)
- ✅ Pipeline infrastructure is ready

### Current Blocker
**Location:** `web/views.py:1217-1219`

```python
# TODO: support pipeline from local file; for now, return to status page
# We'll treat 'name' as an identifier
pmid = name
```

**Problem:**
- Filename stem (e.g., `kahneman-deaton-2010...`) is used as paper ID
- Pipeline tries to fetch from PubMed using filename as PMID/PMCID
- Fails immediately: `PMID [filename] is not available in PubMed Central`

### Pipeline Flow Understanding

**Current Flow (PubMed):**
1. User enters PMID/PMCID
2. `_start_pipeline_async()` called with PMID
3. `generate_video_task()` runs pipeline command: `python main.py generate-video <pmid> <output_dir>`
4. Pipeline's `orchestrate_pipeline()` calls `fetch_paper()` which:
   - Downloads XML from PubMed Central
   - Parses XML to extract content
   - Creates `paper.json` in output directory
5. Subsequent steps use `paper.json`

**Required Flow (File Upload):**
1. User uploads PDF file
2. Extract text and metadata from PDF
3. Create `paper.json` directly (skip PubMed fetch)
4. Generate unique paper ID (UUID or hash)
5. Call pipeline with paper ID
6. Pipeline detects `paper.json` exists → skips `fetch-paper` step
7. Continue with script generation and rest of pipeline

---

## Requirements

### Functional Requirements

1. **PDF Text Extraction**
   - Extract full text content from all pages
   - Preserve paragraph structure where possible
   - Handle multi-column layouts
   - Support encrypted/password-protected PDFs (show error)

2. **Metadata Extraction**
   - Extract title (from first page, typically largest text)
   - Extract authors (look for common patterns)
   - Extract abstract if identifiable
   - Generate unique paper ID

3. **File Validation**
   - Validate file type (PDF only for MVP)
   - Enforce size limits (50MB max recommended)
   - Validate PDF structure (not corrupted)
   - Check if file is actually a PDF (not renamed file)

4. **Paper.json Format**
   - Match exact structure from `pipeline/pubmed.py:parse_pmc_xml()`
   - Required fields: `pmid`, `pmcid`, `title`, `full_text`, `figures`
   - For uploads: `pmcid` can be `None`, `pmid` is generated ID

5. **Pipeline Integration**
   - Detect if `paper.json` exists before `fetch-paper` step
   - Skip `fetch-paper` if `paper.json` exists
   - Continue with remaining pipeline steps normally

### Non-Functional Requirements

1. **Performance**
   - PDF extraction should complete in < 30 seconds for typical papers
   - Handle large PDFs (up to 50MB) efficiently

2. **Error Handling**
   - Clear error messages for all failure cases
   - Log errors for debugging
   - Don't expose internal errors to users

3. **Security**
   - Validate file types to prevent malicious uploads
   - Sanitize extracted text
   - Limit file size to prevent DoS

---

## Architecture Design

### Component Overview

```
┌─────────────────┐
│  Upload Form    │
│  (web/forms.py) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  upload_paper() │
│  (web/views.py)  │
└────────┬────────┘
         │
         ├──► Validate File
         │    (size, type, structure)
         │
         ├──► Extract PDF Content
         │    (web/pdf_extractor.py)
         │
         ├──► Create paper.json
         │    (in output directory)
         │
         └──► Start Pipeline
              (_start_pipeline_async)
                    │
                    ▼
         ┌──────────────────┐
         │ generate_video_   │
         │ task()            │
         │ (web/tasks.py)    │
         └────────┬──────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ orchestrate_     │
         │ pipeline()       │
         │ (pipeline/       │
         │  pipeline.py)    │
         └────────┬─────────┘
                  │
                  ├──► Check paper.json exists
                  │    If YES: Skip fetch-paper
                  │    If NO:  Run fetch-paper
                  │
                  └──► Continue with remaining steps
```

### Data Flow

1. **File Upload** → Saved temporarily to `media/<paper_id>/uploaded_file.pdf`
2. **PDF Extraction** → Text and metadata extracted
3. **Paper.json Creation** → Saved to `media/<paper_id>/paper.json`
4. **Pipeline Start** → Pipeline detects existing `paper.json` and skips fetch

### Key Design Decisions

1. **PDF Library Choice: `pdfplumber`**
   - Better text extraction than PyPDF2
   - Handles complex layouts better
   - More active maintenance
   - Good metadata extraction support

2. **Paper ID Generation: UUID v4**
   - Ensures uniqueness
   - No collisions
   - URL-safe
   - Alternative: SHA-256 hash of file content (deterministic)

3. **Metadata Extraction: Rule-based (MVP)**
   - Simple regex patterns for title/authors
   - Can be enhanced with AI later
   - Fast and reliable for MVP

4. **File Storage: Temporary**
   - Keep uploaded file for debugging
   - Can be cleaned up later
   - Not required for pipeline (only paper.json needed)

---

## Detailed Implementation Steps

### Step 1: Add PDF Parsing Library

**File:** `requirements.txt`

**Action:** Add pdfplumber dependency

```python
# Add after line 18 (after requests)
pdfplumber==0.10.3
```

**Why:** pdfplumber provides better text extraction and layout handling than PyPDF2.

---

### Step 2: Create PDF Extractor Module

**File:** `web/pdf_extractor.py` (NEW FILE)

**Purpose:** Extract text and metadata from PDF files

**Functions to Implement:**

1. `extract_pdf_content(pdf_file_path: Path) -> dict`
   - Main extraction function
   - Returns paper.json structure

2. `extract_text(pdf_file_path: Path) -> str`
   - Extract full text from all pages
   - Handle page breaks

3. `extract_title(pdf_pages: list) -> str`
   - Extract title from first page
   - Look for largest text block
   - Fallback to filename if not found

4. `extract_authors(pdf_pages: list, full_text: str) -> list`
   - Extract author names
   - Look for common patterns (e.g., "Author:", "By:", etc.)
   - Return list of author strings

5. `generate_paper_id(filename: str, content_hash: str = None) -> str`
   - Generate unique paper ID
   - Use UUID v4 or content hash

6. `validate_pdf(pdf_file_path: Path) -> tuple[bool, str]`
   - Validate PDF structure
   - Check if file is actually a PDF
   - Return (is_valid, error_message)

**See Code Implementation section for full code.**

---

### Step 3: Update Upload View

**File:** `web/views.py`

**Function:** `upload_paper()` (lines 1187-1248)

**Changes Required:**

1. **Add PDF extraction logic** when file is uploaded
2. **Generate unique paper ID** instead of using filename
3. **Create paper.json** in output directory
4. **Handle extraction errors** gracefully
5. **Add file validation** before extraction

**Key Changes:**

```python
# Replace lines 1207-1219 with:
if uploaded:
    # Validate file
    is_valid, error_msg = validate_uploaded_file(uploaded)
    if not is_valid:
        form.add_error("file", error_msg)
        return render(request, "upload.html", {"form": form})
    
    # Generate unique paper ID
    paper_id = generate_unique_paper_id(uploaded.name)
    
    # Save uploaded file
    out_dir = Path(settings.MEDIA_ROOT) / paper_id
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / uploaded.name
    with open(file_path, "wb") as f:
        for chunk in uploaded.chunks():
            f.write(chunk)
    
    # Extract PDF content and create paper.json
    try:
        from web.pdf_extractor import extract_pdf_content
        
        paper_data = extract_pdf_content(file_path)
        paper_json_path = out_dir / "paper.json"
        with open(paper_json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(paper_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Extracted PDF content and created paper.json for {paper_id}")
        pmid = paper_id  # Use generated ID
        
    except Exception as e:
        logger.error(f"Failed to extract PDF content: {e}", exc_info=True)
        form.add_error("file", f"Failed to extract content from PDF: {str(e)}")
        return render(request, "upload.html", {"form": form})
```

**See Code Implementation section for complete updated function.**

---

### Step 4: Update Pipeline to Skip Fetch-Paper

**File:** `pipeline/pipeline.py`

**Function:** `orchestrate_pipeline()` (lines 67-237)

**Change Required:** Check if `paper.json` exists before running `fetch-paper` step

**Current Code (lines 93-99):**
```python
steps = [
    PipelineStep(
        name="fetch-paper",
        description=f"Fetching paper {pmid} from PubMed Central",
        check_completion=lambda: check_paper_fetched(output_dir),
        execute=lambda: fetch_paper(pmid, str(output_dir)),
    ),
    # ... more steps
]
```

**Updated Code:**
```python
steps = []

# Only add fetch-paper step if paper.json doesn't exist
if not check_paper_fetched(output_dir):
    steps.append(
        PipelineStep(
            name="fetch-paper",
            description=f"Fetching paper {pmid} from PubMed Central",
            check_completion=lambda: check_paper_fetched(output_dir),
            execute=lambda: fetch_paper(pmid, str(output_dir)),
        )
    )
else:
    logger.info(f"paper.json already exists in {output_dir}, skipping fetch-paper step")

# Add remaining steps
steps.extend([
    PipelineStep(
        name="generate-script",
        # ... rest of steps
    ),
    # ... more steps
])
```

**Alternative Approach (Simpler):**
Modify the `fetch-paper` step to check if `paper.json` exists and skip if it does:

```python
def fetch_paper_if_needed(pmid: str, output_dir: str):
    """Fetch paper only if paper.json doesn't exist."""
    paper_json = Path(output_dir) / "paper.json"
    if paper_json.exists():
        logger.info(f"paper.json already exists, skipping fetch-paper step")
        return
    fetch_paper(pmid, output_dir)

# In steps:
PipelineStep(
    name="fetch-paper",
    description=f"Fetching paper {pmid} from PubMed Central",
    check_completion=lambda: check_paper_fetched(output_dir),
    execute=lambda: fetch_paper_if_needed(pmid, str(output_dir)),
),
```

**Recommendation:** Use the alternative approach (simpler, less code changes).

---

### Step 5: Add File Validation

**File:** `web/views.py` or `web/pdf_extractor.py`

**Function:** `validate_uploaded_file(uploaded_file) -> tuple[bool, str]`

**Validation Checks:**

1. **File Extension**
   - Must be `.pdf` (case-insensitive)
   - Reject other extensions

2. **File Size**
   - Maximum 50MB (configurable)
   - Check `uploaded_file.size`

3. **File Type (MIME)**
   - Check `uploaded_file.content_type`
   - Should be `application/pdf`
   - Note: Django may not always detect correctly

4. **PDF Structure (after saving)**
   - Try to open with pdfplumber
   - If fails, file is corrupted or not a PDF

**See Code Implementation section for complete validation function.**

---

### Step 6: Update Form Validation (Optional)

**File:** `web/forms.py`

**Current:** Basic validation (either paper_id or file required)

**Enhancement:** Add file-specific validation

```python
def clean_file(self):
    file = self.cleaned_data.get("file")
    if file:
        # Check file extension
        if not file.name.lower().endswith('.pdf'):
            raise forms.ValidationError("Only PDF files are supported.")
        
        # Check file size (50MB max)
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if file.size > max_size:
            raise forms.ValidationError(f"File size exceeds 50MB limit. Your file is {file.size / (1024*1024):.1f}MB.")
    
    return file
```

---

## Code Implementation

### Complete PDF Extractor Module

**File:** `web/pdf_extractor.py` (NEW FILE)

```python
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
        with pdfplumber.open(pdf_file_path) as pdf:
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
        logger.info(f"Extracted {len(combined_text)} total characters from {len(pdf.pages)} pages")
        return combined_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}", exc_info=True)
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_title(pdf_pages: list, filename: str) -> str:
    """
    Extract paper title from PDF.
    
    Strategy:
    1. Look for largest text block on first page
    2. Look for text matching common title patterns
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
        
        # Get all text blocks with their sizes
        words = first_page.extract_words()
        if not words:
            return Path(filename).stem.replace("_", " ").replace("-", " ")
        
        # Group words by approximate y-position (same line)
        lines = {}
        for word in words[:50]:  # Check first 50 words
            y = round(word['top'], 1)  # Round to group nearby words
            if y not in lines:
                lines[y] = []
            lines[y].append(word['text'])
        
        # Find the line with most words (likely title)
        if lines:
            largest_line = max(lines.items(), key=lambda x: len(x[1]))
            title = " ".join(largest_line[1])
            
            # Clean up title
            title = re.sub(r'\s+', ' ', title).strip()
            
            # If title is too short or too long, try alternative
            if 10 <= len(title) <= 200:
                return title
        
        # Alternative: Look for text in top 30% of page (title is usually at the top)
        # In PDF coordinates, top increases downward, so top 30% means top < page_height * 0.3
        page_height = first_page.height
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
```

---

### Updated Upload View

**File:** `web/views.py`

**Function:** `upload_paper()` - Replace lines 1207-1219

```python
# Add import at top of file
from web.pdf_extractor import extract_pdf_content, validate_pdf, generate_paper_id

# In upload_paper() function, replace the file upload handling section:
if uploaded:
    # Validate file extension
    if not uploaded.name.lower().endswith('.pdf'):
        form.add_error("file", "Only PDF files are supported.")
        return render(request, "upload.html", {"form": form})
    
    # Validate file size (50MB max)
    max_size = 50 * 1024 * 1024  # 50MB
    if uploaded.size > max_size:
        size_mb = uploaded.size / (1024 * 1024)
        form.add_error("file", f"File size ({size_mb:.1f}MB) exceeds maximum allowed size (50MB)")
        return render(request, "upload.html", {"form": form})
    
    # Generate unique paper ID
    paper_id = generate_paper_id(uploaded.name, use_hash=False)
    
    # Save uploaded file
    out_dir = Path(settings.MEDIA_ROOT) / paper_id
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / uploaded.name
    
    try:
        with open(file_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)
        
        logger.info(f"Saved uploaded file to {file_path}")
        
        # Validate PDF structure
        is_valid, error_msg = validate_pdf(file_path)
        if not is_valid:
            form.add_error("file", error_msg)
            # Clean up saved file
            try:
                file_path.unlink()
                out_dir.rmdir()
            except:
                pass
            return render(request, "upload.html", {"form": form})
        
        # Extract PDF content and create paper.json
        try:
            paper_data = extract_pdf_content(file_path, filename=uploaded.name)
            paper_json_path = out_dir / "paper.json"
            
            import json
            with open(paper_json_path, "w", encoding="utf-8") as f:
                json.dump(paper_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Extracted PDF content and created paper.json for {paper_id}")
            pmid = paper_id  # Use generated ID
            
        except ValueError as e:
            # User-friendly error (validation, extraction issues)
            logger.error(f"PDF extraction failed: {e}")
            form.add_error("file", f"Failed to extract content from PDF: {str(e)}")
            # Clean up
            try:
                file_path.unlink()
                if (out_dir / "paper.json").exists():
                    (out_dir / "paper.json").unlink()
                out_dir.rmdir()
            except:
                pass
            return render(request, "upload.html", {"form": form})
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error during PDF extraction: {e}", exc_info=True)
            form.add_error("file", "An unexpected error occurred while processing the PDF. Please try again or contact support.")
            # Clean up
            try:
                file_path.unlink()
                if (out_dir / "paper.json").exists():
                    (out_dir / "paper.json").unlink()
                out_dir.rmdir()
            except:
                pass
            return render(request, "upload.html", {"form": form})
            
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}", exc_info=True)
        form.add_error("file", f"Failed to save uploaded file: {str(e)}")
        return render(request, "upload.html", {"form": form})
```

---

### Updated Pipeline Function

**File:** `pipeline/pipeline.py`

**Function:** `orchestrate_pipeline()` - Modify fetch-paper step

**Option 1: Skip step entirely (Recommended)**

Add this function before `orchestrate_pipeline()`:

```python
def fetch_paper_if_needed(pmid: str, output_dir: str) -> None:
    """
    Fetch paper from PubMed Central only if paper.json doesn't exist.
    
    This allows the pipeline to work with pre-created paper.json files
    (e.g., from file uploads).
    """
    paper_json = Path(output_dir) / "paper.json"
    if paper_json.exists():
        logger.info(f"paper.json already exists in {output_dir}, skipping fetch-paper step")
        return
    
    # Paper.json doesn't exist, fetch from PubMed
    fetch_paper(pmid, output_dir)
```

Then update the steps list (around line 93):

```python
steps = [
    PipelineStep(
        name="fetch-paper",
        description=f"Fetching paper {pmid} from PubMed Central",
        check_completion=lambda: check_paper_fetched(output_dir),
        execute=lambda: fetch_paper_if_needed(pmid, str(output_dir)),
    ),
    # ... rest of steps unchanged
]
```

**Option 2: Conditional step addition**

Modify the steps list to conditionally add fetch-paper:

```python
steps = []

# Only add fetch-paper step if paper.json doesn't exist
if not check_paper_fetched(output_dir):
    steps.append(
        PipelineStep(
            name="fetch-paper",
            description=f"Fetching paper {pmid} from PubMed Central",
            check_completion=lambda: check_paper_fetched(output_dir),
            execute=lambda: fetch_paper(pmid, str(output_dir)),
        )
    )
else:
    logger.info(f"paper.json already exists in {output_dir}, skipping fetch-paper step")

# Add remaining steps
steps.extend([
    PipelineStep(
        name="generate-script",
        description="Generating video script from paper",
        check_completion=lambda: check_script_generated(output_dir),
        execute=lambda: generate_script_from_paper(str(output_dir)),
    ),
    # ... rest of steps
])
```

**Recommendation:** Use Option 1 (simpler, cleaner).

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_pdf_extractor.py` (NEW FILE)

```python
import pytest
from pathlib import Path
from web.pdf_extractor import (
    extract_pdf_content,
    validate_pdf,
    extract_text,
    extract_title,
    generate_paper_id,
)

def test_extract_pdf_content_valid_pdf(tmp_path):
    """Test extracting content from a valid PDF."""
    # Create a test PDF (would need actual PDF file)
    pdf_path = tmp_path / "test.pdf"
    # ... create test PDF ...
    
    result = extract_pdf_content(pdf_path)
    
    assert "pmid" in result
    assert "title" in result
    assert "full_text" in result
    assert len(result["full_text"]) > 0

def test_validate_pdf_invalid_file(tmp_path):
    """Test validation rejects invalid files."""
    invalid_file = tmp_path / "not_a_pdf.txt"
    invalid_file.write_text("This is not a PDF")
    
    is_valid, error_msg = validate_pdf(invalid_file)
    assert not is_valid
    assert "Invalid PDF" in error_msg

def test_generate_paper_id():
    """Test paper ID generation."""
    id1 = generate_paper_id("test.pdf")
    id2 = generate_paper_id("test.pdf")
    
    # Should be unique (UUID)
    assert id1 != id2
    assert id1.startswith("UPLOAD_")
```

### Integration Tests

**File:** `tests/test_file_upload_integration.py` (NEW FILE)

```python
import pytest
from django.test import Client
from django.contrib.auth.models import User
from pathlib import Path
from django.conf import settings

@pytest.mark.django_db
def test_upload_pdf_and_generate_video(client):
    """Test complete flow: upload PDF → generate video."""
    # Create test user
    user = User.objects.create_user("testuser", "test@example.com", "password")
    client.force_login(user)
    
    # Create test PDF file
    test_pdf = Path(__file__).parent / "fixtures" / "test_paper.pdf"
    
    # Upload PDF
    with open(test_pdf, "rb") as f:
        response = client.post("/upload/", {
            "file": f,
            "access_code": settings.VIDEO_ACCESS_CODE,
        })
    
    assert response.status_code == 302  # Redirect to status page
    
    # Check paper.json was created
    # ... verify paper.json exists ...
    
    # Check pipeline started
    # ... verify job was created ...
```

### Manual Testing Checklist

- [ ] Upload valid PDF file (< 50MB)
- [ ] Verify paper.json is created with correct structure
- [ ] Verify pipeline skips fetch-paper step
- [ ] Verify video generation completes successfully
- [ ] Upload PDF > 50MB → should show error
- [ ] Upload non-PDF file → should show error
- [ ] Upload corrupted PDF → should show error
- [ ] Upload empty PDF → should show error
- [ ] Verify extracted title is reasonable
- [ ] Verify full text is extracted correctly
- [ ] Test with multi-page PDF
- [ ] Test with PDF containing images (should still work)
- [ ] Verify paper ID is unique for each upload

---

## Error Handling

### Error Scenarios and Messages

| Scenario | Error Message | User Action |
|----------|---------------|-------------|
| File not PDF | "Only PDF files are supported." | Upload PDF file |
| File too large | "File size (X MB) exceeds maximum allowed size (50MB)" | Upload smaller file |
| Corrupted PDF | "Invalid PDF file: [details]" | Fix or re-upload PDF |
| Empty PDF | "PDF appears to be empty or contains too little text" | Upload valid PDF |
| Extraction failure | "Failed to extract content from PDF: [details]" | Try different PDF |
| Save failure | "Failed to save uploaded file: [details]" | Retry upload |

### Error Logging

All errors should be logged with:
- Full exception traceback
- File name and size
- User ID (if authenticated)
- Timestamp

Example:
```python
logger.error(
    f"PDF extraction failed for user {user_id}, file {filename}: {e}",
    exc_info=True
)
```

---

## Edge Cases

### 1. PDF with No Text (Scanned Images)
- **Issue:** PDF contains only images, no extractable text
- **Solution:** Extract text using OCR (future enhancement)
- **MVP:** Show error: "PDF appears to contain only images. Text extraction is not supported for scanned PDFs."

### 2. Encrypted/Password-Protected PDF
- **Issue:** PDF requires password
- **Solution:** Show error: "PDF is password-protected. Please upload an unencrypted PDF."

### 3. Very Large PDF (> 50MB)
- **Issue:** File exceeds size limit
- **Solution:** Reject with clear error message

### 4. Multi-Column Layout
- **Issue:** Text extraction may be out of order
- **Solution:** pdfplumber handles this reasonably well, but may need improvement

### 5. PDF with Complex Formatting
- **Issue:** Tables, equations, special characters
- **Solution:** Extract text as-is, let AI handle interpretation

### 6. Duplicate Filenames
- **Issue:** Multiple users upload same filename
- **Solution:** Unique paper ID prevents conflicts

### 7. Concurrent Uploads
- **Issue:** Same user uploads multiple files simultaneously
- **Solution:** Each gets unique ID, no conflict

---

## File Structure Changes

### New Files
```
web/
  └── pdf_extractor.py          # NEW: PDF extraction utilities
```

### Modified Files
```
requirements.txt                 # ADD: pdfplumber==0.10.3
web/
  ├── views.py                   # MODIFY: upload_paper() function
  └── forms.py                   # OPTIONAL: Add file validation
pipeline/
  └── pipeline.py                # MODIFY: Skip fetch-paper if paper.json exists
```

### Directory Structure After Implementation
```
media/
  └── UPLOAD_<uuid>/
      ├── uploaded_file.pdf      # Original uploaded file
      └── paper.json            # Extracted content (created before pipeline)
      └── script.json           # Generated by pipeline
      └── audio.wav             # Generated by pipeline
      └── clips/                # Generated by pipeline
      └── final_video.mp4        # Generated by pipeline
```

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review this document
- [ ] Understand current pipeline flow
- [ ] Set up development environment
- [ ] Install pdfplumber: `pip install pdfplumber==0.10.3`

### Implementation Steps
- [ ] Step 1: Add pdfplumber to requirements.txt
- [ ] Step 2: Create web/pdf_extractor.py with all functions
- [ ] Step 3: Update web/views.py upload_paper() function
- [ ] Step 4: Update pipeline/pipeline.py to skip fetch-paper
- [ ] Step 5: Test PDF extraction locally
- [ ] Step 6: Test complete upload → video generation flow
- [ ] Step 7: Test error cases (invalid files, etc.)
- [ ] Step 8: Update form validation (optional)

### Post-Implementation
- [ ] Run all tests
- [ ] Test with various PDF types
- [ ] Verify paper.json structure matches PubMed format
- [ ] Check error messages are user-friendly
- [ ] Verify logging works correctly
- [ ] Test file cleanup (if implemented)
- [ ] Update documentation if needed

---

## Notes for Implementation

1. **Paper ID Format:** Using `UPLOAD_<uuid>` prefix makes it clear these are uploaded files, not PubMed papers.

2. **Figure Extraction:** Skipped for MVP. Can be added later if needed.

3. **Metadata Quality:** Rule-based extraction is basic but sufficient for MVP. Can be enhanced with AI later.

4. **File Cleanup:** Consider adding cleanup job to remove old uploaded files after video generation completes.

5. **Progress Tracking:** No changes needed - existing progress tracking works for uploaded files too.

6. **Cloud Storage:** If using R2, uploaded files should also be stored there (future enhancement).

---

## Questions or Issues?

If you encounter issues during implementation:

1. Check logs for detailed error messages
2. Verify pdfplumber is installed correctly
3. Test PDF extraction in isolation first
4. Ensure paper.json structure matches expected format
5. Verify pipeline detects existing paper.json correctly

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-28  
**Status:** Ready for Implementation

