import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def list_all_channels():
    """List all channels that the bot can see"""
    try:
        print("🔍 Discovering available channels...\n")
        
        # Get bot info first
        auth_response = client.auth_test()
        bot_user_id = auth_response['user_id']
        print(f"Bot User ID: {bot_user_id}")
        print(f"Team: {auth_response['team']}\n")
        
        # List public channels
        print("📢 PUBLIC CHANNELS:")
        print("-" * 50)
        public_channels = client.conversations_list(
            types="public_channel",
            exclude_archived=True
        )
        
        for channel in public_channels['channels']:
            # Check if bot is a member
            try:
                members_response = client.conversations_members(channel=channel['id'])
                is_member = bot_user_id in members_response['members']
                member_status = "✅ MEMBER" if is_member else "❌ NOT MEMBER"
            except:
                member_status = "❓ UNKNOWN"
            
            print(f"#{channel['name']:<20} | {channel['id']} | {member_status}")
            if channel.get('purpose', {}).get('value'):
                print(f"   Purpose: {channel['purpose']['value']}")
            print()
        
        # List private channels (only ones bot is a member of)
        print("\n🔒 PRIVATE CHANNELS (bot is member of):")
        print("-" * 50)
        private_channels = client.conversations_list(
            types="private_channel",
            exclude_archived=True
        )
        
        for channel in private_channels['channels']:
            print(f"#{channel['name']:<20} | {channel['id']} | ✅ MEMBER")
            if channel.get('purpose', {}).get('value'):
                print(f"   Purpose: {channel['purpose']['value']}")
            print()
        
        # List DMs (if any)
        print("\n💬 DIRECT MESSAGES:")
        print("-" * 50)
        dm_channels = client.conversations_list(
            types="im",
            exclude_archived=True
        )
        
        if dm_channels['channels']:
            for channel in dm_channels['channels']:
                try:
                    # Get user info for the DM
                    user_info = client.users_info(user=channel['user'])
                    user_name = user_info['user']['profile'].get('display_name') or user_info['user']['real_name']
                    print(f"DM with {user_name:<15} | {channel['id']}")
                except:
                    print(f"DM {channel['id']}")
        else:
            print("No direct message channels found.")
        
        print(f"\n💡 To add the bot to a channel, use: /invite @ExportSlack")
        print(f"💡 Channels marked with ✅ MEMBER can be exported immediately.")
        
    except SlackApiError as e:
        print(f"❌ Error listing channels: {e.response['error']}")
        print(f"Full error: {e.response}")

if __name__ == "__main__":
    list_all_channels() 