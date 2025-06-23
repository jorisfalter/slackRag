import os
from flask import Flask, request
from slack_sdk.web import WebClient
from utils.embedding import get_embedding
from utils.pinecone_utils import query_pinecone
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    # Slack URL verification
    if data.get("type") == "url_verification":
        return data.get("challenge")
    # Handle app_mention events
    if "event" in data:
        event = data["event"]
        if event.get("type") == "app_mention":
            user_query = event.get("text")
            channel = event.get("channel")
            embedding = get_embedding(user_query)
            results = query_pinecone(embedding)
            answer = "\n\n".join(results)
            client.chat_postMessage(channel=channel, text=f"Here's what I found:\n{answer}")
    return "", 200

if __name__ == "__main__":
    app.run(port=3000) 