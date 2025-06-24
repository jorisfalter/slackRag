# Deploy Slack Bot to Fly.io

## Prerequisites

1. **Install Fly.io CLI:**

   ```bash
   # macOS
   brew install flyctl

   # Or download from https://fly.io/docs/flyctl/install/
   ```

2. **Sign up and authenticate:**
   ```bash
   flyctl auth signup  # or flyctl auth login
   ```

## Deployment Steps

### 1. Launch your app

```bash
flyctl launch
```

- Choose a unique app name (or use `ragslack-madli`)
- Select a region close to you
- Don't deploy immediately (we need to set secrets first)

### 2. Set environment variables (secrets)

```bash
flyctl secrets set SLACK_BOT_TOKEN="xoxb-your-token"
flyctl secrets set SLACK_BOT_USER_ID="U0909CTDFE1"
flyctl secrets set SLACK_CHANNEL_ID="your-channel-id"
flyctl secrets set OPENAI_API_KEY="sk-your-key"
flyctl secrets set PINECONE_API_KEY="your-pinecone-key"
flyctl secrets set PINECONE_INDEX="your-index-name"
```

### 3. Deploy

```bash
flyctl deploy
```

### 4. Get your app URL

```bash
flyctl info
```

Your app will be available at: `https://your-app-name.fly.dev`

### 5. Configure Slack Event Subscriptions

1. Go to your Slack app settings: https://api.slack.com/apps
2. Click "Event Subscriptions"
3. Set Request URL to: `https://your-app-name.fly.dev/slack/events`
4. Subscribe to bot events:
   - `app_mentions:read`
   - `message.im`

## Useful Commands

- **View logs:** `flyctl logs`
- **Check status:** `flyctl status`
- **Scale app:** `flyctl scale count 1`
- **Update secrets:** `flyctl secrets set KEY=value`
- **Redeploy:** `flyctl deploy`

## Testing

Once deployed, test your bot:

1. Go to your Slack workspace
2. Mention the bot: `@ExportSlack what did we discuss about the project?`
3. Check logs: `flyctl logs` to see if it's working

## Troubleshooting

- **Check logs:** `flyctl logs` for errors
- **Health check:** Visit `https://your-app-name.fly.dev/health`
- **Restart app:** `flyctl restart`
