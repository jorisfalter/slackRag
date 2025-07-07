#!/usr/bin/env python3
"""
Comprehensive status checker for the enhanced tracking system.
Shows current state, identifies issues, and provides recommendations.
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# File paths
LAST_UPDATE_FILE = "last_update.json"
CHANNEL_TRACKING_FILE = "channel_tracking.json"
PROCESSED_MESSAGES_FILE = "processed_messages.json"
MIGRATION_LOG_FILE = "migration_log.json"

def load_json_file(filepath):
    """Safely load a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        if timestamp:
            return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"
    except:
        return "Invalid"

def check_old_system():
    """Check old tracking system status"""
    print("📋 Old Tracking System Status")
    print("-" * 30)
    
    data = load_json_file(LAST_UPDATE_FILE)
    if data:
        last_update = data.get('last_update')
        readable = data.get('last_update_readable')
        
        print(f"✅ File exists: {LAST_UPDATE_FILE}")
        print(f"   Last update: {readable}")
        print(f"   Timestamp: {last_update}")
        
        if last_update:
            hours_ago = (datetime.now().timestamp() - float(last_update)) / 3600
            print(f"   Time ago: {hours_ago:.1f} hours")
            
            if hours_ago > 25:  # Should run daily
                print("   ⚠️ Warning: Last update was more than 25 hours ago")
            else:
                print("   ✅ Recent update detected")
    else:
        print(f"❌ File not found: {LAST_UPDATE_FILE}")
    
    print()

def check_enhanced_system():
    """Check enhanced tracking system status"""
    print("🔧 Enhanced Tracking System Status")
    print("-" * 35)
    
    # Check channel tracking
    channel_data = load_json_file(CHANNEL_TRACKING_FILE)
    if channel_data:
        print(f"✅ File exists: {CHANNEL_TRACKING_FILE}")
        print(f"   Channels tracked: {len(channel_data)}")
        
        print("   📊 Per-channel status:")
        for channel, info in channel_data.items():
            if isinstance(info, dict):
                last_update = info.get('last_update_readable', 'unknown')
                migrated = info.get('migrated_from_old_system', False)
                migration_flag = " (migrated)" if migrated else ""
                print(f"     #{channel}: {last_update}{migration_flag}")
            else:
                # Handle old format
                readable = format_timestamp(info)
                print(f"     #{channel}: {readable} (old format)")
    else:
        print(f"❌ File not found: {CHANNEL_TRACKING_FILE}")
    
    print()
    
    # Check processed messages
    processed_data = load_json_file(PROCESSED_MESSAGES_FILE)
    if processed_data:
        print(f"✅ File exists: {PROCESSED_MESSAGES_FILE}")
        count = processed_data.get('total_count', 0)
        last_updated = processed_data.get('last_updated', 'unknown')
        print(f"   Processed messages: {count}")
        print(f"   Last updated: {last_updated}")
        
        if count == 0:
            print("   ⚠️ No processed messages tracked yet")
        else:
            print("   ✅ Message tracking active")
    else:
        print(f"❌ File not found: {PROCESSED_MESSAGES_FILE}")
    
    print()

def check_migration_status():
    """Check migration status"""
    print("🔄 Migration Status")
    print("-" * 20)
    
    migration_data = load_json_file(MIGRATION_LOG_FILE)
    if migration_data:
        print(f"✅ Migration completed")
        print(f"   Date: {migration_data.get('migration_date', 'unknown')}")
        print(f"   Success: {migration_data.get('migration_success', False)}")
        
        old_system = migration_data.get('old_system', {})
        if old_system.get('file_existed'):
            print(f"   Preserved old timestamp: {old_system.get('last_update_readable', 'unknown')}")
        else:
            print(f"   No old data found, used default lookback")
    else:
        print(f"❌ No migration log found")
        print(f"   System may not have been migrated yet")
    
    print()

def analyze_system_health():
    """Analyze overall system health and provide recommendations"""
    print("🩺 System Health Analysis")
    print("-" * 25)
    
    issues = []
    recommendations = []
    
    # Check if enhanced system exists
    has_enhanced = os.path.exists(CHANNEL_TRACKING_FILE)
    has_old = os.path.exists(LAST_UPDATE_FILE)
    
    if not has_enhanced and not has_old:
        issues.append("No tracking system found")
        recommendations.append("Run initial export: python slack_export/export_multiple_channels.py")
    elif not has_enhanced and has_old:
        issues.append("Only old tracking system found")
        recommendations.append("Migrate to enhanced system: python utils/migrate_tracking.py")
    elif has_enhanced:
        print("✅ Enhanced tracking system detected")
        
        # Check for recent activity
        old_data = load_json_file(LAST_UPDATE_FILE)
        if old_data:
            last_update = old_data.get('last_update')
            if last_update:
                hours_ago = (datetime.now().timestamp() - float(last_update)) / 3600
                if hours_ago > 25:
                    issues.append(f"Last update was {hours_ago:.1f} hours ago")
                    recommendations.append("Check GitHub Actions workflow status")
        
        # Check processed messages
        processed_data = load_json_file(PROCESSED_MESSAGES_FILE)
        if processed_data and processed_data.get('total_count', 0) == 0:
            issues.append("No processed messages tracked")
            recommendations.append("Run incremental update to populate message tracking")
    
    if issues:
        print("⚠️ Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(f"   - {rec}")
    else:
        print("✅ System appears healthy")
    
    print()

def show_next_steps():
    """Show recommended next steps"""
    print("🚀 Next Steps")
    print("-" * 15)
    
    has_enhanced = os.path.exists(CHANNEL_TRACKING_FILE)
    
    if not has_enhanced:
        print("1. Migrate to enhanced system:")
        print("   python utils/migrate_tracking.py")
        print()
        print("2. Test enhanced incremental update:")
        print("   python slack_export/incremental_update.py")
    else:
        print("1. Check current status:")
        print("   python utils/check_update_status.py")
        print()
        print("2. Run manual incremental update:")
        print("   python slack_export/incremental_update.py")
        print()
        print("3. Inspect database for recent data:")
        print("   python utils/inspect_pinecone.py")
    
    print()

def main():
    print("🔍 Enhanced Tracking System Status Check")
    print("=" * 45)
    print()
    
    # Check all systems
    check_old_system()
    check_enhanced_system()
    check_migration_status()
    analyze_system_health()
    show_next_steps()
    
    print("=" * 45)
    print("Status check complete!")

if __name__ == "__main__":
    main() 