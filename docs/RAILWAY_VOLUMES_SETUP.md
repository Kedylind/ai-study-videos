# Railway Volumes Setup Guide

This guide walks you through setting up persistent video storage using Railway Volumes.

## Why This Is Critical

Railway uses an **ephemeral filesystem** by default. This means:
- ❌ All files are **LOST** on container restart
- ❌ All files are **LOST** on deployment
- ❌ All files are **LOST** on service restart
- ❌ All files are **LOST** on scaling events

**Without persistent storage, generated videos will disappear after any restart!**

## Solution: Railway Volumes

Railway Volumes provide persistent storage that survives all container restarts and deployments.

---

## Step-by-Step Setup

### Step 1: Create Railway Volume

1. **Go to Railway Dashboard:**
   - Navigate to your Hidden Hill project
   - Click on your **web service** (the Django app service, not the database)

2. **Add Volume:**
   - In the service settings, scroll to the **"Volumes"** section
   - Click **"Add Volume"** or **"New Volume"**
   - **Name:** `media-storage` (or any descriptive name)
   - **Size:** Start with 10GB (can increase later)
   - Click **"Create"**

3. **Mount the Volume:**
   - After creating the volume, you'll see a **"Mount Path"** field
   - Set the mount path to: **`/app/media`**
   - This is where Railway will mount the persistent volume in your container
   - **Save** the configuration

**Important:** The mount path `/app/media` must match where your Django app expects media files.

---

### Step 2: Verify Configuration

The application is already configured to use `/app/media` as the media root:

- ✅ `MEDIA_ROOT = BASE_DIR / "media"` in `config/settings.py`
- ✅ `BASE_DIR` resolves to `/app` in Railway containers
- ✅ So `MEDIA_ROOT` = `/app/media` (matches volume mount path)

**No code changes needed!** The existing code already uses `MEDIA_ROOT` correctly.

---

### Step 3: Deploy and Test

1. **Deploy to Railway:**
   - Push your code (if you made any changes)
   - Railway will automatically redeploy
   - The volume will be mounted at `/app/media`

2. **Test Video Generation:**
   - Go to your Railway app URL
   - Log in and generate a video
   - Wait for it to complete
   - Note the paper ID (e.g., `PMC10979640`)

3. **Verify File Location:**
   - The video should be at: `/app/media/<paper_id>/final_video.mp4`
   - This path is now on the persistent volume

4. **Test Persistence:**
   - **Option A (Recommended):** In Railway dashboard, restart the service manually
   - **Option B:** Trigger a redeploy
   - After restart, check if the video is still accessible
   - Go to `/result/<paper_id>/` - video should still play ✅

5. **Verify in Database:**
   - Check `VideoGenerationJob` records in Django admin or database
   - `final_video_path` should show the path (e.g., `media/PMC10979640/final_video.mp4`)
   - The file should exist at that path even after restart

---

### Step 4: Verify Volume Mounting

Use the debug endpoint to verify the volume is mounted correctly:

**Visit:** `https://your-app.up.railway.app/debug-media/`

This will show:
- ✅ `MEDIA_ROOT_exists`: Should be `True`
- ✅ `MEDIA_ROOT_writable`: Should be `True`
- ✅ `MEDIA_ROOT_readable`: Should be `True`
- ✅ `volume_mounting_status`: Should be `"OK"`

If any of these are `False`, the volume isn't mounted correctly.

---

## Troubleshooting

### Problem: Videos still lost after restart

**Possible causes:**

1. **Volume not mounted correctly**
   - **Fix:** Check Railway dashboard → Volumes → Verify mount path is `/app/media`
   - Verify service is using the volume (should show in service settings)

2. **MEDIA_ROOT path mismatch**
   - **Fix:** Ensure `MEDIA_ROOT = BASE_DIR / "media"` and volume is at `/app/media`
   - Check that `BASE_DIR` is `/app` in Railway (it should be)

3. **Files being written to wrong location**
   - **Fix:** Visit `/debug-media/` to verify where files are actually being written
   - Check `web/tasks.py` and `web/views.py` - ensure they use `settings.MEDIA_ROOT`

### Problem: Permission errors

**If you see permission errors:**
- Railway volumes should have correct permissions automatically
- If not, you may need to set volume permissions in Railway dashboard
- Or add a startup script to set permissions (rarely needed)

### Problem: Volume not showing in dashboard

**If you can't find Volumes section:**
- Make sure you're on the correct service (web service, not database)
- Some Railway plans may have volume limits - check your plan
- Try creating volume from project level instead of service level

---

## Expected Result

After completing these steps:

✅ Videos are saved to `/app/media/<paper_id>/final_video.mp4`  
✅ Files persist across container restarts  
✅ Files persist across deployments  
✅ Users can access videos even after service restarts  
✅ Database records match actual file locations  
✅ "My Videos" page shows accessible videos  

---

## Testing Checklist

- [ ] Volume created in Railway dashboard
- [ ] Volume mounted at `/app/media`
- [ ] `MEDIA_ROOT` in settings matches mount path
- [ ] Debug endpoint (`/debug-media/`) shows `volume_mounting_status: "OK"`
- [ ] Generated a test video
- [ ] Video file exists at expected path
- [ ] Restarted Railway service
- [ ] Video still accessible after restart
- [ ] Database record shows correct path
- [ ] User can view video in "My Videos" page
- [ ] Video playback works correctly

---

## Advanced: Custom Media Path

If you need to use a different media path, you can set the `MEDIA_ROOT` environment variable:

```bash
# In Railway environment variables
MEDIA_ROOT=/custom/path/to/media
```

Then mount your Railway volume at that path instead of `/app/media`.

---

## Next Steps

Once Railway Volumes are working:

1. **Monitor storage usage:**
   - Check volume size in Railway dashboard
   - Plan for cleanup of old videos if needed (future feature)

2. **Consider cleanup strategy:**
   - Videos will accumulate on the volume
   - May want to implement video deletion feature later
   - Or set up automatic cleanup of videos older than X days

3. **Optional: Migrate to S3 later:**
   - Railway Volumes work great for now
   - Can migrate to AWS S3 later if you need:
     - Multi-region support
     - CDN integration
     - More flexible storage options

---

## Support

If you encounter issues:
- Check the debug endpoint: `/debug-media/`
- Review Railway logs for volume mount messages
- Verify volume is attached to the correct service
- Check that mount path matches `MEDIA_ROOT` setting

