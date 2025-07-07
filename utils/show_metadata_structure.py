#!/usr/bin/env python3
"""
Show the actual metadata structure stored in Pinecone vectors
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.pinecone_utils import get_pinecone_client
from dotenv import load_dotenv
import json

load_dotenv()

def show_metadata_structure():
    """Show actual metadata structure from Pinecone"""
    print("🔍 Pinecone Metadata Structure Analysis")
    print("=" * 45)
    
    try:
        index = get_pinecone_client()
        
        # Query for some recent vectors
        dummy_vector = [0.0] * 1536  # Create a dummy vector for querying
        result = index.query(vector=dummy_vector, top_k=5, include_metadata=True)
        
        print(f"📊 Found {len(result['matches'])} vectors")
        print("\n🏷️  Metadata Structure Examples:")
        print("=" * 45)
        
        for i, match in enumerate(result['matches'], 1):
            print(f"\n📋 Vector {i}:")
            print(f"   ID: {match['id']}")
            print(f"   Score: {match['score']:.4f}")
            print(f"   Metadata:")
            
            metadata = match['metadata']
            for key, value in metadata.items():
                if key == 'text':
                    # Truncate text for readability
                    text_preview = value[:100] + '...' if len(value) > 100 else value
                    print(f"     {key}: {text_preview}")
                else:
                    print(f"     {key}: {value}")
            
            print("   " + "-" * 40)
        
        # Analyze metadata fields across all samples
        print(f"\n📊 Metadata Field Analysis:")
        print("=" * 30)
        
        all_fields = set()
        field_examples = {}
        
        for match in result['matches']:
            metadata = match['metadata']
            for key, value in metadata.items():
                all_fields.add(key)
                if key not in field_examples:
                    field_examples[key] = value
        
        print(f"   Total unique fields: {len(all_fields)}")
        print(f"   Fields found:")
        
        for field in sorted(all_fields):
            example = field_examples[field]
            if isinstance(example, str) and len(example) > 50:
                example = example[:50] + '...'
            print(f"     • {field}: {type(example).__name__} (e.g., {example})")
        
        # Show different update types
        print(f"\n🔄 Update Types Found:")
        print("=" * 25)
        
        update_types = {}
        for match in result['matches']:
            update_type = match['metadata'].get('update_type', 'unknown')
            update_types[update_type] = update_types.get(update_type, 0) + 1
        
        for update_type, count in update_types.items():
            print(f"   {update_type}: {count} vectors")
        
    except Exception as e:
        print(f"❌ Error analyzing metadata: {e}")

if __name__ == "__main__":
    show_metadata_structure() 