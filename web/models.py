from django.db import models
from django.contrib.auth.models import User


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
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=50, blank=True)
    task_id = models.CharField(max_length=255, unique=True)  # Celery task ID
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

