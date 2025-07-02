import os
import sys
import re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, request, jsonify
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from utils.embedding import get_embedding
from utils.pinecone_utils import query_pinecone, query_pinecone_with_metadata
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Simple cache to prevent duplicate responses
import time
recent_queries = {}  # {user_id: {query_hash: timestamp}}

def clean_user_query(text, bot_user_id):
    """Remove bot mention from the query text"""
    # Remove <@UXXXXXXXXX> mentions
    text = re.sub(r'<@[A-Z0-9]+>', '', text)
    # Remove extra whitespace
    text = text.strip()
    return text

def generate_smart_response_with_sources(results_with_metadata, query):
    """Use GPT to analyze retrieved context and generate a helpful response with channel sources"""
    if not results_with_metadata:
        return f"I couldn't find any relevant information about '{query}' in the conversation history. Try rephrasing your question or asking about something else that was discussed."
    
    # Deduplicate and clean results
    unique_results = []
    seen_content = set()
    channels_found = set()
    
    for result in results_with_metadata:
        text = result['text']
        channel_name = result['channel_name']
        
        # Create a simplified version for comparison (remove usernames, whitespace)
        simplified = re.sub(r'\[.*?\]:', '', text.lower()).strip()
        simplified = ' '.join(simplified.split())
        
        # Only add if we haven't seen very similar content
        is_duplicate = False
        for seen in seen_content:
            if len(set(simplified.split()) & set(seen.split())) / max(len(simplified.split()), len(seen.split())) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate and len(text.strip()) > 20:
            unique_results.append(result)
            seen_content.add(simplified)
            channels_found.add(channel_name)
    
    # Limit to top 3 most relevant unique results
    context_parts = []
    for result in unique_results[:3]:
        context_parts.append(f"From #{result['channel_name']}:\n{result['text']}")
    
    context = "\n\n".join(context_parts)
    
    # Create a prompt for GPT to analyze the context
    prompt = f"""You are a helpful assistant that analyzes Slack conversation excerpts to answer questions. 

User's Question: "{query}"

Relevant Conversation Excerpts:
{context}

Based on the conversation excerpts above, provide a clear, concise answer to the user's question. 

Guidelines:
- Provide ONE cohesive answer, don't repeat information
- Summarize the key information that directly answers their question
- Mention specific people, dates, amounts, or details when relevant
- If the information is incomplete, say so briefly
- Keep it conversational and helpful
- Avoid redundancy - don't repeat the same facts multiple times
- Be concise but complete

Answer:"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes Slack conversations to provide clear, concise answers. Avoid repetition and be direct."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Add detailed source information with dates
        source_details = []
        for result in unique_results[:3]:  # Show details for top 3 sources
            channel_name = result['channel_name']
            timestamp = result['timestamp']
            
            # Convert timestamp to readable date
            try:
                import datetime
                date_obj = datetime.datetime.fromtimestamp(float(timestamp))
                date_str = date_obj.strftime("%b %d, %Y")
            except:
                date_str = "unknown date"
            
            source_details.append(f"#{channel_name} ({date_str})")
        
        if source_details:
            if len(source_details) == 1:
                source_info = f"\n\n📍 _Source: {source_details[0]}_"
            else:
                sources_list = ", ".join(source_details)
                source_info = f"\n\n📍 _Sources: {sources_list}_"
        else:
            source_info = "\n\n📍 _Source: Slack conversation history_"
        
        ai_response += source_info
        
        return ai_response
        
    except Exception as e:
        print(f"Error generating AI response: {e}")
        # Fallback to simple formatting if AI fails
        return format_response_simple_with_sources(results_with_metadata, query)

def generate_smart_response(results, query):
    """Use GPT to analyze retrieved context and generate a helpful response"""
    if not results:
        return f"I couldn't find any relevant information about '{query}' in the conversation history. Try rephrasing your question or asking about something else that was discussed."
    
    # Deduplicate and clean results
    unique_results = []
    seen_content = set()
    
    for result in results:
        # Create a simplified version for comparison (remove usernames, whitespace)
        simplified = re.sub(r'\[.*?\]:', '', result.lower()).strip()
        simplified = ' '.join(simplified.split())
        
        # Only add if we haven't seen very similar content
        is_duplicate = False
        for seen in seen_content:
            if len(set(simplified.split()) & set(seen.split())) / max(len(simplified.split()), len(seen.split())) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate and len(result.strip()) > 20:
            unique_results.append(result)
            seen_content.add(simplified)
    
    # Limit to top 3 most relevant unique results
    context = "\n\n".join(unique_results[:3])
    
    # Create a prompt for GPT to analyze the context
    prompt = f"""You are a helpful assistant that analyzes Slack conversation excerpts to answer questions. 

User's Question: "{query}"

Relevant Conversation Excerpts:
{context}

Based on the conversation excerpts above, provide a clear, concise answer to the user's question. 

Guidelines:
- Provide ONE cohesive answer, don't repeat information
- Summarize the key information that directly answers their question
- Mention specific people, dates, amounts, or details when relevant
- If the information is incomplete, say so briefly
- Keep it conversational and helpful
- Avoid redundancy - don't repeat the same facts multiple times
- Be concise but complete

Answer:"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes Slack conversations to provide clear, concise answers. Avoid repetition and be direct."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Add a note about the source
        ai_response += "\n\n💡 _This summary is based on your Slack conversation history._"
        
        return ai_response
        
    except Exception as e:
        print(f"Error generating AI response: {e}")
        # Fallback to simple formatting if AI fails
        return format_response_simple(results, query)

