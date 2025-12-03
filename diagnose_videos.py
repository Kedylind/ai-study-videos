#!/usr/bin/env python
"""Diagnostic script to compare video records in database."""
import os
import sys
import django
from pathlib import Path

# Add project directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from web.models import VideoGenerationJob
from django.core.files.storage import default_storage

def diagnose_video(pmid):
    """Diagnose a video record."""
    print(f"\n{'='*60}")
    print(f"Diagnosing video: {pmid}")
    print(f"{'='*60}")
    
    # Get all jobs for this paper
    jobs = VideoGenerationJob.objects.filter(paper_id=pmid).order_by('-created_at')
    
    if not jobs.exists():
        print(f"❌ No jobs found for {pmid}")
        return
    
    print(f"Found {jobs.count()} job(s) for {pmid}\n")
    
    for i, job in enumerate(jobs, 1):
        print(f"--- Job #{i} (ID: {job.id}) ---")
        print(f"User: {job.user.username} (ID: {job.user.id})")
        print(f"Status: {job.status}")
        print(f"Progress: {job.progress_percent}%")
        print(f"Task ID: {job.task_id}")
        print(f"Created: {job.created_at}")
        print(f"Completed: {job.completed_at}")
        print(f"\nVideo Fields:")
        print(f"  final_video (FileField): {job.final_video}")
        print(f"  final_video.name: {job.final_video.name if job.final_video else 'None'}")
        print(f"  final_video_path: {job.final_video_path}")
        
        # Check if files exist in storage
        print(f"\nStorage Checks:")
        if job.final_video and job.final_video.name:
            try:
                exists = job.final_video.storage.exists(job.final_video.name)
                print(f"  final_video.name exists in storage: {exists}")
                if exists:
                    try:
                        size = job.final_video.storage.size(job.final_video.name)
                        print(f"  File size: {size:,} bytes ({size/1024/1024:.2f} MB)")
                    except Exception as e:
                        print(f"  Could not get file size: {e}")
            except Exception as e:
                print(f"  Error checking final_video: {e}")
        
        if job.final_video_path:
            try:
                exists = default_storage.exists(job.final_video_path)
                print(f"  final_video_path exists in storage: {exists}")
                if exists:
                    try:
                        size = default_storage.size(job.final_video_path)
                        print(f"  File size: {size:,} bytes ({size/1024/1024:.2f} MB)")
                    except Exception as e:
                        print(f"  Could not get file size: {e}")
            except Exception as e:
                print(f"  Error checking final_video_path: {e}")
        
        print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python diagnose_videos.py <pmid1> [pmid2] ...")
        print("\nExample:")
        print("  python diagnose_videos.py PMC9445496 PMC10979640")
        sys.exit(1)
    
    for pmid in sys.argv[1:]:
        diagnose_video(pmid)
