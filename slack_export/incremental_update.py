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
    "newtools",
    "products-n-services",
    "workflow",
]

# File to store last update timestamp
LAST_UPDATE_FILE = "last_update.json"
DEFAULT_LOOKBACK_DAYS = 1  # How many days to look back if no last update file

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def load_last_update_time():
    """Load the timestamp of the last update"""
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
    """Save the timestamp of this update"""
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

def fetch_new_messages(channel_id, channel_name, since_timestamp):
    """Fetch only new messages since the given timestamp"""
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
            new_messages = [msg for msg in batch_messages if float(msg['ts']) > since_timestamp]
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

def update_channel(channel_name, since_timestamp, user_map):
    """Update a single channel with new messages"""
    print(f"\n🔄 Updating #{channel_name}...")
    
    # Get channel info
    channel_id, channel_info = get_channel_id_by_name(channel_name)
    if not channel_id:
        print(f"   ⚠️ Skipping {channel_name} (not found)")
        return 0
    
    # Fetch new messages
    messages = fetch_new_messages(channel_id, channel_name, since_timestamp)
    if not messages:
        print(f"   ✅ No new messages in #{channel_name}")
        return 0
    
    # Create chunks
    chunks = group_messages(messages, user_map, channel_info)
    if not chunks:
        print(f"   ⚠️ No valid chunks created from new messages")
        return 0
    
    print(f"   📦 Created {len(chunks)} new chunks")
    
    # Upload to Pinecone
    for idx, (chunk_id, chunk_text, timestamp) in enumerate(chunks, 1):
        embedding = get_embedding(chunk_text)
        
        metadata = {
            "channel_name": channel_name,
            "channel_id": channel_id,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "message_count": len(chunk_text.split('\n')),
            "timestamp": timestamp,
            "update_type": "incremental"
        }
        
        upsert_to_pinecone(chunk_id, embedding, chunk_text, metadata)
        time.sleep(0.1)  # Small delay
    
    print(f"   ✅ Uploaded {len(chunks)} new chunks from #{channel_name}")
    return len(chunks)

def main():
    print("🔄 Incremental Slack Export Update")
    print("=" * 40)
    
    # Get last update time
    last_update = load_last_update_time()
    last_update_readable = datetime.fromtimestamp(last_update).strftime("%Y-%m-%d %H:%M:%S")
    print(f"📅 Looking for messages since: {last_update_readable}")
    
    # Current time for this update
    current_time = time.time()
    
    # Fetch user map once
    print("\n👥 Fetching user information...")
    user_map = fetch_user_map()
    print(f"   ✅ Loaded {len(user_map)} users")
    
    # Update each channel
    total_new_chunks = 0
    for channel_name in CHANNELS_BY_NAME:
        try:
            new_chunks = update_channel(channel_name, last_update, user_map)
            total_new_chunks += new_chunks
        except Exception as e:
            print(f"   ❌ Error updating {channel_name}: {e}")
            continue
    
    # Save the current time as last update
    save_last_update_time(current_time)
    
    print(f"\n🎉 Incremental Update Complete!")
    print(f"   Total new chunks added: {total_new_chunks}")
    print(f"   Next update will look for messages since: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if total_new_chunks > 0:
        print(f"   🤖 Your bot now has access to the latest conversations!")
    else:
        print(f"   💤 No new conversations to add.")

if __name__ == "__main__":
    main() 