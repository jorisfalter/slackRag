#!/usr/bin/env python3
"""
Migration utility to transition from old tracking system to enhanced tracking system.
This ensures no data loss and provides a smooth upgrade path.
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuration
CHANNELS_BY_NAME = [
    "general",
    "madlicreative-admin",
    "bookkeeping--madlicreative",
    "creative",
    "madlicreative-marketing",
    "newtools",
    "products-n-services",
    "workflow",
]

# File paths
OLD_LAST_UPDATE_FILE = "last_update.json"
NEW_CHANNEL_TRACKING_FILE = "channel_tracking.json"
NEW_PROCESSED_MESSAGES_FILE = "processed_messages.json"
MIGRATION_LOG_FILE = "migration_log.json"

def load_old_tracking():
    """Load the old tracking system data"""
    try:
        if os.path.exists(OLD_LAST_UPDATE_FILE):
            with open(OLD_LAST_UPDATE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_update'), data.get('last_update_readable')
        return None, None
    except Exception as e:
        print(f"Error loading old tracking: {e}")
        return None, None

def create_enhanced_tracking(old_timestamp):
    """Create enhanced tracking files from old system"""
    
    # If we have old data, use it; otherwise use default lookback
    if old_timestamp:
        base_timestamp = float(old_timestamp)
        print(f"📅 Using existing timestamp: {datetime.fromtimestamp(base_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        # Default to 1 day ago
        lookback_time = datetime.now() - timedelta(days=1)
        base_timestamp = lookback_time.timestamp()
        print(f"📅 No existing timestamp, using default: {datetime.fromtimestamp(base_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create per-channel tracking
    channel_tracking = {}
    for channel in CHANNELS_BY_NAME:
        channel_tracking[channel] = {
            "last_update": base_timestamp,
            "last_update_readable": datetime.fromtimestamp(base_timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "migrated_from_old_system": True
        }
    
    # Create empty processed messages tracking
    processed_messages = {
        'processed_ids': [],
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_count': 0,
        'note': 'Initialized during migration - will populate during first enhanced run'
    }
    
    return channel_tracking, processed_messages

def save_enhanced_tracking(channel_tracking, processed_messages):
    """Save the new enhanced tracking files"""
    try:
        # Save channel tracking
        with open(NEW_CHANNEL_TRACKING_FILE, 'w') as f:
            json.dump(channel_tracking, f, indent=2)
        print(f"✅ Created {NEW_CHANNEL_TRACKING_FILE}")
        
        # Save processed messages
        with open(NEW_PROCESSED_MESSAGES_FILE, 'w') as f:
            json.dump(processed_messages, f, indent=2)
        print(f"✅ Created {NEW_PROCESSED_MESSAGES_FILE}")
        
        return True
    except Exception as e:
        print(f"❌ Error saving enhanced tracking: {e}")
        return False

def create_migration_log(old_timestamp, old_readable, success):
    """Create a log of the migration process"""
    migration_data = {
        'migration_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'old_system': {
            'last_update': old_timestamp,
            'last_update_readable': old_readable,
            'file_existed': old_timestamp is not None
        },
        'new_system': {
            'channels_tracked': len(CHANNELS_BY_NAME),
            'channels': CHANNELS_BY_NAME,
            'files_created': [NEW_CHANNEL_TRACKING_FILE, NEW_PROCESSED_MESSAGES_FILE]
        },
        'migration_success': success,
        'notes': [
            "Migration preserves existing timestamp for all channels",
            "Processed messages tracking starts fresh",
            "Old last_update.json file is preserved for backward compatibility"
        ]
    }
    
    try:
        with open(MIGRATION_LOG_FILE, 'w') as f:
            json.dump(migration_data, f, indent=2)
        print(f"✅ Created migration log: {MIGRATION_LOG_FILE}")
    except Exception as e:
        print(f"⚠️ Could not create migration log: {e}")

def main():
    print("🔄 Enhanced Tracking System Migration")
    print("=" * 50)
    
    # Check if new system already exists
    if os.path.exists(NEW_CHANNEL_TRACKING_FILE):
        print("✅ Enhanced tracking system already exists!")
        print(f"   Found: {NEW_CHANNEL_TRACKING_FILE}")
        
        # Show current status
        try:
            with open(NEW_CHANNEL_TRACKING_FILE, 'r') as f:
                data = json.load(f)
                print(f"   Channels tracked: {len(data)}")
                for channel, info in data.items():
                    if isinstance(info, dict):
                        print(f"     #{channel}: {info.get('last_update_readable', 'unknown')}")
        except Exception as e:
            print(f"   Error reading existing file: {e}")
        
        return
    
    # Load old system
    print("📋 Loading old tracking system...")
    old_timestamp, old_readable = load_old_tracking()
    
    if old_timestamp:
        print(f"✅ Found existing tracking data:")
        print(f"   Last update: {old_readable}")
    else:
        print("⚠️ No existing tracking data found")
        print("   Will initialize with default lookback period")
    
    # Create enhanced tracking
    print("\n🔧 Creating enhanced tracking system...")
    channel_tracking, processed_messages = create_enhanced_tracking(old_timestamp)
    
    # Save enhanced tracking
    print("\n💾 Saving enhanced tracking files...")
    success = save_enhanced_tracking(channel_tracking, processed_messages)
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("\n📊 New system features:")
        print("   ✅ Per-channel timestamp tracking")
        print("   ✅ Processed message ID tracking")
        print("   ✅ Enhanced error handling")
        print("   ✅ Waterproof deduplication")
        
        print(f"\n📋 Channels configured:")
        for channel in CHANNELS_BY_NAME:
            print(f"   #{channel}")
        
        print(f"\n📁 Files created:")
        print(f"   {NEW_CHANNEL_TRACKING_FILE}")
        print(f"   {NEW_PROCESSED_MESSAGES_FILE}")
        
        # Create migration log
        create_migration_log(old_timestamp, old_readable, True)
        
        print(f"\n🚀 Ready to use enhanced incremental updates!")
        print(f"   Run: python slack_export/incremental_update.py")
        
    else:
        print("\n❌ Migration failed!")
        create_migration_log(old_timestamp, old_readable, False)

if __name__ == "__main__":
    main() 