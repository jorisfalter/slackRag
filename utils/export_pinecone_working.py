#!/usr/bin/env python3
"""
Working Pinecone Full Export Script
Exports all vectors and metadata from Pinecone index to JSON files
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
            
            # Extract vector IDs using the working format from debug
            vectors = result.vectors if hasattr(result, 'vectors') else []
            
            if vectors:
                page_ids = [v['id'] for v in vectors]
                all_ids.extend(page_ids)
                print(f"   ✅ Found {len(page_ids)} vector IDs on page {page_count}")
            else:
                print(f"   ⚠️  No vectors found on page {page_count}")
                break
            
            # Check for more pages using the working format from debug
            pagination_info = result.pagination if hasattr(result, 'pagination') else None
            if pagination_info and hasattr(pagination_info, 'next'):
                pagination_token = pagination_info.next
            else:
                pagination_token = None
            
            if not pagination_token:
                print(f"   ✅ Reached end of pagination at page {page_count}")
                break
        
        print(f"📊 Total vector IDs found: {len(all_ids)}")
        return all_ids
        
    except Exception as e:
        print(f"❌ Error getting vector IDs: {e}")
        return all_ids

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
            
            # Use the working format from debug
            vectors = result.vectors if hasattr(result, 'vectors') else {}
            print(f"   ✅ Retrieved {len(vectors)} vectors from batch {batch_num}")
            
            # Convert to our format
            for vector_id, vector_data in vectors.items():
                # Handle the vector data format we confirmed works
                values = vector_data.values if hasattr(vector_data, 'values') else []
                metadata = vector_data.metadata if hasattr(vector_data, 'metadata') else {}
                
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

def save_full_export(vectors: List[Dict], index_name: str, output_dir: str = "exports"):
    """Save complete export data to multiple formats"""
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    export_info = {
        'timestamp': datetime.now().isoformat(),
        'index_name': index_name,
        'total_vectors': len(vectors),
        'export_type': 'full_export'
    }
    
    # 1. Full raw export (everything)
    raw_file = os.path.join(output_dir, f"pinecone_full_export_{index_name}_{timestamp}.json")
    full_export = {
        'export_info': export_info,
        'vectors': vectors
    }
    
    with open(raw_file, 'w') as f:
        json.dump(full_export, f, indent=2)
    
    # 2. Metadata + text only (no vectors)
    metadata_file = os.path.join(output_dir, f"pinecone_metadata_text_{index_name}_{timestamp}.json")
    metadata_export = {
        'export_info': export_info,
        'data': [
            {
                'id': v['id'],
                'metadata': v['metadata'],
                'text': v['metadata'].get('text', ''),
                'channel': v['metadata'].get('channel_name', ''),
                'timestamp': v['metadata'].get('timestamp', '')
            }
            for v in vectors
        ]
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata_export, f, indent=2)
    
    # 3. Readable text export
    text_file = os.path.join(output_dir, f"pinecone_readable_{index_name}_{timestamp}.txt")
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(f"PINECONE EXPORT - {datetime.now().isoformat()}\n")
        f.write(f"Index: {index_name}\n")
        f.write(f"Total vectors: {len(vectors)}\n")
        f.write("=" * 80 + "\n\n")
        
        # Group by channel
        by_channel = {}
        for vector in vectors:
            channel = vector['metadata'].get('channel_name', 'unknown')
            if channel not in by_channel:
                by_channel[channel] = []
            by_channel[channel].append(vector)
        
        for channel, channel_vectors in by_channel.items():
            f.write(f"CHANNEL: #{channel}\n")
            f.write("-" * 40 + "\n")
            
            for vector in sorted(channel_vectors, key=lambda x: x['metadata'].get('timestamp', '0')):
                text = vector['metadata'].get('text', '')
                timestamp = vector['metadata'].get('timestamp', 'unknown')
                chunk_idx = vector['metadata'].get('chunk_index', 'unknown')
                
                f.write(f"Chunk {chunk_idx} | {timestamp}\n")
                f.write(f"{text}\n")
                f.write("\n" + "." * 40 + "\n\n")
            
            f.write("\n")
    
    # 4. Statistics summary
    stats_file = os.path.join(output_dir, f"pinecone_stats_{index_name}_{timestamp}.json")
    
    # Analyze the data
    channels = set()
    total_messages = 0
    date_range = {'earliest': None, 'latest': None}
    
    for vector in vectors:
        metadata = vector['metadata']
        
        if 'channel_name' in metadata:
            channels.add(metadata['channel_name'])
        
        if 'message_count' in metadata:
            total_messages += int(metadata.get('message_count', 0))
        
        if 'timestamp' in metadata:
            ts = metadata['timestamp']
            if date_range['earliest'] is None or ts < date_range['earliest']:
                date_range['earliest'] = ts
            if date_range['latest'] is None or ts > date_range['latest']:
                date_range['latest'] = ts
    
    stats = {
        'export_info': export_info,
        'analysis': {
            'channels_found': sorted(list(channels)),
            'total_channels': len(channels),
            'total_conversation_chunks': len(vectors),
            'estimated_total_messages': total_messages,
            'date_range': date_range,
            'vector_dimensions': len(vectors[0]['values']) if vectors else 0
        }
    }
    
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n💾 Export files saved:")
    print(f"   📄 Full export: {raw_file}")
    print(f"   📄 Metadata + text: {metadata_file}")
    print(f"   📄 Readable text: {text_file}")
    print(f"   📄 Statistics: {stats_file}")
    
    return {
        'raw': raw_file,
        'metadata': metadata_file,
        'text': text_file,
        'stats': stats_file
    }

def main():
    print("🗄️  Pinecone Full Export")
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
        print(f"🔢 Expected vectors: {total_vectors}")
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
    
    # Quick analysis
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
    
    # Save the complete export
    print(f"\n💾 Saving complete export...")
    files = save_full_export(vectors, index_name)
    
    print(f"\n✅ Full export complete!")
    print(f"📁 All files saved in 'exports/' directory")
    print(f"🎯 You now have all {len(vectors)} vectors exported in multiple formats")

if __name__ == "__main__":
    main() 