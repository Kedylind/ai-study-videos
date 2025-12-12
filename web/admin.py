from django.contrib import admin
from .models import VideoGenerationJob, ABTestEvent


@admin.register(VideoGenerationJob)
class VideoGenerationJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'paper_id', 'status', 'progress_percent', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['paper_id', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ABTestEvent)
class ABTestEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_type', 'variant', 'session_id', 'created_at']
    list_filter = ['event_type', 'variant', 'created_at']
    search_fields = ['session_id', 'ip_address']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related()
    
    # Add action to view analytics summary
    actions = ['view_analytics_summary']
    
    def view_analytics_summary(self, request, queryset):
        """Display analytics summary in admin."""
        from django.db.models import Count
        from django.utils.html import format_html
        
        # Group by event type and variant
        summary = queryset.values('event_type', 'variant').annotate(
            count=Count('id')
        ).order_by('event_type', 'variant')
        
        # Calculate click-through rates
        impressions_a = queryset.filter(event_type='impression', variant='A').count()
        impressions_b = queryset.filter(event_type='impression', variant='B').count()
        clicks_a = queryset.filter(event_type='click', variant='A').count()
        clicks_b = queryset.filter(event_type='click', variant='B').count()
        
        ctr_a = (clicks_a / impressions_a * 100) if impressions_a > 0 else 0
        ctr_b = (clicks_b / impressions_b * 100) if impressions_b > 0 else 0
        
        result = format_html(
            '<h3>Analytics Summary</h3>'
            '<table style="border-collapse: collapse; width: 100%;">'
            '<tr><th style="border: 1px solid #ddd; padding: 8px;">Metric</th>'
            '<th style="border: 1px solid #ddd; padding: 8px;">Variant A (kudos)</th>'
            '<th style="border: 1px solid #ddd; padding: 8px;">Variant B (thanks)</th></tr>'
            '<tr><td style="border: 1px solid #ddd; padding: 8px;">Impressions</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{}</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{}</td></tr>'
            '<tr><td style="border: 1px solid #ddd; padding: 8px;">Clicks</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{}</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{}</td></tr>'
            '<tr><td style="border: 1px solid #ddd; padding: 8px;">CTR</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{:.2f}%</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{:.2f}%</td></tr>'
            '</table>'
            '<br><strong>Preferred Variant:</strong> {}',
            impressions_a, impressions_b,
            clicks_a, clicks_b,
            ctr_a, ctr_b,
            'Variant A (kudos)' if ctr_a > ctr_b else 'Variant B (thanks)' if ctr_b > ctr_a else 'Tie'
        )
        
        self.message_user(request, result)
    view_analytics_summary.short_description = "View analytics summary for selected events"

