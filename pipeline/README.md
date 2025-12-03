# Social media video generator for papers

## Quick Start

Generate a video from a PubMed/PMC paper ID:

### Using PowerShell (Windows):

1. Set your API keys as environment variables:
```powershell
$env:GEMINI_API_KEY = "your-gemini-api-key"
$env:RUNWAYML_API_SECRET = "your-runway-api-key"
```

2. Activate the virtual environment and run:
```powershell
cd "C:\Users\david\OneDrive\Desktop\Cursor Projects\Hidden-Hill"
.\venv\Scripts\activate.ps1
cd pipeline
python main.py generate-video PMC10979640 tmp/PMC10979640
```

### Using the test script:

```powershell
cd pipeline
.\test_video_generation.ps1 -PaperId PMC10979640 -OutputDir tmp/PMC10979640
```

(You'll still need to set the API keys as environment variables first)

### Using uv (if installed):

```bash
uv run python main.py generate-video PMC10979640 tmp/PMC10979640
```

## Requirements

- **GEMINI_API_KEY**: Google Gemini API key for text generation and TTS
- **RUNWAYML_API_SECRET**: Runway ML API key for video generation
- Python 3.12+ with dependencies installed (see `pyproject.toml`)
- FFmpeg (for video processing)

## Pipeline Steps

The `generate-video` command runs the complete pipeline:
1. **fetch-paper**: Download paper from PubMed Central
2. **generate-script**: Create video script with scenes using Gemini
3. **generate-audio**: Generate TTS audio for each scene
4. **generate-videos**: Create video clips with Runway Veo 3.1

Output will be saved to the specified output directory (e.g., `tmp/PMC10979640/`).
