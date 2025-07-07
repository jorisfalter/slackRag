#!/usr/bin/env python3
"""
Find the latest messages in Pinecone database by examining timestamps.
This helps understand what the most recent data in the system is.
"""

import os
import sys
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

def get_pinecone_client():
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_index_name = os.getenv("PINECONE_INDEX")
    
    if not pinecone_api_key or not pinecone_index_name:
        print("❌ Missing PINECONE_API_KEY or PINECONE_INDEX environment variables")
        return None
    
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(pinecone_index_name)
    return index

def find_latest_messages():
    print("🔍 Finding Latest Messages in Pinecone")
    print("=" * 40)
    
    index = get_pinecone_client()
    if not index:
        return
    
    # Get index statistics
    try:
        stats = index.describe_index_stats()
        total_vectors = stats['total_vector_count']
        
        print(f"📊 Database Statistics:")
        print(f"   Total vectors: {total_vectors}")
        print()
        
        if total_vectors == 0:
            print("📭 Database is empty")
            return
            
    except Exception as e:
        print(f"❌ Error getting database stats: {e}")
        return
    
    # Query for a larger sample to find recent data
    print("🔍 Searching for recent messages...")
    
    try:
        # Create a dummy query vector to get results
        dummy_vector = [0.0] * 1536  # OpenAI embedding dimension
        
        # Query for more results to get a better sample
        results = index.query(
            vector=dummy_vector,
            top_k=100,  # Get more results
            include_metadata=True
        )
        
        if not results['matches']:
            print("📭 No vectors found in database")
            return
        
        print(f"📋 Analyzing {len(results['matches'])} vectors...")
        print()
        
        # Collect all timestamps and sort them
        message_data = []
        
        for match in results['matches']:
            metadata = match.get('metadata', {})
            timestamp = metadata.get('timestamp')
            channel_name = metadata.get('channel_name', 'unknown')
            update_type = metadata.get('update_type', 'original')
            text_preview = metadata.get('text', '')[:100] + '...' if len(metadata.get('text', '')) > 100 else metadata.get('text', '')
            
            if timestamp:
                try:
                    ts_float = float(timestamp)
                    message_data.append({
                        'timestamp': ts_float,
                        'channel': channel_name,
                        'type': update_type,
                        'text': text_preview,
                        'readable_time': datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d %H:%M:%S")
                    })
                except (ValueError, TypeError):
                    pass
        
        if not message_data:
            print("❌ No valid timestamps found in sample")
            return
        
        # Sort by timestamp (newest first)
        message_data.sort(key=lambda x: x['timestamp'], reverse=True)
        
        print(f"🕐 Latest Messages (Top 10):")
        print("-" * 50)
        
        for i, msg in enumerate(message_data[:10], 1):
            hours_ago = (datetime.now().timestamp() - msg['timestamp']) / 3600
            type_indicator = "🔄" if msg['type'] == 'incremental' else "📝"
            
            print(f"{i:2d}. {type_indicator} #{msg['channel']} ({msg['readable_time']})")
            print(f"    {hours_ago:.1f} hours ago")
            print(f"    Preview: {msg['text']}")
            print()
        
        # Show oldest message for comparison
        oldest_msg = message_data[-1]
        oldest_hours_ago = (datetime.now().timestamp() - oldest_msg['timestamp']) / 3600
        
        print(f"📅 Oldest Message in Sample:")
        print(f"   #{oldest_msg['channel']} ({oldest_msg['readable_time']})")
        print(f"   {oldest_hours_ago:.1f} hours ago")
        print()
        
        # Summary statistics
        print(f"📊 Summary:")
        print(f"   Latest message: {message_data[0]['readable_time']}")
        print(f"   Oldest message: {oldest_msg['readable_time']}")
        print(f"   Time span: {(message_data[0]['timestamp'] - oldest_msg['timestamp']) / 3600:.1f} hours")
        
        # Count by update type
        original_count = sum(1 for msg in message_data if msg['type'] == 'original')
        incremental_count = sum(1 for msg in message_data if msg['type'] == 'incremental')
        
        print(f"   Original chunks: {original_count}")
        print(f"   Incremental chunks: {incremental_count}")
        
        # Count by channel
        channel_counts = {}
        for msg in message_data:
            channel_counts[msg['channel']] = channel_counts.get(msg['channel'], 0) + 1
        
        print(f"\n📋 By Channel:")
        for channel, count in sorted(channel_counts.items()):
            print(f"   #{channel}: {count} chunks")
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")

if __name__ == "__main__":
    find_latest_messages() 