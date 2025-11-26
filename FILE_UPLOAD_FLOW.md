# File Upload Feature - Flow Diagrams

## High-Level User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER FLOW                                 │
└─────────────────────────────────────────────────────────────────┘

User Registration / Login
         ↓
User navigates to /upload/
         ↓
    ┌────────────────────────────────────────┐
    │    Choose input method:                 │
    │  A) Enter PubMed ID/PMCID               │
    │  B) Upload PDF or TXT file              │
    └────────────────────────────────────────┘
         ↓
    ┌─────────────────┬──────────────────────┐
    │ PATH A          │ PATH B               │
    │ PubMed ID       │ File Upload          │
    ↓                 ↓
Validate PMID    Save to disk
    ↓                 ↓
Enter            Process file
Access Code      (extract text)
    ↓                 ↓
Submit           Create paper.json
    ↓                 │
    └─────────────────┴──────────────────────┘
         ↓
Start Pipeline Asynchronously
(Celery task)
         ↓
Display Status Page
(Real-time progress tracking)
         ↓
Video Generation Complete
         ↓
Download Video
```

## Detailed File Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              FILE UPLOAD PROCESSING PIPELINE                     │
└─────────────────────────────────────────────────────────────────┘

User Uploads File
         ↓
Save to media/<filename>/<original-filename>
         ↓
Validate File (web/file_utils.py)
    │
    ├─ Check file exists ✓
    ├─ Check file size (max 50MB) ✓
    ├─ Check file type (.pdf or .txt) ✓
    ├─ Check file not empty ✓
    ↓
Extract Text
    │
    ├─ If PDF: Use PyPDF2
    │   └─ Read pages → extract text → concatenate
    │
    └─ If TXT: Read directly
        └─ UTF-8 decode → return text
         ↓
Create paper.json (web/file_utils.py)
    │
    ├─ Set title from filename
    ├─ Set abstract (first 500 chars)
    ├─ Set full_text (all extracted text)
    ├─ Set authors: ["Unknown"]
    ├─ Set publication_date: (current time)
    ├─ Set source: "local_file"
    └─ Set filename: (original filename)
         ↓
Save paper.json to media/<filename>/
         ↓
Return Success to Web View
    └─ Redirect to status page
```

## Pipeline Execution Flow - File vs PubMed

```
┌────────────────────────────────────────────────────────────────┐
│                   PIPELINE COMPARISON                           │
└────────────────────────────────────────────────────────────────┘

PUBMED ID PATH:
┌─────────────────────────────┐
│ 1. fetch-paper              │  ← Fetch from PubMed Central
│    Create paper.json        │
├─────────────────────────────┤
│ 2. generate-script          │
├─────────────────────────────┤
│ 3. generate-audio           │
├─────────────────────────────┤
│ 4. generate-videos          │
├─────────────────────────────┤
│ 5. add-captions             │
├─────────────────────────────┤
│ OUTPUT: final_video.mp4     │
└─────────────────────────────┘

LOCAL FILE PATH:
┌─────────────────────────────┐
│ (paper.json already exists) │  ← Pre-processed by file_utils
├─────────────────────────────┤
│ 1. generate-script          │  ← Same as above
├─────────────────────────────┤
│ 2. generate-audio           │
├─────────────────────────────┤
│ 3. generate-videos          │
├─────────────────────────────┤
│ 4. add-captions             │
├─────────────────────────────┤
│ OUTPUT: final_video.mp4     │
└─────────────────────────────┘

Result: Local files are processed faster (skip fetch-paper)
```

## Error Handling Flow

```
┌────────────────────────────────────────────────────────────────┐
│                   ERROR HANDLING                                │
└────────────────────────────────────────────────────────────────┘

File Upload
         ↓
    ┌────────────────────────────────────────┐
    │  Validation Error?                      │
    └────────────────────────────────────────┘
         │
    ┌────┴────┬────────────┬──────────┬─────┐
    │          │            │          │     │
    ↓          ↓            ↓          ↓     ↓
   No file   Too large   Wrong type  Empty Invalid
   found     (>50MB)      (not .pdf   file  PDF
                          or .txt)
    │         │            │          │     │
    └─────────┴────────────┴──────────┴─────┘
              ↓
    Display Error Message to User
              ↓
    Form shows error and file input
              ↓
    User can correct and resubmit
```

## Directory Structure After Upload

