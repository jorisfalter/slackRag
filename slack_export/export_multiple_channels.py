import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils.embedding import get_embedding
from utils.pinecone_utils import upsert_to_pinecone
from dotenv import load_dotenv

load_dotenv()

# Configuration
TEST_MODE = False  # Set to True to only fetch a few messages for testing
MAX_TEST_MESSAGES = 30

# Channels to export - Add your channel IDs here
CHANNELS_TO_EXPORT = [
    # Add channel IDs like this:
    # "C1234567890",  # general
    # "C0987654321",  # random
    # "C1111111111",  # project-alpha
]

# You can also specify channels by name if you prefer
# The script will look them up automatically
CHANNELS_BY_NAME = [
    # Add channel names like this (remove the # symbol):
    "general",                      # Main discussion channel
    "madlicreative-admin",         # Admin discussions
    "bookkeeping--madlicreative",  # Bookkeeping topics
    "creative",                    # Creative work
    "madlicreative-marketing",     # Marketing discussions
    "newtools",                    # New tools and tech
    "products-n-services",         # Products and services
    "workflow",                    # Workflow discussions
    # "project-alpha",             # Uncomment to add more channels
]

print(f"PINECONE_API_KEY loaded: {os.getenv('PINECONE_API_KEY') is not None}")
print(f"PINECONE_INDEX loaded: {os.getenv('PINECONE_INDEX') is not None}")
print(f"SLACK_BOT_TOKEN loaded: {os.getenv('SLACK_BOT_TOKEN') is not None}")
print(f"OPENAI_API_KEY loaded: {os.getenv('OPENAI_API_KEY') is not None}")

if TEST_MODE:
    print(f"\n🧪 TEST MODE: Only fetching {MAX_TEST_MESSAGES} messages per channel")

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def get_channel_id_by_name(channel_name):
    """Get channel ID by channel name"""
    try:
        # Remove # if present
        channel_name = channel_name.lstrip('#')
        
        # Search in public channels
        response = client.conversations_list(types="public_channel,private_channel")
        for channel in response['channels']:
            if channel['name'] == channel_name:
                return channel['id'], channel
        
        print(f"❌ Channel '{channel_name}' not found")
        return None, None
    except SlackApiError as e:
        print(f"❌ Error looking up channel '{channel_name}': {e.response['error']}")
        return None, None

def test_bot_connection():
    """Test if the bot token is valid"""
    try:
        response = client.auth_test()
        print(f"✅ Bot connection successful!")
        print(f"   Bot User ID: {response['user_id']}")
        print(f"   Team: {response['team']}")
        return True, response['user_id']
    except SlackApiError as e:
        print(f"❌ Bot connection failed: {e.response['error']}")
        return False, None

def test_channel_access(channel_id):
    """Test if the bot can access the channel"""
    try:
        response = client.conversations_info(channel=channel_id)
        print(f"✅ Channel access successful!")
        print(f"   Channel name: #{response['channel']['name']}")
        print(f"   Channel ID: {response['channel']['id']}")
        return response['channel']
    except SlackApiError as e:
        print(f"❌ Channel access failed: {e.response['error']}")
        return None

def test_bot_in_channel(channel_id, bot_user_id):
    """Test if the bot is a member of the channel"""
    try:
        response = client.conversations_members(channel=channel_id)
        members = response['members']
        if bot_user_id in members:
            print(f"✅ Bot is a member of this channel!")
            return True
        else:
            print(f"❌ Bot is NOT a member of this channel.")
            print(f"   Add the bot to the channel by typing: /invite @ExportSlack")
            return False
    except SlackApiError as e:
        print(f"❌ Could not check channel membership: {e.response['error']}")
        return False

def fetch_channel_messages(channel_id, channel_name):
    """Fetch messages from a specific channel"""
    messages = []
    cursor = None
    call_count = 0
    
    print(f"📥 Starting to fetch messages from #{channel_name} ({channel_id})")
    if TEST_MODE:
        print(f"🧪 TEST MODE: Will stop after {MAX_TEST_MESSAGES} messages")
    
    while True:
        call_count += 1
        print(f"   API call #{call_count} - Fetching messages...")
        
        try:
            response = client.conversations_history(channel=channel_id, cursor=cursor, limit=100)
            print(f"   ✅ Successfully fetched {len(response['messages'])} messages")
            messages.extend(response['messages'])
            
            # Check if we've reached our test limit
            if TEST_MODE and len(messages) >= MAX_TEST_MESSAGES:
                print(f"   🧪 TEST MODE: Reached {len(messages)} messages, stopping here")
                break
            
            if not response.get('has_more'):
                print(f"   ✅ No more messages to fetch from #{channel_name}")
                break
                
            cursor = response['response_metadata']['next_cursor']
            
            # Rate limiting
            if TEST_MODE:
                print("   Waiting 2 seconds before next call (test mode)...")
                time.sleep(2)
            else:
                print("   Waiting 30 seconds before next call...")
                time.sleep(30)
            
        except SlackApiError as e:
            print(f"   ❌ Slack API Error: {e.response['error']}")
            
            if e.response['error'] == 'ratelimited':
                retry_after = getattr(e.response, 'headers', {}).get('Retry-After', 120)
                print(f"   Rate limited, waiting {retry_after} seconds...")
                time.sleep(int(retry_after) + 5)
            else:
                print(f"   Non-rate-limit error: {e}")
                break
                
    # Sort messages by timestamp (oldest first)
    messages.sort(key=lambda x: float(x['ts']))
    print(f"📊 Total messages fetched from #{channel_name}: {len(messages)}")
    return messages

