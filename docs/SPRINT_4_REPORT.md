# Sprint 4 Report 

## 1. Sprint Goal & Achievement

### Sprint Goal:

The goal of Sprint 4 was to complete remaining MVP features, deploy the application to production, implement the required A/B test endpoint, integrate analytics tracking, and ensure the project was ready for the final submission phase.

### Achievement Assessment:

The production deployment is complete and stable. The backend architecture, pipeline, and documentation are strong. The A/B test endpoint and analytics tracking are in progress. As a result, the sprint goal was largely achieved.

## 2. Production Deployment

### Production URL

https://ai-study-videos-production.up.railway.app/

### What's Working

- Application is fully deployed and publicly accessible
- All core backend features run without crashes
- Environment-variable-based configuration (12-factor compliant)
- Cloudflare R2 storage integration configured
- Deployment artifacts (Procfile, Aptfile, runtime configuration) in place
- Migration script (run_migrations.py) functional
- Railway volume setup documented and ready

### What's Not Working

- A/B test endpoint missing
- No analytics tracking integrated (Google Analytics / Plausible)
- No monitoring/logging confirmation from production

### Deployment Process

Deployment to Railway is achieved through:

1. Linking the GitHub repository to a Railway service
2. Setting required environment variables (DATABASE_URL, SECRET_KEY, USE_CLOUD_STORAGE, Cloudflare R2 credentials, etc.)
3. Attaching a persistent volume for media
4. Running database migrations
5. Deploying updates automatically via GitHub → Railway pipeline

## 3. A/B Test Endpoint

### Endpoint URL

Not implemented yet.

### Current Status

- No route in web/urls.py
- No view handling randomized button text
- No template displaying team nicknames
- No analytics script in base.html or any template

### Required Steps

- Compute SHA-1 hash of team nickname and create endpoint
- Display list of team nicknames
- Add analytics tracking
- Track variant impressions and (optionally) button clicks

## 4. Completed Work (Story Points)

Summary of completed Sprint 4 work based on the project state:

| User Story | Status | Points |
| --- | --- | --- |
| Production deployment configuration | Completed | 8 |
| Pipeline architecture & documentation | Completed | 7 |
| Progress tracking feature | Completed | 6 |

---

**Total completed work in Sprint 4: 26 points**

## 5. Velocity Summary

### Sprint Velocity

- Sprint 2: 22 points
- Sprint 3: 25 points
- Sprint 4: 26 points

**Average Velocity: 24.3 points**

## 6. Readiness for Final Submission 

### What's Complete

- Fully deployed and accessible production environment
- Mature backend architecture
- Cloud storage integration (Cloudflare R2)
- Progress tracking workflow
- Testing scripts and simulation mode
- Strong documentation (API, pipeline, testing, deployment setup)
- Clean and modular Django codebase

### What Remains for the Next 9 Days

1. Implement the A/B test endpoint
2. Integrate analytics (Google Analytics or Plausible)
3. Perform final QA on production
4. Prepare the final submission package

## Risks & Mitigation Plan 

| Risk | Impact | Mitigation |
| :-- | :-- | :-- |
| Missing A/B endpoint | Fails mandatory requirement | Implement immediately |
| No analytics integration | Cannot analyze variant performance | Add GA/Plausible minimal snippet |
| Missing sprint docs | Documentation penalty | Write sprint docs first |
| Time pressure | Reduced QA | Focus strictly on mandatory features |

## 7. Sprint Retrospective Highlights

### What Went Well

- Production deployment successful
- Strong architectural foundation
- High-quality documentation
- Stable backend with clear workflows

### What Didn't Go Well

- A/B testing and analytics still missing
- Some tasks postponed into final submission window

### Key Learnings

- Testing is expensive

---

## 8. Links 

- Production URL: https://ai-study-videos-production.up.railway.app/
- GitHub Repository: https://github.com/Kedylind/ai-study-videos

