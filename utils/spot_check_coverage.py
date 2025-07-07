#!/usr/bin/env python3
"""
Spot check utility to verify Slack messages are properly stored in Pinecone.
Samples a few messages from each channel and checks if they exist in the vector database.
"""

import os
import sys
import time
import re
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils.pinecone_utils import get_pinecone_client
from dotenv import load_dotenv

load_dotenv()

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

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

def sample_slack_messages(channel_id, channel_name, sample_size=3):
    """Sample a few messages from a Slack channel"""
    print(f"🔍 Sampling {sample_size} messages from #{channel_name}")
    
    try:
        # Get recent messages
        response = client.conversations_history(
            channel=channel_id,
            limit=50  # Get more to have options
        )
        
        messages = response['messages']
        
        # Filter out bot messages, system messages, etc.
        valid_messages = [
            msg for msg in messages 
            if msg.get('text') and msg.get('user') and len(msg.get('text', '').strip()) > 10
        ]
        
        # Sample messages from different time periods
        if len(valid_messages) >= sample_size:
            # Take messages from beginning, middle, and end
            indices = [0, len(valid_messages)//2, len(valid_messages)-1]
            sampled = [valid_messages[i] for i in indices[:sample_size]]
        else:
            sampled = valid_messages
        
        print(f"   📦 Found {len(valid_messages)} valid messages, sampling {len(sampled)}")
        
        return sampled
        
    except SlackApiError as e:
        print(f"   ❌ Error fetching messages: {e.response['error']}")
        return []

def search_message_in_pinecone(message_text, channel_name, timestamp):
    """Search for a message in Pinecone using text similarity"""
    try:
        index = get_pinecone_client()
        
        # Create a dummy vector for querying (we'll use metadata filters)
        dummy_vector = [0.0] * 1536
        
        # Search with metadata filter for the specific channel
        result = index.query(
            vector=dummy_vector,
            top_k=100,  # Get more results to search through
            include_metadata=True,
            filter={"channel_name": channel_name}
        )
        
        # Look for the message in the results
        message_words = set(message_text.lower().split())
        best_match_score = 0
        best_match = None
        
        for match in result['matches']:
            chunk_text = match['metadata'].get('text', '')
            chunk_timestamp = match['metadata'].get('timestamp', '')
            
            # Check if this chunk contains our message
            chunk_words = set(chunk_text.lower().split())
            
            # Calculate word overlap
            overlap = len(message_words & chunk_words)
            overlap_score = overlap / len(message_words) if message_words else 0
            
            # Also check timestamp proximity (within 60 seconds)
            try:
                time_diff = abs(float(timestamp) - float(chunk_timestamp))
                time_match = time_diff < 60  # Within 1 minute
            except:
                time_match = False
            
            # Consider it a match if high word overlap OR exact timestamp match
            if overlap_score > 0.7 or time_match:
                if overlap_score > best_match_score:
                    best_match_score = overlap_score
                    best_match = {
                        'chunk_text': chunk_text,
                        'chunk_timestamp': chunk_timestamp,
                        'vector_id': match['id'],
                        'overlap_score': overlap_score,
                        'time_match': time_match
                    }
        
        return best_match
        
    except Exception as e:
        print(f"   ❌ Error searching Pinecone: {e}")
        return None

def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp)

def spot_check_channel(channel_name):
    """Spot check a single channel"""
    print(f"\n🔍 Spot Check: #{channel_name}")
    print("=" * 50)
    
    # Get channel info
    channel_id, channel_info = get_channel_id_by_name(channel_name)
    if not channel_id:
        print(f"   ❌ Channel not found or not accessible")
        return {"channel": channel_name, "accessible": False}
    
    # Sample messages
    messages = sample_slack_messages(channel_id, channel_name, sample_size=3)
    if not messages:
        print(f"   💤 No messages to check")
        return {"channel": channel_name, "accessible": True, "messages_found": 0, "matches": []}
    
    # Check each message
    results = []
    for i, msg in enumerate(messages, 1):
        message_text = msg.get('text', '')
        timestamp = msg.get('ts', '')
        user_id = msg.get('user', '')
        
        # Truncate message for display
        display_text = message_text[:60] + '...' if len(message_text) > 60 else message_text
        
        print(f"\n   📋 Message {i}: {display_text}")
        print(f"      Time: {format_timestamp(timestamp)}")
        print(f"      User: {user_id}")
        
        # Search in Pinecone
        match = search_message_in_pinecone(message_text, channel_name, timestamp)
        
        if match:
            print(f"      ✅ FOUND in Pinecone (overlap: {match['overlap_score']:.2f})")
            if match['time_match']:
                print(f"         🕐 Timestamp match confirmed")
            print(f"         Vector ID: {match['vector_id']}")
            results.append({
                "message": display_text,
                "timestamp": timestamp,
                "found": True,
                "overlap_score": match['overlap_score'],
                "vector_id": match['vector_id']
            })
        else:
            print(f"      ❌ NOT FOUND in Pinecone")
            results.append({
                "message": display_text,
                "timestamp": timestamp,
                "found": False
            })
        
        time.sleep(0.5)  # Rate limiting
    
    return {
        "channel": channel_name,
        "accessible": True,
        "messages_found": len(messages),
        "matches": results
    }

def main():
    """Run spot check on all channels"""
    print("🔍 Pinecone Coverage Spot Check")
    print("=" * 40)
    print("Checking if Slack messages are properly stored in Pinecone...")
    print("This will sample a few messages from each channel and verify they exist in the vector database.")
    
    all_results = []
    
    for channel_name in CHANNELS_TO_CHECK:
        result = spot_check_channel(channel_name)
        all_results.append(result)
        time.sleep(1)  # Rate limiting between channels
    
    # Summary
    print(f"\n📊 SPOT CHECK SUMMARY")
    print("=" * 30)
    
    total_messages = 0
    total_found = 0
    
    for result in all_results:
        if not result.get('accessible'):
            print(f"❌ #{result['channel']}: Not accessible")
            continue
        
        messages_count = result.get('messages_found', 0)
        if messages_count == 0:
            print(f"💤 #{result['channel']}: No messages to check")
            continue
        
        found_count = sum(1 for match in result.get('matches', []) if match.get('found'))
        total_messages += messages_count
        total_found += found_count
        
        status = "✅" if found_count == messages_count else "⚠️"
        print(f"{status} #{result['channel']}: {found_count}/{messages_count} messages found in Pinecone")
        
        # Show missing messages
        missing = [match for match in result.get('matches', []) if not match.get('found')]
        if missing:
            print(f"   Missing messages:")
            for miss in missing:
                print(f"     - {miss['message']} ({format_timestamp(miss['timestamp'])})")
    
    print(f"\n🎯 OVERALL COVERAGE:")
    if total_messages > 0:
        coverage_percent = (total_found / total_messages) * 100
        print(f"   {total_found}/{total_messages} messages found ({coverage_percent:.1f}% coverage)")
        
        if coverage_percent >= 95:
            print("   🎉 Excellent coverage! Your data is well synchronized.")
        elif coverage_percent >= 80:
            print("   👍 Good coverage. Minor gaps may exist.")
        else:
            print("   ⚠️  Coverage gaps detected. Consider running a full re-sync.")
    else:
        print("   💤 No messages found to check")
    
    print(f"\n💡 Note: This is a spot check with small samples.")
    print(f"   For comprehensive verification, run a full data audit.")

if __name__ == "__main__":
    main() 