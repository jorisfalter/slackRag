import os
import sys
import time
import json
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils.embedding import get_embedding
from utils.pinecone_utils import upsert_to_pinecone
from dotenv import load_dotenv

load_dotenv()

# Configuration
CHANNELS_BY_NAME = [
    "general",
    "madlicreative-admin",
    "bookkeeping--madlicreative",
    "creative",
    "madlicreative-marketing",
    "products-n-services",
    "workflow",
]

# Enhanced tracking files
LAST_UPDATE_FILE = "last_update.json"
CHANNEL_TRACKING_FILE = "channel_tracking.json"
PROCESSED_MESSAGES_FILE = "processed_messages.json"
DEFAULT_LOOKBACK_DAYS = 1

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def load_channel_tracking():
    """Load per-channel timestamp tracking"""
    try:
        if os.path.exists(CHANNEL_TRACKING_FILE):
            with open(CHANNEL_TRACKING_FILE, 'r') as f:
                data = json.load(f)
                
                # Handle both old format (channel: timestamp) and new format (channel: {last_update: timestamp})
                normalized_data = {}
                for channel, value in data.items():
                    if isinstance(value, dict):
                        # New format: extract timestamp from nested structure
                        normalized_data[channel] = value.get('last_update', 0)
                    else:
                        # Old format: value is already the timestamp
                        normalized_data[channel] = value
                
                return normalized_data
        else:
            # Initialize with default lookback for all channels
            lookback_time = datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            default_timestamp = lookback_time.timestamp()
            return {channel: default_timestamp for channel in CHANNELS_BY_NAME}
    except Exception as e:
        print(f"Error loading channel tracking: {e}")
        # Fallback to default
        lookback_time = datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        default_timestamp = lookback_time.timestamp()
        return {channel: default_timestamp for channel in CHANNELS_BY_NAME}

