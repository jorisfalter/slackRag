#!/usr/bin/env python3
"""
Utility to reset channel tracking timestamps to capture missed messages.
This fixes the issue where timestamps were set too far in the future.
"""

import json
import os
from datetime import datetime, timedelta

def reset_channel_timestamps():
    """Reset channel tracking timestamps to capture missed messages"""
    
    # Set timestamp to June 30th to capture all messages from July 1st onwards
    reset_date = datetime(2025, 6, 30, 0, 0, 0)
    reset_timestamp = reset_date.timestamp()
    
    print(f"🔄 Resetting all channel timestamps to: {reset_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   This will capture all messages from July 1st onwards")
    
    # Channels to reset
    channels = [
        "general",
        "madlicreative-admin",
        "bookkeeping--madlicreative",
        "creative", 
        "madlicreative-marketing",
        "products-n-services",
        "workflow"
    ]
    
    # Create new tracking data
    tracking_data = {}
    for channel in channels:
        tracking_data[channel] = {
            "last_update": reset_timestamp,
            "last_update_readable": reset_date.strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Reset to capture missed messages from July 1-3"
        }
    
    # Save to file
    with open('channel_tracking.json', 'w') as f:
        json.dump(tracking_data, f, indent=2)
    
    print(f"✅ Updated channel_tracking.json")
    
    # Also clear processed messages to avoid conflicts
    processed_data = {
        'processed_ids': [],
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_count': 0,
        'note': 'Cleared to allow reprocessing of missed messages'
    }
    
    with open('processed_messages.json', 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print(f"✅ Cleared processed_messages.json")
    
    print(f"\n🎯 Next steps:")
    print(f"   1. Run incremental update to capture missed messages")
    print(f"   2. Check that messages from July 1-3 are processed")
    print(f"   3. Verify Pinecone database contains the new messages")

if __name__ == "__main__":
    reset_channel_timestamps() 