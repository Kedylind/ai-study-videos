#!/usr/bin/env python
"""
Script to run Django migrations on Railway database from local machine.

Usage:
1. Get your public DATABASE_URL from Railway:
   - Go to Railway → PostgreSQL service → "Connect" or "Variables" tab
   - Look for DATABASE_URL (should have a public hostname, not postgres.railway.internal)
   - It should look like: postgresql://postgres:password@containers-us-west-xxx.railway.app:5432/railway

2. Set it as an environment variable and run:
   python run_migrations.py

Or set it inline:
   $env:DATABASE_URL="your-public-url-here"; python run_migrations.py
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

# Setup Django
django.setup()

# Now we can import Django management commands
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # Check if DATABASE_URL is set
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set!")
        print("\nPlease set it first:")
        print("  PowerShell: $env:DATABASE_URL='your-database-url-here'")
        print("  Then run: python run_migrations.py")
        print("\nOr get it from Railway → PostgreSQL service → Variables tab")
        sys.exit(1)
    
    # Set DATABASE_SSL if not set
    if not os.getenv('DATABASE_SSL'):
        os.environ['DATABASE_SSL'] = 'True'
    
    print("Running migrations on Railway database...")
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print()
    
    # Run migrations
    execute_from_command_line(['manage.py', 'migrate'])

