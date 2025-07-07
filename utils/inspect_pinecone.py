import os
import sys
from datetime import datetime, timedelta
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

def inspect_database():
    print("🔍 Inspecting Pinecone Database")
    print("=" * 50)
    
    index = get_pinecone_client()
    if not index:
        return
    
    # Get index statistics
    try:
        stats = index.describe_index_stats()
        total_vectors = stats['total_vector_count']
        
        print(f"📊 Database Statistics:")
        print(f"   Total vectors: {total_vectors}")
        print(f"   Index dimension: {stats.get('dimension', 'unknown')}")
        print()
        
        if total_vectors == 0:
            print("📭 Database is empty - no data to inspect")
            return
            
    except Exception as e:
        print(f"❌ Error getting database stats: {e}")
        return
    
    # Query for recent data (last 48 hours to see what's new)
    print("🕒 Searching for recent data (last 48 hours)...")
    
    # Since we can't directly query by timestamp, we'll do a sample query
    # to get some vectors and check their metadata
    try:
        # Create a dummy query vector (all zeros) just to get some results
        dummy_vector = [0.0] * 1536  # OpenAI embedding dimension
        
        # Query for a sample of vectors
        results = index.query(
            vector=dummy_vector,
            top_k=50,  # Get more results to analyze
            include_metadata=True
        )
        
        if not results['matches']:
            print("📭 No vectors found in database")
            return
        
        print(f"📋 Analyzing {len(results['matches'])} sample vectors...")
        print()
        
        # Analyze the metadata
        channels = {}
        recent_count = 0
        total_analyzed = 0
        update_types = {}
        
        # Calculate 24 hours ago timestamp
        hours_24_ago = (datetime.now() - timedelta(hours=24)).timestamp()
        hours_48_ago = (datetime.now() - timedelta(hours=48)).timestamp()
        
        for match in results['matches']:
            metadata = match.get('metadata', {})
            total_analyzed += 1
            
            # Channel statistics
            channel_name = metadata.get('channel_name', 'unknown')
            if channel_name not in channels:
                channels[channel_name] = {'count': 0, 'recent': 0}
            channels[channel_name]['count'] += 1
            
            # Update type statistics
            update_type = metadata.get('update_type', 'original')
            update_types[update_type] = update_types.get(update_type, 0) + 1
            
            # Check if recent (last 24-48 hours)
            timestamp = metadata.get('timestamp')
            if timestamp:
                try:
                    ts_float = float(timestamp)
                    if ts_float > hours_24_ago:
                        recent_count += 1
                        channels[channel_name]['recent'] += 1
                        
                        # Show details of very recent items
                        date_str = datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d %H:%M:%S")
                        text_preview = metadata.get('text', '')[:100] + '...' if len(metadata.get('text', '')) > 100 else metadata.get('text', '')
                        print(f"🆕 Recent: #{channel_name} ({date_str})")
                        print(f"    Preview: {text_preview}")
                        print()
                        
                except (ValueError, TypeError):
                    pass
        
        # Summary statistics
        print("📊 Channel Breakdown:")
        for channel, data in sorted(channels.items()):
            recent_indicator = f" ({data['recent']} recent)" if data['recent'] > 0 else ""
            print(f"   #{channel}: {data['count']} chunks{recent_indicator}")
        
        print(f"\n📈 Summary:")
        print(f"   Total chunks analyzed: {total_analyzed}")
        print(f"   Chunks from last 24 hours: {recent_count}")
        print(f"   Channels with data: {len(channels)}")
        
        print(f"\n🔄 Update Types:")
        for update_type, count in update_types.items():
            print(f"   {update_type}: {count} chunks")
        
        if recent_count > 0:
            print(f"\n✅ Found {recent_count} recent chunks - incremental update seems to be working!")
        else:
            print(f"\n⚠️  No chunks from last 24 hours found in sample")
            print("   This might mean:")
            print("   - No new messages in the channels")
            print("   - Incremental update hasn't run yet")
            print("   - Need to check larger sample size")
            
    except Exception as e:
        print(f"❌ Error querying database: {e}")

def check_last_update_file():
    print("\n📄 Checking last_update.json file...")
    
    if os.path.exists("last_update.json"):
        try:
            import json
            with open("last_update.json", 'r') as f:
                data = json.load(f)
            
            last_update = data.get('last_update')
            readable_time = data.get('last_update_readable')
            
            print(f"✅ Last update file found:")
            print(f"   Timestamp: {last_update}")
            print(f"   Readable: {readable_time}")
            
            if last_update:
                hours_ago = (datetime.now().timestamp() - float(last_update)) / 3600
                print(f"   Time ago: {hours_ago:.1f} hours ago")
                
        except Exception as e:
            print(f"❌ Error reading last_update.json: {e}")
    else:
        print("⚠️  No last_update.json file found")
        print("   This means incremental update hasn't run yet")

if __name__ == "__main__":
    inspect_database()
    check_last_update_file() 