#!/usr/bin/env python3
"""
Full Pinecone Export Script
Exports all vectors and metadata from a Pinecone index to JSON files
"""

import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Any
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

def init_pinecone():
    """Initialize Pinecone client and index"""
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index_name = os.getenv("PINECONE_INDEX")
        
        if not index_name:
            raise ValueError("PINECONE_INDEX environment variable not set")
        
        index = pc.Index(index_name)
        return pc, index, index_name
    except Exception as e:
        print(f"❌ Failed to initialize Pinecone: {e}")
        return None, None, None

def get_index_stats(index):
    """Get index statistics"""
    try:
        stats = index.describe_index_stats()
        return stats
    except Exception as e:
        print(f"❌ Failed to get index stats: {e}")
        return None

def export_all_vectors(index, batch_size=100):
    """Export all vectors from the index"""
    print(f"🔍 Starting full vector export (batch size: {batch_size})")
    
    all_vectors = []
    total_exported = 0
    
    try:
        # Get all vector IDs first by querying with a dummy vector
        # This is a workaround since Pinecone doesn't have a direct "list all IDs" method
        print("📋 Discovering all vector IDs...")
        
        # Query to get some initial IDs
        dummy_vector = [0.0] * 1536  # Assuming OpenAI embeddings (1536 dimensions)
        
        # Use query to discover vector IDs
        query_result = index.query(
            vector=dummy_vector,
            top_k=10000,  # Get as many as possible
            include_metadata=True,
            include_values=True
        )
        
        print(f"📊 Discovered {len(query_result['matches'])} vectors via query")
        
        # Extract vectors from query results
        for match in query_result['matches']:
            vector_data = {
                'id': match['id'],
                'values': match['values'],
                'metadata': match.get('metadata', {}),
                'score': match.get('score')
            }
            all_vectors.append(vector_data)
            total_exported += 1
        
        print(f"✅ Exported {total_exported} vectors successfully")
        return all_vectors
        
    except Exception as e:
        print(f"❌ Error during vector export: {e}")
        return all_vectors

def export_by_namespace(index, namespace=None):
    """Export vectors from a specific namespace or default namespace"""
    print(f"🔍 Exporting from namespace: {namespace or 'default'}")
    
    try:
        # Get stats for the namespace
        stats = index.describe_index_stats()
        if namespace:
            ns_stats = stats.get('namespaces', {}).get(namespace, {})
        else:
            ns_stats = stats.get('total_vector_count', 0)
        
        print(f"📊 Namespace stats: {ns_stats}")
        
        # Since Pinecone doesn't have a direct "export all" method,
        # we'll use the fetch method with known IDs or query method
        
        # Try to get all vectors using query with random vectors
        dummy_vector = [0.0] * 1536
        
        vectors = []
        
        # Multiple queries to try to get all vectors
        for i in range(10):  # Try multiple random queries
            query_result = index.query(
                vector=dummy_vector,
                top_k=1000,
                namespace=namespace,
                include_metadata=True,
                include_values=True
            )
            
            for match in query_result['matches']:
                # Check if we already have this vector
                if not any(v['id'] == match['id'] for v in vectors):
                    vector_data = {
                        'id': match['id'],
                        'values': match['values'],
                        'metadata': match.get('metadata', {}),
                        'score': match.get('score')
                    }
                    vectors.append(vector_data)
            
            # Slight variation in dummy vector for next query
            dummy_vector = [(i * 0.1) % 1.0 for i in range(1536)]
        
        print(f"✅ Exported {len(vectors)} unique vectors from namespace")
        return vectors
        
    except Exception as e:
        print(f"❌ Error exporting namespace {namespace}: {e}")
        return []

def save_export_data(vectors: List[Dict], stats: Dict, index_name: str, output_dir: str = "exports"):
    """Save exported data to JSON files"""
    
    # Create exports directory
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save vectors
    vectors_file = os.path.join(output_dir, f"pinecone_vectors_{index_name}_{timestamp}.json")
    with open(vectors_file, 'w') as f:
        json.dump(vectors, f, indent=2)
    
    # Save metadata summary
    metadata_summary = {
        'export_timestamp': datetime.now().isoformat(),
        'index_name': index_name,
        'total_vectors_exported': len(vectors),
        'index_stats': stats,
        'export_method': 'query_based_discovery'
    }
    
    # Extract just metadata for easier analysis
    metadata_only = []
    for vector in vectors:
        metadata_only.append({
            'id': vector['id'],
            'metadata': vector['metadata']
        })
    
    metadata_file = os.path.join(output_dir, f"pinecone_metadata_{index_name}_{timestamp}.json")
    with open(metadata_file, 'w') as f:
        json.dump({
            'summary': metadata_summary,
            'metadata': metadata_only
        }, f, indent=2)
    
    # Save summary
    summary_file = os.path.join(output_dir, f"export_summary_{index_name}_{timestamp}.json")
    with open(summary_file, 'w') as f:
        json.dump(metadata_summary, f, indent=2)
    
    print(f"💾 Exported data saved to:")
    print(f"   📄 Vectors: {vectors_file}")
    print(f"   📄 Metadata: {metadata_file}")
    print(f"   📄 Summary: {summary_file}")
    
    return vectors_file, metadata_file, summary_file

def analyze_export(vectors: List[Dict]):
    """Analyze the exported data"""
    print(f"\n📊 Export Analysis")
    print(f"=" * 40)
    
    if not vectors:
        print("❌ No vectors to analyze")
        return
    
    print(f"Total vectors: {len(vectors)}")
    
    # Analyze metadata
    metadata_keys = set()
    channel_names = set()
    
    for vector in vectors:
        metadata = vector.get('metadata', {})
        metadata_keys.update(metadata.keys())
        
        if 'channel_name' in metadata:
            channel_names.add(metadata['channel_name'])
    
    print(f"Metadata fields found: {sorted(metadata_keys)}")
    print(f"Channels found: {sorted(channel_names)}")
    
    # Sample vector info
    if vectors:
        sample = vectors[0]
        print(f"Vector dimensions: {len(sample.get('values', []))}")
        print(f"Sample vector ID: {sample.get('id')}")
        print(f"Sample metadata: {sample.get('metadata', {})}")

def main():
    print("🗄️  Full Pinecone Export")
    print("=" * 40)
    
    # Initialize Pinecone
    pc, index, index_name = init_pinecone()
    if not index:
        return
    
    print(f"📌 Connected to index: {index_name}")
    
    # Get index stats
    stats = get_index_stats(index)
    if stats:
        print(f"📊 Index stats: {stats}")
    
    # Export all vectors
    print(f"\n🔄 Starting export...")
    vectors = export_all_vectors(index)
    
    if not vectors:
        print("❌ No vectors exported. Trying namespace-based export...")
        vectors = export_by_namespace(index)
    
    if not vectors:
        print("❌ Still no vectors found. The index might be empty or there might be permission issues.")
        return
    
    # Analyze the export
    analyze_export(vectors)
    
    # Save the data
    print(f"\n💾 Saving export data...")
    files = save_export_data(vectors, stats, index_name)
    
    print(f"\n✅ Export complete!")
    print(f"📄 {len(vectors)} vectors exported")
    print(f"📁 Files saved in 'exports/' directory")

if __name__ == "__main__":
    main() 