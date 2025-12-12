# Hidden Hill (KyleAI)

**Transform Research Into Visual Stories**

Hidden Hill is a Django web application that automatically converts scientific papers into engaging social media videos (TikTok/Instagram Reels format). The system uses AI (Google Gemini for text/audio generation, RunwayML for video generation) to transform complex research papers from PubMed Central into accessible, shareable video content.

## 🎯 Problem Being Solved

Scientific research is often locked behind paywalls and buried in technical jargon, making it inaccessible to the general public. Hidden Hill democratizes science by:

- **Breaking Down Barriers**: Converting complex research papers into engaging visual stories
- **Increasing Reach**: Videos get 10x more engagement than static PDFs
- **Accelerating Discovery**: Sharing findings faster than traditional publication timelines
- **Amplifying Impact**: Making research more visible, shareable, and impactful

## 🚀 Production Environment

- **Production URL**: https://ai-study-videos-production.up.railway.app/
- **Staging URL**: Not currently configured (can be set up as needed)

## 🛠️ Technology Stack

### Backend
- **Django 5.1.2** - Web framework
- **Celery 5.3.6** - Asynchronous task queue
- **Redis 5.0.1** - Message broker for Celery
- **PostgreSQL** - Production database (via Railway)
- **SQLite** - Local development database

### AI & APIs
- **Google Gemini API** - Text generation, scene creation, and text-to-speech
- **RunwayML API** - Video generation using Veo 3.1 model

### Storage
- **Cloudflare R2** - Cloud storage for generated videos (S3-compatible)
- **Railway Volumes** - Persistent storage option (alternative to R2)

### Infrastructure
- **Railway** - Hosting and deployment platform
- **Gunicorn** - WSGI HTTP server
- **WhiteNoise** - Static file serving

### Frontend
- **HTML/CSS/JavaScript** - Traditional web stack
- **Django Templates** - Server-side rendering

## 🚢 Deployment Information

### Production Environment

- **URL**: https://ai-study-videos-production.up.railway.app/
- **Platform**: Railway
- **Database**: PostgreSQL (managed by Railway)
- **Storage**: Cloudflare R2 (cloud storage)
- **Task Queue**: Redis (managed by Railway)

### Staging Environment

- **URL**: Not currently configured
- **Setup**: Can be configured similarly to production on Railway with a separate service

### Deployment Process

Deployment to Railway is automated via GitHub integration:

1. **Link Repository to Railway**
   - Connect GitHub repository to Railway service
   - Railway automatically detects Django projects

2. **Configure Environment Variables**
   Set the following in Railway dashboard:
   ```
   GEMINI_API_KEY=<your-key>
   RUNWAYML_API_SECRET=<your-key>
   SECRET_KEY=<your-secret-key>
   VIDEO_ACCESS_CODE=<your-access-code>
   DATABASE_URL=<railway-postgres-url>
   USE_CLOUD_STORAGE=True
   AWS_ACCESS_KEY_ID=<r2-key>
   AWS_SECRET_ACCESS_KEY=<r2-secret>
   AWS_STORAGE_BUCKET_NAME=<bucket-name>
   AWS_S3_ENDPOINT_URL=<r2-endpoint>
   CELERY_BROKER_URL=<railway-redis-url>
   CELERY_RESULT_BACKEND=<railway-redis-url>
   DEBUG=False
   ALLOWED_HOSTS=.up.railway.app
   CSRF_TRUSTED_ORIGINS=https://*.up.railway.app
   ```

3. **Attach Services**
   - PostgreSQL database (Railway managed)
   - Redis (Railway managed)
   - Optional: Railway Volume for persistent storage (alternative to R2)

4. **Deploy**
   - Railway automatically deploys on git push
   - Or manually trigger deployment from Railway dashboard

5. **Run Migrations**
   ```bash
   # Via Railway CLI or dashboard
   railway run python manage.py migrate
   railway run python manage.py collectstatic --noinput
   ```

### Deployment Commands

**Manual Deployment (if needed):**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# Deploy
railway up

# Run migrations
railway run python manage.py migrate

