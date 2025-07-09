#!/usr/bin/env python3
"""
Debug Pinecone Export Script
Better logging and controls to understand what's happening with pagination
"""

import os
import json
import sys
from datetime import datetime
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

def debug_list_vectors(index, max_pages=50, namespace=None):
    """Debug version with page limits and detailed logging"""
    print(f"🔍 Debug: Listing vectors from namespace: {namespace or 'default'}")
    print(f"⚠️  Limited to {max_pages} pages for debugging")
    
    all_ids = []
    pagination_token = None
    page_count = 0
    
    try:
        while page_count < max_pages:  # Safety limit
            page_count += 1
            print(f"   📄 Page {page_count}...")
            
            # List vectors with pagination
            try:
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
                
                print(f"      Raw result type: {type(result)}")
                print(f"      Raw result: {result}")
                
            except Exception as api_error:
                print(f"   ❌ API Error on page {page_count}: {api_error}")
                break
            
            # Extract vector IDs - handle different response formats
            vectors = None
            pagination_info = None
            
            if hasattr(result, 'vectors'):
                vectors = result.vectors
                pagination_info = getattr(result, 'pagination', None)
                print(f"      Found vectors attribute: {len(vectors) if vectors else 0}")
            elif hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
                vectors = result_dict.get('vectors', [])
                pagination_info = result_dict.get('pagination', {})
                print(f"      Found to_dict vectors: {len(vectors) if vectors else 0}")
            else:
                vectors = getattr(result, 'vectors', [])
                pagination_info = getattr(result, 'pagination', {})
                print(f"      Found getattr vectors: {len(vectors) if vectors else 0}")
            
            if vectors:
                # Handle different vector formats
                if isinstance(vectors, list):
                    page_ids = [v['id'] if isinstance(v, dict) else v.id for v in vectors]
                else:
                    page_ids = list(vectors.keys()) if hasattr(vectors, 'keys') else []
                
                all_ids.extend(page_ids)
                print(f"   ✅ Found {len(page_ids)} vector IDs on page {page_count}")
                print(f"      First few IDs: {page_ids[:3]}")
            else:
                print(f"   ⚠️  No vectors found on page {page_count}")
            
            # Check for more pages
            has_more = False
            if pagination_info:
                if hasattr(pagination_info, 'next'):
                    pagination_token = pagination_info.next
                    has_more = pagination_token is not None
                else:
                    pagination_token = pagination_info.get('next')
                    has_more = pagination_token is not None
                
                print(f"      Pagination info: {pagination_info}")
                print(f"      Next token: {pagination_token}")
                print(f"      Has more: {has_more}")
            
            if not has_more:
                print(f"   ✅ Reached end of pagination at page {page_count}")
                break
        
        if page_count >= max_pages:
            print(f"   ⚠️  Stopped at page limit ({max_pages})")
        
        print(f"📊 Total vector IDs found: {len(all_ids)}")
        print(f"📊 Unique vector IDs: {len(set(all_ids))}")
        
        return all_ids
        
    except Exception as e:
        print(f"❌ Error during pagination: {e}")
        return all_ids

def quick_fetch_sample(index, vector_ids, sample_size=5):
    """Fetch a small sample to test the fetch mechanism"""
    if not vector_ids:
        print("❌ No vector IDs to sample")
        return []
    
    sample_ids = vector_ids[:sample_size]
    print(f"🧪 Testing fetch with {len(sample_ids)} sample vectors...")
    
    try:
        result = index.fetch(ids=sample_ids)
        print(f"   Raw fetch result type: {type(result)}")
        
        # Handle different response formats
        if hasattr(result, 'vectors'):
            vectors = result.vectors
        elif hasattr(result, 'to_dict'):
            vectors = result.to_dict().get('vectors', {})
        else:
            vectors = getattr(result, 'vectors', {})
        
        print(f"   ✅ Successfully fetched {len(vectors)} vectors")
        
        # Convert to our format
        sample_vectors = []
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
                'values': values[:5],  # Just first 5 dimensions for debugging
                'metadata': metadata
            }
            sample_vectors.append(vector_record)
        
        return sample_vectors
        
    except Exception as e:
        print(f"   ❌ Error fetching sample: {e}")
        return []

def main():
    print("🔧 Pinecone Debug Export")
    print("=" * 40)
    
    # Initialize Pinecone
    pc, index, index_name = init_pinecone()
    if not index:
        return
    
    print(f"📌 Connected to index: {index_name}")
    
    # Get index stats
    try:
        stats = index.describe_index_stats()
        print(f"📊 Index stats: {stats}")
    except Exception as e:
        print(f"⚠️  Could not get stats: {e}")
    
    # Debug list with page limit
    print(f"\n🔍 Starting debug listing...")
    vector_ids = debug_list_vectors(index, max_pages=10)  # Limit to 10 pages for debugging
    
    if vector_ids:
        print(f"\n📋 Found {len(vector_ids)} total vector IDs")
        print(f"📋 First 10 IDs: {vector_ids[:10]}")
        print(f"📋 Last 10 IDs: {vector_ids[-10:]}")
        
        # Test fetch with a small sample
        sample_vectors = quick_fetch_sample(index, vector_ids, sample_size=3)
        
        if sample_vectors:
            print(f"\n📄 Sample vector data:")
            for i, vector in enumerate(sample_vectors):
                print(f"   Vector {i+1}:")
                print(f"     ID: {vector['id']}")
                print(f"     Metadata: {vector['metadata']}")
                print(f"     Dimensions: {len(vector.get('values', []))}")
    else:
        print("❌ No vector IDs found")

if __name__ == "__main__":
    main() 