def format_response_simple_with_sources(results_with_metadata, query):
    """Simple fallback response formatting with channel sources"""
    response = f"Here's what I found about '{query}':\n\n"
    channels_found = set()
    
    for i, result in enumerate(results_with_metadata, 1):
        text = result['text']
        channel_name = result['channel_name']
        channels_found.add(channel_name)
        
        # Truncate very long results
        if len(text) > 300:
            text = text[:300] + "..."
        response += f"**{i}.** From #{channel_name}: {text}\n\n"
    
    # Add source summary
    if len(channels_found) == 1:
        source_info = f"📍 _Source: #{list(channels_found)[0]} channel_"
    else:
        channels_list = ", ".join([f"#{ch}" for ch in sorted(channels_found)])
        source_info = f"📍 _Sources: {channels_list}_"
    
    response += source_info
    return response

def format_response_simple(results, query):
    """Simple fallback response formatting"""
    response = f"Here's what I found about '{query}':\n\n"
    
    for i, result in enumerate(results, 1):
        # Truncate very long results
        if len(result) > 300:
            result = result[:300] + "..."
        response += f"**{i}.** {result}\n\n"
    
    response += "💡 _These are excerpts from your Slack conversations._"
    return response

def handle_user_query(user_query, channel, user_id):
    """Process user query and return response"""
    try:
        print(f"Processing query: '{user_query}' from user {user_id} in channel {channel}")
        
        # Clean the query
        clean_query = clean_user_query(user_query, os.getenv("SLACK_BOT_USER_ID"))
        
        if not clean_query:
            return "Hi! Ask me anything about your Slack conversations. For example: 'What did we discuss about the project?' or 'Tell me about recent decisions.'"
        
        # Check for recent duplicate queries from same user
        import hashlib
        query_hash = hashlib.md5(clean_query.lower().encode()).hexdigest()
        current_time = time.time()
        
        # Clean old entries (older than 30 seconds)
        if user_id in recent_queries:
            recent_queries[user_id] = {
                hash_key: timestamp for hash_key, timestamp in recent_queries[user_id].items()
                if current_time - timestamp < 30
            }
        
        # Check if this query was recently processed
        if user_id in recent_queries and query_hash in recent_queries[user_id]:
            time_since = current_time - recent_queries[user_id][query_hash]
            if time_since < 10:  # Ignore if same query within 10 seconds
                print(f"Ignoring duplicate query from {user_id} (asked {time_since:.1f}s ago)")
                return None
        
        # Record this query
        if user_id not in recent_queries:
            recent_queries[user_id] = {}
        recent_queries[user_id][query_hash] = current_time
        
        # Get embedding for the query
        embedding = get_embedding(clean_query)
        
        # Query Pinecone for relevant context with metadata
        results_with_metadata = query_pinecone_with_metadata(embedding, top_k=5)
        
        # Generate smart response using GPT
        response = generate_smart_response_with_sources(results_with_metadata, clean_query)
        return response
        
    except Exception as e:
        print(f"Error processing query: {e}")
        return f"Sorry, I encountered an error while searching for information about '{clean_query}'. Please try again."

@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        data = request.json
        
        # Slack URL verification
        if data.get("type") == "url_verification":
            return data.get("challenge")
        
        # Handle events
        if "event" in data:
            event = data["event"]
            
            # Multiple checks to ignore bot's own messages and avoid loops
            bot_user_id = os.getenv("SLACK_BOT_USER_ID")
            
            # Ignore if message is from the bot itself
            if event.get("user") == bot_user_id:
                print(f"Ignoring message from bot user: {bot_user_id}")
                return "", 200
            
            # Ignore if message has bot_id (another way messages from bots are identified)
            if event.get("bot_id"):
                print(f"Ignoring message from bot_id: {event.get('bot_id')}")
                return "", 200
            
            # Ignore if message subtype indicates it's from a bot
            if event.get("subtype") in ["bot_message", "message_changed", "message_deleted"]:
                print(f"Ignoring message with subtype: {event.get('subtype')}")
                return "", 200
            
            # Handle app mentions
            if event.get("type") == "app_mention":
                user_query = event.get("text", "")
                channel = event.get("channel")
                user_id = event.get("user")
                
                # Additional check: ignore if the message looks like our own response format
                if "Here's what I found about" in user_query or "**Result" in user_query:
                    print("Ignoring message that looks like bot's own response")
                    return "", 200
                
                print(f"Processing app mention from user {user_id}: {user_query}")
                response = handle_user_query(user_query, channel, user_id)
                
                # Only respond if we got a response (not a duplicate)
                if response:
                    client.chat_postMessage(
                        channel=channel,
                        text=response,
                        thread_ts=event.get("ts")  # Reply in thread if mentioned in a thread
                    )
            
            # Handle direct messages (if bot is in a DM)
            elif event.get("type") == "message" and event.get("channel_type") == "im":
                user_query = event.get("text", "")
                channel = event.get("channel")
                user_id = event.get("user")
                
                # Additional check: ignore if the message looks like our own response format
                if "Here's what I found about" in user_query or "**Result" in user_query:
                    print("Ignoring DM that looks like bot's own response")
                    return "", 200
                
                print(f"Processing DM from user {user_id}: {user_query}")
                response = handle_user_query(user_query, channel, user_id)
                
                # Only respond if we got a response (not a duplicate)
                if response:
                    client.chat_postMessage(
                        channel=channel,
                        text=response
                    )
        
        return "", 200
        
    except Exception as e:
        print(f"Error in slack_events: {e}")
        return "", 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Slack bot is running"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    print("🤖 Starting Slack bot server...")
    print(f"📡 Listening for Slack events on port {port}")
    print("💬 You can now mention the bot in Slack to ask questions!")
    app.run(host="0.0.0.0", port=port, debug=False) 