#!/usr/bin/env python3
"""
Fly.io persistent volume storage for tracking data.
Alternative to GitHub storage for production deployments.
"""

import os
import json
import shutil
from pathlib import Path

# Fly.io persistent volume mount point
FLY_VOLUME_PATH = "/data"  # Standard Fly.io volume mount point

def setup_fly_storage():
    """Setup Fly.io persistent storage"""
    if not os.path.exists(FLY_VOLUME_PATH):
        print(f"⚠️  Fly.io volume not mounted at {FLY_VOLUME_PATH}")
        print("   Add a volume to your Fly.io app:")
        print("   fly volumes create data --size 1")
        print("   Then update fly.toml with:")
        print("   [mounts]")
        print('     source = "data"')
        print('     destination = "/data"')
        return False
    
    tracking_dir = os.path.join(FLY_VOLUME_PATH, "tracking")
    os.makedirs(tracking_dir, exist_ok=True)
    print(f"✅ Fly.io storage ready at {tracking_dir}")
    return True

def save_to_fly_volume(filename, data):
    """Save tracking data to Fly.io persistent volume"""
    if not setup_fly_storage():
        return False
    
    try:
        volume_path = os.path.join(FLY_VOLUME_PATH, "tracking", filename)
        
        with open(volume_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Also save a local copy for current run
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Saved {filename} to Fly.io volume")
        return True
        
    except Exception as e:
        print(f"❌ Error saving to Fly.io volume: {e}")
        return False

def load_from_fly_volume(filename):
    """Load tracking data from Fly.io persistent volume"""
    volume_path = os.path.join(FLY_VOLUME_PATH, "tracking", filename)
    
    try:
        if os.path.exists(volume_path):
            with open(volume_path, 'r') as f:
                data = json.load(f)
            
            # Copy to local for current run
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Loaded {filename} from Fly.io volume")
            return data
        else:
            print(f"📄 {filename} not found in Fly.io volume")
            return None
            
    except Exception as e:
        print(f"❌ Error loading from Fly.io volume: {e}")
        return None

# Example usage in incremental_update.py:
"""
# At the start of incremental update:
if os.getenv('FLY_APP_NAME'):  # Running on Fly.io
    from utils.fly_storage import load_from_fly_volume, save_to_fly_volume
    
    # Load existing tracking data
    channel_data = load_from_fly_volume('channel_tracking.json')
    processed_data = load_from_fly_volume('processed_messages.json')
    
    # ... run update logic ...
    
    # Save updated tracking data
    save_to_fly_volume('channel_tracking.json', updated_channel_tracking)
    save_to_fly_volume('processed_messages.json', updated_processed_messages)
""" 