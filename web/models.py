from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import default_storage


class VideoGenerationJob(models.Model):
    """Model to track video generation jobs in the database."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_jobs')
    paper_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percent = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, null=True, blank=True)
    progress_updated_at = models.DateTimeField(null=True, blank=True)  # Timestamp of last progress update
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=50, blank=True)
    task_id = models.CharField(max_length=255, unique=True)  # Celery task ID
    
    # Store video in cloud storage (R2) or local filesystem
    final_video = models.FileField(
        upload_to='videos/%Y/%m/%d/',  # Organize by date: videos/2025/01/28/
        blank=True,
        null=True,
        storage=default_storage,  # Will use R2 if USE_CLOUD_STORAGE=True, else local
    )
    
    # Keep final_video_path for backward compatibility during migration
    # This will store the storage path (e.g., "videos/2025/01/28/final_video.mp4")
    final_video_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['paper_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.paper_id} - {self.status}"

