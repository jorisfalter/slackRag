import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

def clear_pinecone_index():
    """Clear all vectors from the Pinecone index"""
    try:
        # Initialize Pinecone client
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        pinecone_index_name = os.getenv("PINECONE_INDEX")
        
        if not pinecone_api_key:
            print("❌ PINECONE_API_KEY environment variable is not set")
            return False
        if not pinecone_index_name:
            print("❌ PINECONE_INDEX environment variable is not set")
            return False
        
        print(f"🔗 Connecting to Pinecone index: {pinecone_index_name}")
        pc = Pinecone(api_key=pinecone_api_key)
        index = pc.Index(pinecone_index_name)
        
        # Get index stats first
        stats = index.describe_index_stats()
        total_vectors = stats['total_vector_count']
        
        print(f"📊 Current index stats:")
        print(f"   Total vectors: {total_vectors}")
        print(f"   Index dimension: {stats.get('dimension', 'unknown')}")
        
        if total_vectors == 0:
            print("✅ Index is already empty!")
            return True
        
        # Confirm deletion
        print(f"\n⚠️  WARNING: This will delete ALL {total_vectors} vectors from the index!")
        print("   This action cannot be undone.")
        
        confirmation = input("\nType 'DELETE' to confirm: ")
        if confirmation != 'DELETE':
            print("❌ Deletion cancelled.")
            return False
        
        print(f"\n🗑️  Deleting all vectors from index '{pinecone_index_name}'...")
        
        # Delete all vectors by using delete_all (if available) or namespace deletion
        try:
            # Try the newer delete method
            index.delete(delete_all=True)
            print("✅ Successfully deleted all vectors using delete_all=True")
        except Exception as e:
            print(f"⚠️  delete_all=True failed: {e}")
            print("🔄 Trying alternative method...")
            
            # Alternative: Delete by namespace (empty namespace = all vectors)
            try:
                index.delete(namespace="")
                print("✅ Successfully deleted all vectors using namespace deletion")
            except Exception as e2:
                print(f"❌ Alternative deletion method also failed: {e2}")
                return False
        
        # Verify deletion
        print("🔍 Verifying deletion...")
        import time
        time.sleep(2)  # Give Pinecone a moment to process
        
        stats_after = index.describe_index_stats()
        vectors_after = stats_after['total_vector_count']
        
        if vectors_after == 0:
            print("✅ Index successfully cleared!")
            print("🚀 Ready for fresh multi-channel data import!")
            return True
        else:
            print(f"⚠️  Warning: {vectors_after} vectors still remain in the index")
            print("   This might be due to indexing delay. Check again in a few minutes.")
            return True
            
    except Exception as e:
        print(f"❌ Error clearing Pinecone index: {e}")
        return False

def main():
    print("🧹 Pinecone Index Cleaner")
    print("=" * 30)
    print("This script will delete ALL data from your Pinecone index.")
    print("Use this before importing fresh multi-channel data.")
    print()
    
    success = clear_pinecone_index()
    
    if success:
        print("\n✅ Index cleared successfully!")
        print("💡 Next steps:")
        print("   1. Run: python slack_export/export_multiple_channels.py")
        print("   2. Your bot will then have access to all channel data with proper source attribution!")
    else:
        print("\n❌ Failed to clear index. Please check your configuration and try again.")

if __name__ == "__main__":
    main() 