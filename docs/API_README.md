# Hidden Hill Video Generation API

This document describes the REST API for generating videos from PubMed papers using the kyle-code pipeline.

## Prerequisites

Before using the API, you need to set the following environment variables:

1. **GEMINI_API_KEY** - Your Google Gemini API key (for text-to-speech and scene generation)
2. **RUNWAYML_API_SECRET** - Your RunwayML API key (for video generation)

These can be set in your `.env` file for local development, or as environment variables in your deployment environment.

## API Endpoints

### 1. Start Video Generation

**POST** `/api/generate/`

Starts the video generation pipeline for a given PubMed ID or PMCID.

**Request Body (JSON):**
```json
{
  "paper_id": "PMC10979640",
  "access_code": "your-access-code-here"
}
```

Or as form data:
```
paper_id=PMC10979640&access_code=your-access-code-here
```

**Note:** The `access_code` is required to prevent unauthorized usage. Contact the administrator to obtain the access code.

**Response (200 OK):**
```json
{
  "success": true,
  "paper_id": "PMC10979640",
  "status_url": "/api/status/PMC10979640/",
  "result_url": "/api/result/PMC10979640/",
  "message": "Pipeline started successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Missing or invalid `paper_id`
- `403 Forbidden`: Invalid or missing `access_code`
- `409 Conflict`: Pipeline already running for this paper_id
- `500 Internal Server Error`: Missing API keys or other server errors

**Example using curl:**
```bash
curl -X POST http://localhost:8000/api/generate/ \
  -H "Content-Type: application/json" \
  -d '{"paper_id": "PMC10979640"}'
```

---

### 2. Check Pipeline Status

**GET** `/api/status/<paper_id>/`

Returns the current status and progress of the video generation pipeline.

**Response (200 OK):**
```json
{
  "paper_id": "PMC10979640",
  "status": "running",
  "current_step": "generate-videos",
  "completed_steps": ["fetch-paper", "generate-script", "generate-audio"],
  "progress_percent": 60,
  "final_video_url": null,
  "log_tail": "Last 8KB of pipeline log output..."
}
```

**Status Values:**
- `pending`: Pipeline hasn't started yet
- `running`: Pipeline is currently executing
- `completed`: Pipeline finished successfully
- `failed`: Pipeline encountered an error

**Pipeline Steps:**
1. `fetch-paper` - Download paper from PubMed Central
2. `generate-script` - Generate video script with scenes using Gemini
3. `generate-audio` - Generate text-to-speech audio for narration
4. `generate-videos` - Generate video clips using RunwayML Veo 3.1
5. `add-captions` - Add captions and merge into final video

**Example using curl:**
```bash
curl http://localhost:8000/api/status/PMC10979640/
```

---

### 3. Get Final Video Result

**GET** `/api/result/<paper_id>/`

Returns the final video URL when generation is complete.

**Response (200 OK) - Video Ready:**
```json
{
  "paper_id": "PMC10979640",
  "success": true,
  "video_url": "/media/PMC10979640/final_video.mp4",
  "status": "completed",
  "progress_percent": 100
}
```

**Response (202 Accepted) - Video Not Ready:**
```json
{
  "paper_id": "PMC10979640",
  "success": false,
  "error": "Video not ready yet",
  "status": "running",
  "progress_percent": 60,
  "status_url": "/api/status/PMC10979640/"
}
```

**Example using curl:**
```bash
curl http://localhost:8000/api/result/PMC10979640/
```

---

## Complete Workflow Example

Here's a complete example of using the API to generate a video:

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# 1. Start generation
response = requests.post(
    f"{BASE_URL}/api/generate/",
    json={
        "paper_id": "PMC10979640",
        "access_code": "your-access-code-here"  # Required!
    }
)
data = response.json()
print(f"Started: {data['message']}")

# 2. Poll for status
paper_id = data["paper_id"]
status_url = data["status_url"]

while True:
    response = requests.get(f"{BASE_URL}{status_url}")
    status = response.json()
    
    print(f"Status: {status['status']} - {status['progress_percent']}%")
    print(f"Current step: {status['current_step']}")
    
    if status["status"] == "completed":
        print(f"Video ready: {status['final_video_url']}")
        break
    elif status["status"] == "failed":
        print("Pipeline failed!")
        print(status.get("log_tail", ""))
        break
    
    time.sleep(5)  # Poll every 5 seconds

# 3. Get final result
response = requests.get(f"{BASE_URL}/api/result/{paper_id}/")
result = response.json()
if result["success"]:
    print(f"Final video: {BASE_URL}{result['video_url']}")
```

---

## Web UI

The web application also provides a user-friendly interface:

- **Upload Page**: `/upload/` - Submit a PubMed ID or upload a file
- **Status Page**: `/status/<pmid>/` - View pipeline status with progress
- **Result Page**: `/result/<pmid>/` - View the final generated video

---

## Notes

- The pipeline typically takes 5-15 minutes depending on the number of scenes and video generation time
- Videos are stored in `MEDIA_ROOT/<paper_id>/final_video.mp4`
- The pipeline is idempotent - it will skip already completed steps if restarted
- All intermediate files (paper.json, script.json, audio files, video clips) are saved in the output directory for debugging

## Error Handling

If the pipeline fails, check:
1. The `log_tail` field in the status response for error messages
2. The full log file at `MEDIA_ROOT/<paper_id>/pipeline.log`
3. Ensure API keys are correctly set in environment variables
4. Verify the PubMed ID is valid and the paper is available in PubMed Central (open access)

