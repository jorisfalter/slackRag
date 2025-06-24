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

# Debug: Check if environment variables are loaded
print(f"PINECONE_API_KEY loaded: {os.getenv('PINECONE_API_KEY') is not None}")
print(f"PINECONE_INDEX loaded: {os.getenv('PINECONE_INDEX') is not None}")
print(f"SLACK_BOT_TOKEN loaded: {os.getenv('SLACK_BOT_TOKEN') is not None}")
print(f"SLACK_CHANNEL_ID loaded: {os.getenv('SLACK_CHANNEL_ID') is not None}")
print(f"OPENAI_API_KEY loaded: {os.getenv('OPENAI_API_KEY') is not None}")

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

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
        print(f"   Channel name: {response['channel']['name']}")
        print(f"   Channel ID: {response['channel']['id']}")
        return True
    except SlackApiError as e:
        print(f"❌ Channel access failed: {e.response['error']}")
        if e.response['error'] == 'channel_not_found':
            print("   The channel ID might be wrong, or the bot isn't in this channel.")
        elif e.response['error'] == 'not_in_channel':
            print("   The bot needs to be added to this channel first.")
        return False

def test_simple_api_call():
    """Test a simple API call to see if rate limiting happens immediately"""
    try:
        print("Testing simple API call (auth.test)...")
        response = client.auth_test()
        print("✅ Simple API call successful")
        return True
    except SlackApiError as e:
        print(f"❌ Simple API call failed: {e.response['error']}")
        return False

def fetch_channel_messages(channel_id):
    messages = []
    cursor = None
    call_count = 0
    
    print(f"Starting to fetch messages from channel {channel_id}")
    print("Note: Using 30-second delays to avoid rate limits (2 calls per minute)")
    
    while True:
        call_count += 1
        print(f"API call #{call_count} - Fetching messages...")
        
        try:
            # Start with a smaller limit to test
            response = client.conversations_history(channel=channel_id, cursor=cursor, limit=10)
            print(f"✅ Successfully fetched {len(response['messages'])} messages")
            messages.extend(response['messages'])
            
            if not response.get('has_more'):
                print("No more messages to fetch")
                break
                
            cursor = response['response_metadata']['next_cursor']
            print(f"More messages available, cursor: {cursor[:20]}...")
            
            # Rate limiting: wait 30 seconds between API calls (2 per minute max)
            print("Waiting 30 seconds before next call...")
            time.sleep(30)
            
        except SlackApiError as e:
            print(f"❌ Slack API Error: {e.response['error']}")
            print(f"Full error response: {e.response}")
            
            if e.response['error'] == 'ratelimited':
                # Check if there are rate limit headers
                if hasattr(e.response, 'headers'):
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        print(f"Retry-After header: {retry_after} seconds")
                        time.sleep(int(retry_after) + 5)  # Add 5 seconds buffer
                    else:
                        print("No Retry-After header, waiting 120 seconds...")
                        time.sleep(120)
                else:
                    print("No headers available, waiting 120 seconds...")
                    time.sleep(120)
            else:
                print(f"Non-rate-limit error: {e}")
                break
                
    # Sort messages by timestamp (oldest first)
    messages.sort(key=lambda x: float(x['ts']))
    return messages

def fetch_user_map():
    user_map = {}
    cursor = None
    call_count = 0
    
    print("Starting to fetch user information...")
    print("Note: Using 30-second delays to avoid rate limits (2 calls per minute)")
    
    while True:
        call_count += 1
        print(f"User API call #{call_count}...")
        
        try:
            response = client.users_list(cursor=cursor)
            print(f"✅ Successfully fetched {len(response['members'])} users")
            
            for user in response['members']:
                user_map[user['id']] = user['profile'].get('display_name') or user['profile'].get('real_name') or user['name']
            
            if not response.get('response_metadata', {}).get('next_cursor'):
                print("No more users to fetch")
                break
                
            cursor = response['response_metadata']['next_cursor']
            print("More users available...")
            
            # Rate limiting: wait 30 seconds between API calls (2 per minute max)
            print("Waiting 30 seconds before next user call...")
            time.sleep(30)
            
        except SlackApiError as e:
            print(f"❌ User API Error: {e.response['error']}")
            print(f"Full error response: {e.response}")
            
            if e.response['error'] == 'ratelimited':
                print("Rate limited on users. Waiting 120 seconds...")
                time.sleep(120)
            else:
                print(f"Non-rate-limit error: {e}")
                break
                
    return user_map

def group_messages(messages, user_map, window_size=5, overlap=2):
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
            chunk_id = window[0]['ts']  # Use ts of first message in window
            chunks.append((chunk_id, chunk_text))
        i += window_size - overlap
    return chunks

def main():
    channel_id = os.getenv("SLACK_CHANNEL_ID")
    if not channel_id:
        print("SLACK_CHANNEL_ID not set in .env file.")
        return
    
    print("\n=== Testing Bot Connection ===")
    bot_connected, bot_user_id = test_bot_connection()
    if not bot_connected:
        return
    
    print(f"\n=== Testing Channel Access ===")
    if not test_channel_access(channel_id):
        return
    
    print(f"\n=== Testing Bot Channel Membership ===")
    if not test_bot_in_channel(channel_id, bot_user_id):
        return
    
    print(f"\n=== Testing Simple API Call ===")
    if not test_simple_api_call():
        return
    
    print("\n=== Fetching Data ===")
    print("Fetching channel messages...")
    messages = fetch_channel_messages(channel_id)
    print(f"Fetched {len(messages)} messages.")
    print("Fetching user information...")
    user_map = fetch_user_map()
    print(f"Fetched {len(user_map)} users.")
    chunks = group_messages(messages, user_map, window_size=5, overlap=2)
    for idx, (chunk_id, chunk_text) in enumerate(chunks, 1):
        print(f"\n--- Conversation Chunk {idx} ---\n{chunk_text}\n-----------------------------\n")
        embedding = get_embedding(chunk_text)
        upsert_to_pinecone(chunk_id, embedding, chunk_text)
    print(f"Uploaded {len(chunks)} chunks to Pinecone.")

if __name__ == "__main__":
    main() 