# File Upload Feature Implementation

## Summary
Task 3 has been successfully implemented. The file upload feature now allows users to upload PDF or TXT files, which are automatically converted to the paper.json format and processed through the video generation pipeline without requiring a PubMed ID.

## Changes Made

### 1. Added PyPDF2 Dependency
**File:** `requirements.txt`
- Added `PyPDF2>=3.0.0` for PDF text extraction

### 2. Created File Utilities Module
**File:** `web/file_utils.py` (NEW)
- `validate_uploaded_file()`: Validates file type and size (max 50MB, supports .pdf and .txt)
- `extract_text_from_pdf()`: Extracts text from PDF files
- `extract_text_from_file()`: Routes to appropriate extraction method based on file type
- `create_paper_json()`: Converts extracted text to paper.json format (matches PubMed structure)
- `process_uploaded_file()`: Orchestrates validation, extraction, and conversion
- `FileExtractionError`: Custom exception for file processing errors

**Features:**
- Comprehensive error handling with user-friendly messages
- File size validation (max 50MB)
- File type validation (.pdf, .txt only)
- Graceful handling of corrupted PDFs
- Logging for debugging

### 3. Updated Pipeline to Support Local Files
**File:** `kyle-code/pipeline.py`
- Added `is_local_file` parameter to `orchestrate_pipeline()`
- When `is_local_file=True`, skips the fetch-paper step
- Verifies paper.json exists before proceeding
- Local files don't require PubMed IDs

**Logic:**
- If paper.json already exists → skip fetch-paper step
- If paper.json missing → raise error (file processing failed)
- All subsequent steps (generate-script, generate-audio, etc.) proceed normally

### 4. Updated Main CLI to Auto-Detect Local Files
**File:** `kyle-code/main.py`
- Modified `generate_video()` command to detect local files
- Checks if paper.json exists in output directory
- Automatically sets `is_local_file=True` for pre-processed files

### 5. Updated Web Views with File Processing
**File:** `web/views.py`
- Imported file utilities
- Enhanced `upload_paper()` view to:
  1. Save uploaded file to disk
  2. Call `process_uploaded_file()` to extract and convert
  3. Handle errors with user-friendly messages
  4. Start pipeline with processed paper.json

**Error Handling:**
- File save errors
- File processing errors (extraction, validation, etc.)
- All errors displayed to user on the form

## How It Works

### User Flow
1. User registers/logs in
2. User navigates to upload form
3. User either:
   - **Option A:** Provides PubMed ID/PMCID → Pipeline fetches from PubMed
   - **Option B:** Uploads PDF/TXT file → File is processed locally
4. User enters access code
5. Form validates and:
   - For PubMed: Creates paper.json from PubMed data
   - For files: Creates paper.json from extracted text
6. Pipeline starts (skips fetch-paper for local files)
7. Status page shows progress
8. Video is generated and available for download

### Pipeline Execution
```
PubMed ID flow:
- fetch-paper → generate-script → generate-audio → generate-videos → add-captions → final_video.mp4

Local file flow:
- (paper.json already exists) → generate-script → generate-audio → generate-videos → add-captions → final_video.mp4
```

## Supported File Types
- **PDF** (.pdf): Text extracted using PyPDF2 library
- **Text** (.txt): Read directly with UTF-8 encoding
- **Size limit:** 50MB per file
- **Error handling:** Gracefully handles corrupted/unreadable files

## Testing

### Manual Testing Steps
1. **Test PDF Upload:**
   - Upload a valid PDF file
   - Verify paper.json is created in media directory
   - Check that text was properly extracted
   - Verify pipeline skips fetch-paper step
   - Confirm video generation succeeds

2. **Test TXT Upload:**
   - Upload a valid text file
   - Verify paper.json is created
   - Confirm pipeline processes correctly

3. **Test Validation:**
   - Try to upload file > 50MB (should be rejected)
   - Try to upload unsupported file type like .docx (should be rejected)
   - Try to upload empty file (should be rejected)
   - Try to upload corrupted PDF (should show error)

4. **Test PubMed ID Still Works:**
   - Upload with PubMed ID should still work normally
   - Verify fetch-paper step is NOT skipped

### Testing in Development
```bash
# Install dependencies (in venv)
pip install -r requirements.txt

# Run Django development server
python manage.py runserver

# Test file upload at:
# http://localhost:8000/upload/

# Check created paper.json:
# cat media/<filename>/paper.json
```

## Paper JSON Structure
Files are converted to this format:
```json
{
  "title": "extracted-filename-as-title",
  "abstract": "First 500 characters of extracted text",
  "full_text": "Complete extracted text from file",
  "authors": ["Unknown"],
  "publication_date": "ISO timestamp",
  "source": "local_file",
  "filename": "original-filename"
}
```

## Known Limitations
1. **No DOCX Support:** Only PDF and TXT files. DOCX would require `python-docx` library.
2. **Simple Metadata:** Extracted files don't have real metadata like authors, publication date, etc.
3. **Text Extraction Quality:** Depends on PDF structure. Complex layouts may have issues.
4. **No OCR:** Cannot extract text from scanned PDFs or images.

## Future Enhancements
1. Add DOCX support (requires `python-docx`)
2. Add OCR for scanned PDFs (requires `pytesseract`, `Tesseract` binary)
3. Improve metadata extraction from PDFs
4. Add file upload progress tracking
5. Support for other formats (.epub, .docx, etc.)

## Error Messages Shown to Users
- "File is too large (max 50MB)"
- "File is empty"
- "Unsupported file type. Supported: .pdf, .txt"
- "Failed to extract text from PDF: [specific error]"
- "Failed to read text file: [specific error]"
- "File processing error: [specific error]"
- "Failed to save file: [specific error]"

## Implementation Details

### File Processing Flow
```
1. User uploads file
   ↓
2. Save file to media/<filename>/ directory
   ↓
3. Validate file (size, type, not empty)
   ↓
4. Extract text (PDF → PyPDF2, TXT → read)
   ↓
5. Create paper.json with extracted text
   ↓
6. Start pipeline (auto-detects local file, skips fetch-paper)
   ↓
7. Generate video from extracted content
```

### Code Quality
- All functions have docstrings
- Comprehensive error handling
- Logging for debugging
- Type hints for clarity
- Follows project conventions

## Files Modified/Created
1. ✅ `requirements.txt` - Added PyPDF2
2. ✅ `web/file_utils.py` - NEW file with all extraction/conversion logic
3. ✅ `web/views.py` - Updated upload_paper() to use file utilities
4. ✅ `kyle-code/pipeline.py` - Added is_local_file parameter and logic
5. ✅ `kyle-code/main.py` - Auto-detect local files and pass is_local_file flag

## Testing Status
- ✅ Python syntax validation passed for all modified files
- ✅ Import validation passed
- ⏳ End-to-end testing pending (requires full environment setup)
- ⏳ PDF extraction testing pending (requires PyPDF2 installation)

## Next Steps (For Your Team)
1. **Test in development environment** after installing dependencies
2. **Test with real PDF/TXT files** to verify quality
3. **Monitor error handling** in production
4. **Consider DOCX support** if users request it (would need python-docx)

---

**Implementation completed by:** Claude Code
**Date:** 2025-11-25
**Status:** Ready for testing
