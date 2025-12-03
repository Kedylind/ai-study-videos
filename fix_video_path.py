#!/usr/bin/env python
"""
Script to fix video database records by setting final_video_path from R2 storage.

Usage:
    python fix_video_path.py PMC9445496
"""
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
from django.conf import settings
from django.core.files.storage import default_storage

def fix_video_path(pmid, video_path=None):
    """Fix video database record by setting final_video_path."""
    print(f"\n{'='*60}")
    print(f"Fixing video record for: {pmid}")
    print(f"{'='*60}\n")
    
    # Get the job
    job = VideoGenerationJob.objects.filter(paper_id=pmid).order_by('-created_at').first()
    
    if not job:
        print(f"❌ No job found for {pmid}")
        return False
    
    print(f"Found job: ID={job.id}, Status={job.status}")
    print(f"Current final_video: {job.final_video.name if job.final_video else 'EMPTY'}")
    print(f"Current final_video_path: {job.final_video_path or 'EMPTY'}\n")
    
    # If path provided, use it
    if video_path:
        print(f"Using provided path: {video_path}")
        target_path = video_path
    else:
        # Try to find the video in R2 storage
        # Common patterns based on date
        from datetime import datetime
        now = datetime.now()
        possible_paths = [
            f"videos/{now.year}/{now.month:02d}/{now.day:02d}/{pmid}_final_video_*.mp4",
            f"videos/{now.year}/{now.month:02d}/{now.day:02d}/{pmid}_final_video_*{now.year}{now.month:02d}{now.day:02d}*.mp4",
        ]
        
        # Try exact path from completed_at date
        if job.completed_at:
            completed = job.completed_at
            exact_path = f"videos/{completed.year}/{completed.month:02d}/{completed.day:02d}/{pmid}_final_video_{completed.strftime('%Y%m%d')}*.mp4"
            possible_paths.insert(0, exact_path)
        
        print("Searching for video in R2 storage...")
        target_path = None
        
        # List files in R2 to find the video
        try:
            # List all files in videos directory for this paper
            video_files = []
            if hasattr(default_storage, 'listdir'):
                try:
                    # Try to list files in videos directory
                    dirs, files = default_storage.listdir('videos')
                    for subdir in dirs:
                        try:
                            subdirs2, files2 = default_storage.listdir(f'videos/{subdir}')
                            for file in files2:
                                if pmid in file and file.endswith('.mp4'):
                                    full_path = f'videos/{subdir}/{file}'
                                    video_files.append(full_path)
                        except:
                            pass
                except:
                    pass
        except Exception as e:
            print(f"Could not list files: {e}")
        
        if not video_files:
            print("❌ Could not find video file automatically.")
            print("\nPlease provide the exact path from R2 storage:")
            print("Example: videos/2025/12/03/PMC9445496_final_video_20251203_055306.mp4")
            return False
    
    # Verify file exists in storage
    print(f"\nVerifying file exists: {target_path}")
    if not default_storage.exists(target_path):
        print(f"❌ File not found in storage: {target_path}")
        return False
    
    print(f"✅ File found in storage!")
    
    # Get file size
    try:
        size = default_storage.size(target_path)
        print(f"   Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
    except:
        pass
    
    # Update database
    print(f"\nUpdating database record...")
    job.final_video_path = target_path
    
    # Try to set FileField as well
    try:
        # Open the file and save to FileField
        with default_storage.open(target_path, 'rb') as f:
            from django.core.files import File
            django_file = File(f, name=os.path.basename(target_path))
            job.final_video.save(os.path.basename(target_path), django_file, save=False)
    except Exception as e:
        print(f"   Warning: Could not set final_video FileField: {e}")
    
    # Save the record
    job.save(update_fields=['final_video', 'final_video_path', 'updated_at'])
    
    print(f"✅ Database updated successfully!")
    print(f"   final_video_path: {job.final_video_path}")
    print(f"   final_video: {job.final_video.name if job.final_video else 'NOT SET'}")
    
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_video_path.py <pmid> [video_path]")
        print("\nExample:")
        print("  python fix_video_path.py PMC9445496")
        print("  python fix_video_path.py PMC9445496 videos/2025/12/03/PMC9445496_final_video_20251203_055306.mp4")
        sys.exit(1)
    
    pmid = sys.argv[1]
    video_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = fix_video_path(pmid, video_path)
    sys.exit(0 if success else 1)
