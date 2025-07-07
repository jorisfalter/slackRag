#!/usr/bin/env python3
"""
Debug utility to manually check for recent messages in each channel.
This helps identify why incremental updates might be missing messages.
"""

import os
import sys
import time
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# Channels to check
CHANNELS_TO_CHECK = [
    "general",
    "madlicreative-admin", 
    "bookkeeping--madlicreative",
    "creative",
    "madlicreative-marketing",
    "products-n-services",
    "workflow"
]

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

def fetch_recent_messages(channel_id, channel_name, days_back=7):
    """Fetch recent messages from a channel"""
    since_timestamp = (datetime.now() - timedelta(days=days_back)).timestamp()
    
    print(f"\n🔍 Checking #{channel_name} for messages since {datetime.fromtimestamp(since_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    messages = []
    cursor = None
    
    try:
        while True:
            response = client.conversations_history(
                channel=channel_id,
                cursor=cursor,
                limit=100,
                oldest=str(since_timestamp)
            )
            
            batch_messages = response['messages']
            print(f"   📦 Fetched {len(batch_messages)} messages in this batch")
            
            # Filter messages newer than timestamp
            new_messages = [msg for msg in batch_messages if float(msg['ts']) > since_timestamp]
            messages.extend(new_messages)
            
            if not response.get('has_more'):
                break
                
            cursor = response['response_metadata']['next_cursor']
            time.sleep(0.5)  # Rate limiting
            
    except SlackApiError as e:
        print(f"   ❌ Error fetching messages: {e.response['error']}")
        return []
    
    # Sort by timestamp (newest first for display)
    messages.sort(key=lambda x: float(x['ts']), reverse=True)
    
    print(f"   📊 Total recent messages: {len(messages)}")
    
    # Show recent messages
    if messages:
        print(f"   🕐 Recent messages:")
        for i, msg in enumerate(messages[:5], 1):  # Show top 5
            timestamp = float(msg['ts'])
            readable_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            hours_ago = (datetime.now().timestamp() - timestamp) / 3600
            
            # Get user info
            user_id = msg.get('user', 'unknown')
            text = msg.get('text', '')[:100] + '...' if len(msg.get('text', '')) > 100 else msg.get('text', '')
            
            print(f"     {i}. {readable_time} ({hours_ago:.1f}h ago)")
            print(f"        User: {user_id}")
            print(f"        Text: {text}")
    else:
        print(f"   💤 No recent messages found")
    
    return messages

def main():
    print("🔍 Debug: Checking Recent Messages in All Channels")
    print("=" * 55)
    
    total_recent_messages = 0
    channel_summary = {}
    
    for channel_name in CHANNELS_TO_CHECK:
        channel_id, channel_info = get_channel_id_by_name(channel_name)
        
        if not channel_id:
            print(f"\n❌ Channel #{channel_name} not found or not accessible")
            continue
            
        messages = fetch_recent_messages(channel_id, channel_name, days_back=7)
        total_recent_messages += len(messages)
        channel_summary[channel_name] = len(messages)
    
    print(f"\n📊 Summary:")
    print(f"   Total recent messages across all channels: {total_recent_messages}")
    print(f"   Channels with recent activity:")
    
    for channel, count in channel_summary.items():
        if count > 0:
            print(f"     #{channel}: {count} messages")
    
    if total_recent_messages == 0:
        print(f"   💤 No recent messages found in any monitored channel")
        print(f"   This could mean:")
        print(f"     - Channels have been quiet")
        print(f"     - Bot permissions issue")
        print(f"     - Wrong channel names configured")
    else:
        print(f"\n⚠️  If incremental update found 0 messages but this shows {total_recent_messages},")
        print(f"   there's likely an issue with:")
        print(f"     - Timestamp comparison logic")
        print(f"     - Message filtering")
        print(f"     - Channel access during automated runs")

if __name__ == "__main__":
    main() 