# Collect static files
railway run python manage.py collectstatic --noinput
```

**Procfile** (automatically used by Railway):
```
web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT}
worker: celery -A config worker --loglevel=info --concurrency=2 --max-tasks-per-child=50
```

## 👥 Team Member Contributions

*Note: Team member information should be added here. Please update with actual team member names and their contributions.*

### Example Format:
- **Team Member 1** - Backend development, pipeline architecture
- **Team Member 2** - Frontend development, UI/UX design
- **Team Member 3** - DevOps, deployment, infrastructure
- **Team Member 4** - Testing, QA, documentation

## 🧪 A/B Test Endpoint

### How to Compute the A/B Test Endpoint

The A/B test endpoint is computed using a SHA-1 hash of team nicknames. Here's how to compute and access it:

#### Step 1: List Team Nicknames

Team nicknames should be defined (typically in a configuration file or database). For example:
- "HiddenHill"
- "KyleAI"
- "ScienceVideos"

#### Step 2: Compute SHA-1 Hash

**Python:**
```python
import hashlib

team_nickname = "HiddenHill"  # Replace with actual team nickname
hash_object = hashlib.sha1(team_nickname.encode())
hex_dig = hash_object.hexdigest()
print(hex_dig)  # e.g., "a1b2c3d4e5f6..."
```

**Command Line (Linux/Mac):**
```bash
echo -n "HiddenHill" | sha1sum
```

**Command Line (Windows PowerShell):**
```powershell
$teamNickname = "HiddenHill"
$sha1 = [System.Security.Cryptography.SHA1]::Create()
$hash = $sha1.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($teamNickname))
$hexString = ($hash | ForEach-Object { $_.ToString("x2") }) -join ""
Write-Host $hexString
```

#### Step 3: Access the Endpoint

Once the A/B test endpoint is implemented, access it using:

```
https://ai-study-videos-production.up.railway.app/ab-test/<sha1-hash>/
```

For example:
```
https://ai-study-videos-production.up.railway.app/ab-test/a1b2c3d4e5f6.../
```

#### Current Status

⚠️ **Note**: The A/B test endpoint is currently not implemented. According to the Sprint 4 report, it needs to:
- Compute SHA-1 hash of team nickname
- Create endpoint route in `web/urls.py`
- Display list of team nicknames
- Add analytics tracking for variant impressions

#### Implementation Example

When implemented, the endpoint should:
1. Accept a SHA-1 hash in the URL path
2. Match it to a team nickname
3. Display randomized button text variants
4. Track impressions and clicks via analytics

**Example View (to be implemented):**
```python
# web/views.py
import hashlib
from django.shortcuts import render

def ab_test(request, hash_value):
    # Match hash to team nickname
    team_nicknames = ["HiddenHill", "KyleAI", "ScienceVideos"]
    matched_nickname = None
    
    for nickname in team_nicknames:
        if hashlib.sha1(nickname.encode()).hexdigest() == hash_value:
            matched_nickname = nickname
            break
    
    # Display A/B test page with variants
    return render(request, 'ab_test.html', {
        'team_nickname': matched_nickname,
        'hash': hash_value
    })
```

## 📚 Additional Documentation

- **[API Documentation](./docs/API_README.md)** - Complete REST API reference
- **[Pipeline Guide](./docs/PIPELINE_README.md)** - Video generation pipeline details
- **[Next Steps](./docs/NEXT_STEPS.md)** - Roadmap and future features
- **[Testing Guide](./docs/TESTING.md)** - Testing procedures and scripts
- **[Railway Setup](./docs/RAILWAY_VOLUMES_SETUP.md)** - Persistent storage configuration

## 🔧 Development

### Running Tests

```bash
# Run Django tests
python manage.py test

# Run pipeline tests
cd tests
.\test_status.ps1  # Windows
```

### Project Structure

```
Hidden-Hill/
├── config/          # Django configuration
├── web/             # Main Django app
│   ├── models.py    # Database models
│   ├── views.py     # View handlers
│   ├── tasks.py     # Celery tasks
│   └── templates/   # HTML templates
├── pipeline/        # Video generation pipeline
│   ├── main.py      # CLI entry point
│   ├── pipeline.py  # Core pipeline logic
│   ├── pubmed.py    # PubMed integration
│   ├── scenes.py    # Scene generation
│   ├── audio.py     # Audio generation
│   └── video.py    # Video generation
├── docs/            # Documentation
├── scripts/         # Utility scripts
└── tests/           # Test scripts
```

## 📝 License

*Add license information here*

## 🤝 Contributing

*Add contribution guidelines here*

---

**Last Updated**: 2025-01-28  
**Project Status**: Production-ready, core features complete