```
ai-study-videos/
├── media/
│   └── my-paper-title/              ← Directory created from filename
│       ├── my-paper-title.pdf       ← Original uploaded file
│       ├── paper.json               ← Created by file_utils
│       │   ├── title
│       │   ├── abstract
│       │   ├── full_text
│       │   ├── authors
│       │   ├── publication_date
│       │   ├── source
│       │   └── filename
│       ├── task_id.txt              ← Celery task ID
│       ├── task_result.json         ← Task status (running/completed/failed)
│       ├── pipeline.log             ← Pipeline execution log
│       │
│       ├── script.json              ← Generated by pipeline
│       ├── audio.wav                ← Generated by pipeline
│       ├── audio_metadata.json      ← Generated by pipeline
│       │
│       ├── clips/                   ← Generated by pipeline
│       │   ├── scene_00.mp4
│       │   ├── scene_01.mp4
│       │   └── .videos_complete
│       │
│       ├── clips_captioned/         ← Generated by pipeline
│       │   ├── scene_00_captioned.mp4
│       │   ├── scene_01_captioned.mp4
│       │   └── .captions_complete
│       │
│       └── final_video.mp4          ← Final output
```

## Component Interaction Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                          │
└────────────────────────────────────────────────────────────────┘

                        DJANGO WEB
                        ┌──────────┐
                        │ views.py │
                        │upload_    │
                        │paper()    │
                        └─────┬────┘
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
              ┌──────────────┐  ┌──────────────────┐
              │ forms.py     │  │ file_utils.py    │
              │              │  │ (NEW FILE)       │
              │ Validation   │  │ ├─ Extract text  │
              │ fields       │  │ ├─ Validate      │
              └──────────────┘  │ ├─ Create JSON   │
                                └──────────────────┘
                                      │
                    ┌─────────────────┴──────────────────┐
                    ↓                                    ↓
            ┌──────────────────┐            ┌──────────────────┐
            │ tasks.py         │            │ media/ directory │
            │                  │            │                  │
            │ generate_video   │            │ Stores files:    │
            │ _task (Celery)   │            │ ├─ Uploaded PDF  │
            │                  │            │ ├─ paper.json    │
            └─────────┬────────┘            │ ├─ Logs          │
                      │                     │ └─ Output video  │
                      ↓                     └──────────────────┘
            ┌──────────────────────┐
            │ kyle-code/main.py    │
            │                      │
            │ generate_video()     │ ← Auto-detects local files
            │ Command              │
            └─────────┬────────────┘
                      │
                      ↓
            ┌──────────────────────┐
            │ kyle-code/pipeline.py│
            │                      │
            │ orchestrate_pipeline │ ← Skips fetch-paper
            │ (is_local_file=True) │   for local files
            └─────────┬────────────┘
                      │
        ┌─────────────┼─────────────┬──────────┐
        ↓             ↓             ↓          ↓
    ┌────────┐  ┌──────────┐ ┌──────────┐ ┌───────┐
    │generate│  │generate  │ │generate  │ │add-   │
    │script  │→ │audio     │→│videos    │→│caption│
    └────────┘  └──────────┘ └──────────┘ └───────┘
                                          │
                                          ↓
                                   ┌────────────────┐
                                   │ final_video.mp4│
                                   └────────────────┘
```

## State Diagram - Upload Status Progression

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATUS PROGRESSION                            │
└─────────────────────────────────────────────────────────────────┘

                        Pending
                           ↓
                  Validating File
                           ↓
                  Processing File
                    ├─ Extract text
                    ├─ Create paper.json
                           ↓
            ┌───────────────┴────────────────┐
            │ Success                        │ Error
            ↓                                ↓
    Pipeline Running           Error Page Displayed
         ↓                      ├─ File validation error
    ┌────────────────┐          ├─ Text extraction error
    │ generate-script│          ├─ PDF processing error
    │ generate-audio │          └─ File save error
    │ generate-videos│
    │ add-captions   │
    └────────────────┘
         ↓
    Video Ready
         ↓
    Download/View
```

## Code Organization

```
web/                          kyle-code/
├── forms.py                  ├── main.py
├── views.py      ──────┐     ├── pipeline.py
├── tasks.py       ←────┼──→  ├── pubmed.py
├── models.py              │   ├── scenes.py
├── file_utils.py (NEW) ──┘   ├── audio.py
└── ...                        ├── video.py
                               ├── captions.py
                               └── ...
```

---

**Architecture designed to be simple, maintainable, and extensible**
