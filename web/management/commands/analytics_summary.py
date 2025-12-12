"""
Management command to generate analytics summary for A/B testing.

Usage:
    python manage.py analytics_summary
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from web.models import ABTestEvent


class Command(BaseCommand):
    help = 'Generate analytics summary for A/B test endpoint'

    def handle(self, *args, **options):
        # Get impression and click counts by variant
        impressions_a = ABTestEvent.objects.filter(
            event_type='impression', variant='A'
        ).count()
        impressions_b = ABTestEvent.objects.filter(
            event_type='impression', variant='B'
        ).count()
        clicks_a = ABTestEvent.objects.filter(
            event_type='click', variant='A'
        ).count()
        clicks_b = ABTestEvent.objects.filter(
            event_type='click', variant='B'
        ).count()
        
        # Calculate click-through rates
        ctr_a = (clicks_a / impressions_a * 100) if impressions_a > 0 else 0
        ctr_b = (clicks_b / impressions_b * 100) if impressions_b > 0 else 0
        
        # Determine preferred variant
        if ctr_a > ctr_b:
            preferred = 'Variant A (kudos)'
        elif ctr_b > ctr_a:
            preferred = 'Variant B (thanks)'
        else:
            preferred = 'Tie (equal CTR)'
        
        # Output summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('A/B Test Analytics Summary'))
        self.stdout.write('='*60)
        self.stdout.write('\nVariant A (kudos):')
        self.stdout.write(f'  Impressions: {impressions_a}')
        self.stdout.write(f'  Clicks: {clicks_a}')
        self.stdout.write(f'  CTR: {ctr_a:.2f}%')
        self.stdout.write('\nVariant B (thanks):')
        self.stdout.write(f'  Impressions: {impressions_b}')
        self.stdout.write(f'  Clicks: {clicks_b}')
        self.stdout.write(f'  CTR: {ctr_b:.2f}%')
        self.stdout.write('\n' + '-'*60)
        self.stdout.write(self.style.SUCCESS(f'Preferred Variant: {preferred}'))
        self.stdout.write('='*60 + '\n')

