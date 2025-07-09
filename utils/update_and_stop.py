#!/usr/bin/env python3
"""
One-shot updater script for Fly.io scheduled machines
Runs the incremental update and then exits
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import and run the incremental update
from slack_export.incremental_update import main

if __name__ == "__main__":
    print("🚀 Starting scheduled Slack database update...")
    try:
        main()
        print("✅ Update completed successfully")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Update failed: {e}")
        sys.exit(1) 