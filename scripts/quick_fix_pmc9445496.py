#!/usr/bin/env python
"""
Quick fix script to update PMC9445496 database record with correct R2 path.
"""
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # Go up from scripts/ to project root
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from web.models import VideoGenerationJob
from django.core.files.storage import default_storage

# Exact path from R2 storage
VIDEO_PATH = "videos/2025/12/03/PMC9445496_final_video_20251203_055306.mp4"
PMID = "PMC9445496"

print(f"Fixing database record for {PMID}...")
print(f"Setting path to: {VIDEO_PATH}\n")

job = VideoGenerationJob.objects.filter(paper_id=PMID).order_by('-created_at').first()

if not job:
    print(f"❌ No job found for {PMID}")
    sys.exit(1)

print(f"Found job ID: {job.id}")
print(f"Current final_video_path: {job.final_video_path or 'EMPTY'}")
print(f"Current final_video: {job.final_video.name if job.final_video else 'EMPTY'}\n")

# Verify file exists
if default_storage.exists(VIDEO_PATH):
    print(f"✅ File exists in R2 storage")
    try:
        size = default_storage.size(VIDEO_PATH)
        print(f"   File size: {size:,} bytes ({size/1024/1024:.2f} MB)\n")
    except:
        pass
else:
    print(f"❌ File NOT found in R2 storage at: {VIDEO_PATH}")
    print("   Please verify the path is correct.")
    sys.exit(1)

# Update database
print("Updating database...")
job.final_video_path = VIDEO_PATH

# Try to set FileField
try:
    from django.core.files import File
    with default_storage.open(VIDEO_PATH, 'rb') as f:
        django_file = File(f, name=os.path.basename(VIDEO_PATH))
        job.final_video.save(os.path.basename(VIDEO_PATH), django_file, save=False)
    print("   Set final_video FileField")
except Exception as e:
    print(f"   Warning: Could not set FileField: {e}")

job.save(update_fields=['final_video', 'final_video_path', 'updated_at'])

print("\n✅ SUCCESS! Database updated.")
print(f"   final_video_path: {job.final_video_path}")
print(f"   final_video: {job.final_video.name if job.final_video else 'NOT SET'}")
print("\nThe video should now be accessible!")
