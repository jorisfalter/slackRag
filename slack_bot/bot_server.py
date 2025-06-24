import os
import sys
import re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, request, jsonify
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from utils.embedding import get_embedding
from utils.pinecone_utils import query_pinecone
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def clean_user_query(text, bot_user_id):
    """Remove bot mention from the query text"""
    # Remove <@UXXXXXXXXX> mentions
    text = re.sub(r'<@[A-Z0-9]+>', '', text)
    # Remove extra whitespace
    text = text.strip()
    return text

def format_response(results, query):
    """Format the response with context and sources"""
    if not results:
        return f"I couldn't find any relevant information about '{query}' in the conversation history. Try rephrasing your question or asking about something else that was discussed."
    
    response = f"Here's what I found about '{query}':\n\n"
    
    for i, result in enumerate(results, 1):
        # Truncate very long results
        if len(result) > 500:
            result = result[:500] + "..."
        response += f"**Result {i}:**\n{result}\n\n"
    
    response += "💡 _These are excerpts from your Slack conversations. Ask me more specific questions for better results!_"
    return response

def handle_user_query(user_query, channel, user_id):
    """Process user query and return response"""
    try:
        print(f"Processing query: '{user_query}' from user {user_id} in channel {channel}")
        
        # Clean the query
        clean_query = clean_user_query(user_query, os.getenv("SLACK_BOT_USER_ID"))
        
        if not clean_query:
            return "Hi! Ask me anything about your Slack conversations. For example: 'What did we discuss about the project?' or 'Tell me about recent decisions.'"
        
        # Get embedding for the query
        embedding = get_embedding(clean_query)
        
        # Query Pinecone for relevant context
        results = query_pinecone(embedding, top_k=3)
        
        # Format and return response
        response = format_response(results, clean_query)
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