def save_channel_tracking(tracking_data):
    """Save per-channel timestamp tracking"""
    try:
        # Add readable timestamps for debugging
        enhanced_data = {}
        for channel, timestamp in tracking_data.items():
            if isinstance(timestamp, (int, float)):
                enhanced_data[channel] = {
                    "last_update": float(timestamp),
                    "last_update_readable": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    "last_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                print(f"Warning: Invalid timestamp for {channel}: {timestamp}")
                # Use current time as fallback
                current_time = time.time()
                enhanced_data[channel] = {
                    "last_update": current_time,
                    "last_update_readable": datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "last_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "Fallback timestamp due to invalid data"
                }
        
        with open(CHANNEL_TRACKING_FILE, 'w') as f:
            json.dump(enhanced_data, f, indent=2)
        print(f"✅ Saved channel tracking data")
    except Exception as e:
        print(f"Error saving channel tracking: {e}")

def load_processed_messages():
    """Load set of already processed message IDs"""
    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_ids', []))
        return set()
    except Exception as e:
        print(f"Error loading processed messages: {e}")
        return set()

def save_processed_messages(processed_ids, max_keep=10000):
    """Save processed message IDs (keep only recent ones)"""
    try:
        # Convert set to list and keep only the most recent
        id_list = list(processed_ids)
        if len(id_list) > max_keep:
            id_list = id_list[-max_keep:]  # Keep the last N
        
        data = {
            'processed_ids': id_list,
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_count': len(id_list)
        }
        
        with open(PROCESSED_MESSAGES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved {len(id_list)} processed message IDs")
    except Exception as e:
        print(f"Error saving processed messages: {e}")

def load_last_update_time():
    """Load the timestamp of the last update (for backward compatibility)"""
    try:
        if os.path.exists(LAST_UPDATE_FILE):
            with open(LAST_UPDATE_FILE, 'r') as f:
                data = json.load(f)
                return float(data.get('last_update', 0))
        else:
            # If no file exists, look back DEFAULT_LOOKBACK_DAYS
            lookback_time = datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            return lookback_time.timestamp()
    except Exception as e:
        print(f"Error loading last update time: {e}")
        # Fallback to 1 day ago
        lookback_time = datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        return lookback_time.timestamp()

def save_last_update_time(timestamp):
    """Save the timestamp of this update (for backward compatibility)"""
    try:
        data = {
            'last_update': timestamp,
            'last_update_readable': datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(LAST_UPDATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved last update time: {data['last_update_readable']}")
    except Exception as e:
        print(f"Error saving last update time: {e}")

def get_channel_id_by_name(channel_name):
    """Get channel ID by channel name"""
    try:
        channel_name = channel_name.lstrip('#')
        response = client.conversations_list(types="public_channel,private_channel")
        for channel in response['channels']:
            if channel['name'] == channel_name:
                return channel['id'], channel
        return None, None
    except SlackApiError as e:
        print(f"❌ Error looking up channel '{channel_name}': {e.response['error']}")
        return None, None

def fetch_new_messages(channel_id, channel_name, since_timestamp, processed_ids):
    """Fetch only new messages since the given timestamp, excluding already processed ones"""
    messages = []
    cursor = None
    
    print(f"📥 Fetching new messages from #{channel_name} since {datetime.fromtimestamp(since_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    while True:
        try:
            response = client.conversations_history(
                channel=channel_id, 
                cursor=cursor, 
                limit=100,
                oldest=str(since_timestamp)  # Only get messages newer than this
            )
            
            batch_messages = response['messages']
            print(f"   📦 Fetched {len(batch_messages)} messages")
            
            # Filter out messages that are exactly at the timestamp (to avoid duplicates)
            # AND filter out already processed messages
            new_messages = [
                msg for msg in batch_messages 
                if float(msg['ts']) > since_timestamp and msg['ts'] not in processed_ids
            ]
            messages.extend(new_messages)
            
            if not response.get('has_more'):
                break
                
            cursor = response['response_metadata']['next_cursor']
            time.sleep(1)  # Rate limiting
            
        except SlackApiError as e:
            print(f"   ❌ Error fetching messages: {e.response['error']}")
            break
    
    # Sort by timestamp (oldest first)
    messages.sort(key=lambda x: float(x['ts']))
    print(f"📊 Total new messages from #{channel_name}: {len(messages)}")
    return messages

def fetch_user_map():
    """Fetch user information (cached approach could be added later)"""
    user_map = {}
    try:
        response = client.users_list()
        for user in response['members']:
            user_map[user['id']] = user['profile'].get('display_name') or user['profile'].get('real_name') or user['name']
    except SlackApiError as e:
        print(f"❌ Error fetching users: {e.response['error']}")
    return user_map

def group_messages(messages, user_map, channel_info, window_size=5, overlap=2):
    """Group messages into conversation chunks"""
    if not messages:
        return []
    
    chunks = []
    i = 0
    while i < len(messages):
        window = messages[i:i+window_size]
        chunk_lines = []
        for msg in window:
            if 'text' in msg and 'user' in msg:
                username = user_map.get(msg['user'], msg['user'])
                chunk_lines.append(f"[{username}]: {msg['text']}")
        
        if chunk_lines:
            chunk_text = "\n".join(chunk_lines)
            # Use timestamp + channel for unique ID
            chunk_id = f"{channel_info['id']}_{window[0]['ts']}_incremental"
            chunks.append((chunk_id, chunk_text, window[0]['ts']))
        
        i += window_size - overlap
    
    return chunks

def update_channel(channel_name, since_timestamp, user_map, processed_ids):
    """Update a single channel with new messages"""
    print(f"\n🔄 Updating #{channel_name}...")
    
    # Get channel info
    channel_id, channel_info = get_channel_id_by_name(channel_name)
    if not channel_id:
        print(f"   ⚠️ Skipping {channel_name} (not found)")
        return 0, since_timestamp, set()
    
    # Fetch new messages
    messages = fetch_new_messages(channel_id, channel_name, since_timestamp, processed_ids)
    if not messages:
        print(f"   ✅ No new messages in #{channel_name}")
        return 0, since_timestamp, set()
    
    # Create chunks
    chunks = group_messages(messages, user_map, channel_info)
    if not chunks:
        print(f"   ⚠️ No valid chunks created from new messages")
        return 0, since_timestamp, set()
    
    print(f"   📦 Created {len(chunks)} new chunks")
    
    # Track processed message IDs and find latest timestamp
    new_processed_ids = set()
    latest_timestamp = since_timestamp
    
    # Upload to Pinecone
    for idx, (chunk_id, chunk_text, timestamp) in enumerate(chunks, 1):
        try:
            embedding = get_embedding(chunk_text)
            
            metadata = {
                "channel_name": channel_name,
                "channel_id": channel_id,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "message_count": len(chunk_text.split('\n')),
                "timestamp": timestamp,
                "update_type": "incremental",
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            upsert_to_pinecone(chunk_id, embedding, chunk_text, metadata)
            
            # Track the message IDs in this chunk
            # We need to extract message timestamps from the chunk
            chunk_messages = [msg for msg in messages if msg['ts'] in chunk_text or abs(float(msg['ts']) - float(timestamp)) < 1.0]
            for msg in chunk_messages:
                new_processed_ids.add(msg['ts'])
                latest_timestamp = max(latest_timestamp, float(msg['ts']))
            
            time.sleep(0.1)  # Small delay
            
        except Exception as e:
            print(f"   ❌ Error processing chunk {idx}: {e}")
            continue
    
    print(f"   ✅ Uploaded {len(chunks)} new chunks from #{channel_name}")
    print(f"   📊 Processed {len(new_processed_ids)} message IDs")
    print(f"   ⏰ Latest message timestamp: {datetime.fromtimestamp(latest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    return len(chunks), latest_timestamp, new_processed_ids

def main():
    print("🔄 Enhanced Incremental Slack Export Update")
    print("=" * 50)
    
    # Load tracking data
    channel_tracking = load_channel_tracking()
    processed_ids = load_processed_messages()
    
    print(f"📊 Loaded tracking data:")
    print(f"   Channels tracked: {len(channel_tracking)}")
    print(f"   Previously processed messages: {len(processed_ids)}")
    
    # Current time for this update
    current_time = time.time()
    
    # Fetch user map once
    print("\n👥 Fetching user information...")
    user_map = fetch_user_map()
    print(f"   ✅ Loaded {len(user_map)} users")
    
    # Update each channel individually
    total_new_chunks = 0
    updated_tracking = {}
    all_new_processed_ids = set()
    
    for channel_name in CHANNELS_BY_NAME:
        try:
            since_timestamp = channel_tracking.get(channel_name, current_time - (DEFAULT_LOOKBACK_DAYS * 24 * 3600))
            
            print(f"\n📅 #{channel_name}: Looking for messages since {datetime.fromtimestamp(since_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
            
            new_chunks, latest_timestamp, new_processed_ids = update_channel(
                channel_name, since_timestamp, user_map, processed_ids
            )
            
            total_new_chunks += new_chunks
            updated_tracking[channel_name] = latest_timestamp
            all_new_processed_ids.update(new_processed_ids)
            
        except Exception as e:
            print(f"   ❌ Error updating {channel_name}: {e}")
            # Keep the old timestamp for this channel
            updated_tracking[channel_name] = channel_tracking.get(channel_name, current_time)
            continue
    
    # Update processed IDs
    processed_ids.update(all_new_processed_ids)
    
    # Save all tracking data
    save_channel_tracking(updated_tracking)
    save_processed_messages(processed_ids)
    save_last_update_time(current_time)  # For backward compatibility
    
    # Commit tracking data to GitHub (if running in GitHub Actions)
    if os.getenv('GITHUB_ACTIONS'):
        print(f"\n💾 Saving tracking data to GitHub repository...")
        try:
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            from utils.github_storage import setup_github_token, commit_tracking_files_to_github
            
            setup_github_token()
            commit_tracking_files_to_github()
        except Exception as e:
            print(f"⚠️  Could not commit tracking data to GitHub: {e}")
            print("   Tracking data saved locally but may be lost between runs")
    
    print(f"\n🎉 Enhanced Incremental Update Complete!")
    print(f"   Total new chunks added: {total_new_chunks}")
    print(f"   New message IDs processed: {len(all_new_processed_ids)}")
    print(f"   Total tracked message IDs: {len(processed_ids)}")
    
    # Show per-channel summary
    print(f"\n📊 Per-Channel Summary:")
    for channel, timestamp in updated_tracking.items():
        readable_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"   #{channel}: Next update from {readable_time}")
    
    if total_new_chunks > 0:
        print(f"\n🤖 Your bot now has access to the latest conversations!")
    else:
        print(f"\n💤 No new conversations to add.")

if __name__ == "__main__":
    main() 