#!/usr/bin/env python3
"""
Simple Pinecone Export Script
Uses list_paginated to get all vector IDs, then fetches them in batches
"""

import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Any
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from pinecone import Pinecone

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

def get_all_vector_ids(index, namespace=None):
    """Get all vector IDs using list_paginated"""
    print(f"📋 Getting all vector IDs from namespace: {namespace or 'default'}")
    
    all_ids = []
    pagination_token = None
    page_count = 0
    
    try:
        while True:
            page_count += 1
            print(f"   📄 Fetching page {page_count}...")
            
            # List vectors with pagination
            if pagination_token:
                result = index.list_paginated(
                    namespace=namespace,
                    pagination_token=pagination_token,
                    limit=100
                )
            else:
                result = index.list_paginated(
                    namespace=namespace,
                    limit=100
                )
            
            # Extract vector IDs - handle different response formats
            vectors = None
            pagination_info = None
            
            if hasattr(result, 'vectors'):
                vectors = result.vectors
                pagination_info = getattr(result, 'pagination', None)
            elif hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
                vectors = result_dict.get('vectors', [])
                pagination_info = result_dict.get('pagination', {})
            else:
                vectors = getattr(result, 'vectors', [])
                pagination_info = getattr(result, 'pagination', {})
            
            if vectors:
                # Handle different vector formats
                if isinstance(vectors, list):
                    page_ids = [v['id'] if isinstance(v, dict) else v.id for v in vectors]
                else:
                    page_ids = list(vectors.keys()) if hasattr(vectors, 'keys') else []
                
                all_ids.extend(page_ids)
                print(f"   ✅ Found {len(page_ids)} vector IDs on page {page_count}")
            
            # Check for more pages
            if pagination_info:
                if hasattr(pagination_info, 'next'):
                    pagination_token = pagination_info.next
                else:
                    pagination_token = pagination_info.get('next')
            if not pagination_token:
                break
        
        print(f"📊 Total vector IDs found: {len(all_ids)}")
        return all_ids
        
    except Exception as e:
        print(f"❌ Error getting vector IDs: {e}")
        # Fall back to empty list
        return []

def fetch_vectors_in_batches(index, vector_ids, batch_size=100, namespace=None):
    """Fetch vectors in batches using their IDs"""
    print(f"📥 Fetching {len(vector_ids)} vectors in batches of {batch_size}")
    
    all_vectors = []
    total_batches = (len(vector_ids) + batch_size - 1) // batch_size
    
    for i in range(0, len(vector_ids), batch_size):
        batch_num = (i // batch_size) + 1
        batch_ids = vector_ids[i:i + batch_size]
        
        print(f"   📦 Fetching batch {batch_num}/{total_batches} ({len(batch_ids)} vectors)...")
        
        try:
            # Fetch this batch of vectors
            result = index.fetch(ids=batch_ids, namespace=namespace)
            
            # Handle different response formats
            if hasattr(result, 'vectors'):
                vectors = result.vectors
            elif hasattr(result, 'to_dict'):
                vectors = result.to_dict().get('vectors', {})
            else:
                vectors = getattr(result, 'vectors', {})
            
            print(f"   ✅ Retrieved {len(vectors)} vectors from batch {batch_num}")
            
            # Convert to our format
            for vector_id, vector_data in vectors.items():
                # Handle different vector data formats
                if hasattr(vector_data, 'values'):
                    values = vector_data.values
                    metadata = getattr(vector_data, 'metadata', {})
                else:
                    values = vector_data.get('values', [])
                    metadata = vector_data.get('metadata', {})
                
                vector_record = {
                    'id': vector_id,
                    'values': values,
                    'metadata': metadata
                }
                all_vectors.append(vector_record)
                
        except Exception as e:
            print(f"   ❌ Error fetching batch {batch_num}: {e}")
            continue
    
    print(f"✅ Successfully fetched {len(all_vectors)} vectors")
    return all_vectors

def save_raw_export(vectors: List[Dict], index_name: str, output_dir: str = "exports"):
    """Save raw export data to JSON files"""
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Full raw export
    raw_file = os.path.join(output_dir, f"pinecone_raw_export_{index_name}_{timestamp}.json")
    export_data = {
        'export_info': {
            'timestamp': datetime.now().isoformat(),
            'index_name': index_name,
            'total_vectors': len(vectors),
            'export_type': 'full_raw_export'
        },
        'vectors': vectors
    }
    
    with open(raw_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    # Metadata-only file
    metadata_file = os.path.join(output_dir, f"pinecone_metadata_only_{index_name}_{timestamp}.json")
    metadata_export = {
        'export_info': export_data['export_info'],
        'metadata': [
            {
                'id': v['id'],
                'metadata': v['metadata']
            }
            for v in vectors
        ]
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata_export, f, indent=2)
    
    # Text content file (for easy reading)
    text_file = os.path.join(output_dir, f"pinecone_text_content_{index_name}_{timestamp}.txt")
    with open(text_file, 'w') as f:
        f.write(f"Pinecone Export - {datetime.now().isoformat()}\n")
        f.write(f"Index: {index_name}\n")
        f.write(f"Total vectors: {len(vectors)}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, vector in enumerate(vectors, 1):
            f.write(f"Vector {i}: {vector['id']}\n")
            f.write(f"Metadata: {json.dumps(vector['metadata'], indent=2)}\n")
            f.write("-" * 40 + "\n")
    
    print(f"💾 Export files saved:")
    print(f"   📄 Raw export: {raw_file}")
    print(f"   📄 Metadata only: {metadata_file}")
    print(f"   📄 Text content: {text_file}")
    
    return raw_file, metadata_file, text_file

def main():
    print("🗄️  Simple Pinecone Raw Export")
    print("=" * 50)
    
    # Initialize Pinecone
    pc, index, index_name = init_pinecone()
    if not index:
        return
    
    print(f"📌 Connected to index: {index_name}")
    
    # Get index stats
    try:
        stats = index.describe_index_stats()
        print(f"📊 Index stats: {stats}")
        total_vectors = stats.get('total_vector_count', 0)
        print(f"🔢 Total vectors in index: {total_vectors}")
    except Exception as e:
        print(f"⚠️  Could not get stats: {e}")
        total_vectors = "unknown"
    
    # Get all vector IDs
    vector_ids = get_all_vector_ids(index)
    
    if not vector_ids:
        print("❌ No vector IDs found. The index might be empty.")
        return
    
    print(f"📋 Found {len(vector_ids)} vector IDs")
    
    # Fetch all vectors
    vectors = fetch_vectors_in_batches(index, vector_ids)
    
    if not vectors:
        print("❌ No vectors retrieved.")
        return
    
    # Analyze the data
    print(f"\n📊 Export Analysis:")
    print(f"   Total vectors: {len(vectors)}")
    
    if vectors:
        # Analyze metadata
        all_metadata_keys = set()
        channels = set()
        
        for vector in vectors:
            metadata = vector.get('metadata', {})
            all_metadata_keys.update(metadata.keys())
            
            if 'channel_name' in metadata:
                channels.add(metadata['channel_name'])
        
        print(f"   Metadata fields: {sorted(all_metadata_keys)}")
        print(f"   Channels found: {sorted(channels)}")
        print(f"   Vector dimensions: {len(vectors[0].get('values', []))}")
    
    # Save the export
    print(f"\n💾 Saving raw export...")
    files = save_raw_export(vectors, index_name)
    
    print(f"\n✅ Raw export complete!")
    print(f"📁 All files saved in 'exports/' directory")

if __name__ == "__main__":
    main() 