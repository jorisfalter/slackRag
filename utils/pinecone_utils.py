import os
from pinecone import Pinecone

def get_pinecone_client():
    # Initialize Pinecone client
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_index_name = os.getenv("PINECONE_INDEX")
    
    print(f"Debug - PINECONE_API_KEY: {pinecone_api_key[:10] + '...' if pinecone_api_key else 'None'}")
    print(f"Debug - PINECONE_INDEX: {pinecone_index_name}")
    
    if not pinecone_api_key:
        raise ValueError("PINECONE_API_KEY environment variable is not set")
    if not pinecone_index_name:
        raise ValueError("PINECONE_INDEX environment variable is not set")
    
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(pinecone_index_name)
    return index

def upsert_to_pinecone(id, embedding, text, metadata=None):
    index = get_pinecone_client()
    
    # Base metadata
    vector_metadata = {"text": text}
    
    # Add additional metadata if provided
    if metadata:
        vector_metadata.update(metadata)
    
    index.upsert(vectors=[{"id": id, "values": embedding, "metadata": vector_metadata}])

def query_pinecone(embedding, top_k=3):
    index = get_pinecone_client()
    result = index.query(vector=embedding, top_k=top_k, include_metadata=True)
    return [match['metadata']['text'] for match in result['matches']] 