def fetch_user_map():
    """Fetch user information once for all channels"""
    user_map = {}
    cursor = None
    call_count = 0
    
    print("👥 Fetching user information...")
    
    while True:
        call_count += 1
        print(f"   User API call #{call_count}...")
        
        try:
            response = client.users_list(cursor=cursor)
            print(f"   ✅ Successfully fetched {len(response['members'])} users")
            
            for user in response['members']:
                user_map[user['id']] = user['profile'].get('display_name') or user['profile'].get('real_name') or user['name']
            
            if not response.get('response_metadata', {}).get('next_cursor'):
                print("   ✅ No more users to fetch")
                break
                
            cursor = response['response_metadata']['next_cursor']
            
            # Rate limiting
            print("   Waiting 30 seconds before next user call...")
            time.sleep(30)
            
        except SlackApiError as e:
            print(f"   ❌ User API Error: {e.response['error']}")
            
            if e.response['error'] == 'ratelimited':
                print("   Rate limited on users. Waiting 120 seconds...")
                time.sleep(120)
            else:
                print(f"   Non-rate-limit error: {e}")
                break
                
    print(f"👥 Total users fetched: {len(user_map)}")
    return user_map

def group_messages(messages, user_map, channel_info, window_size=5, overlap=2):
    """Group messages into conversation chunks"""
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
            chunk_id = f"{channel_info['id']}_{window[0]['ts']}"  # Include channel ID in chunk ID
            chunks.append((chunk_id, chunk_text))
        i += window_size - overlap
    return chunks

def process_channel(channel_id, channel_info, user_map):
    """Process a single channel: fetch messages, create chunks, upload to Pinecone"""
    channel_name = channel_info['name']
    print(f"\n🔄 Processing #{channel_name}...")
    
    # Fetch messages
    messages = fetch_channel_messages(channel_id, channel_name)
    if not messages:
        print(f"   ⚠️ No messages found in #{channel_name}")
        return 0
    
    # Create conversation chunks
    chunks = group_messages(messages, user_map, channel_info, window_size=5, overlap=2)
    print(f"   📦 Created {len(chunks)} conversation chunks")
    
    # Upload to Pinecone
    for idx, (chunk_id, chunk_text) in enumerate(chunks, 1):
        print(f"   📤 Uploading chunk {idx}/{len(chunks)}...")
        
        embedding = get_embedding(chunk_text)
        
        # Create metadata for this chunk
        metadata = {
            "channel_name": channel_name,
            "channel_id": channel_id,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "message_count": len(chunk_text.split('\n')),
            "timestamp": chunk_id.split('_')[1]  # Extract timestamp from chunk_id
        }
        
        upsert_to_pinecone(chunk_id, embedding, chunk_text, metadata)
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.1)
    
    print(f"   ✅ Successfully uploaded {len(chunks)} chunks from #{channel_name}")
    return len(chunks)

def main():
    print("🚀 Multi-Channel Slack Export to Pinecone")
    print("=" * 50)
    
    # Collect all channel IDs to process
    all_channels = []
    
    # Add channels specified by ID
    for channel_id in CHANNELS_TO_EXPORT:
        all_channels.append(channel_id)
    
    # Add channels specified by name
    for channel_name in CHANNELS_BY_NAME:
        channel_id, _ = get_channel_id_by_name(channel_name)
        if channel_id:
            all_channels.append(channel_id)
    
    if not all_channels:
        print("❌ No channels specified!")
        print("   Please add channel IDs to CHANNELS_TO_EXPORT or names to CHANNELS_BY_NAME")
        return
    
    print(f"📋 Channels to process: {len(all_channels)}")
    
    # Test bot connection
    print("\n=== Testing Bot Connection ===")
    bot_connected, bot_user_id = test_bot_connection()
    if not bot_connected:
        return
    
    # Fetch user map once (used for all channels)
    print("\n=== Fetching User Information ===")
    user_map = fetch_user_map()
    
    # Process each channel
    total_chunks = 0
    successful_channels = 0
    
    for channel_id in all_channels:
        print(f"\n=== Processing Channel {channel_id} ===")
        
        # Test channel access
        channel_info = test_channel_access(channel_id)
        if not channel_info:
            print(f"   ⚠️ Skipping channel {channel_id} (access failed)")
            continue
        
        # Test bot membership
        if not test_bot_in_channel(channel_id, bot_user_id):
            print(f"   ⚠️ Skipping #{channel_info['name']} (bot not a member)")
            continue
        
        # Process the channel
        try:
            chunks_uploaded = process_channel(channel_id, channel_info, user_map)
            total_chunks += chunks_uploaded
            successful_channels += 1
        except Exception as e:
            print(f"   ❌ Error processing #{channel_info['name']}: {e}")
            continue
    
    print(f"\n🎉 Export Complete!")
    print(f"   Channels processed: {successful_channels}/{len(all_channels)}")
    print(f"   Total chunks uploaded: {total_chunks}")
    print(f"   Your Slack bot now has access to conversations from multiple channels!")

if __name__ == "__main__":
    main() 