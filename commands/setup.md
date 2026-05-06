---
description: Guides you through initial Slack app configuration for the slack-notify plugin. Validates existing tokens or walks you through creating a new Slack app.
---

# Slack Notify Setup

Run this procedure to configure Slack notifications for Claude Code. Do NOT skip steps.

## Step 1: Check for existing SLACK_BOT_TOKEN

Run the following to test whether a token is already configured:

```bash
python3 -c "
import urllib.request, json
req = urllib.request.Request(
    'https://slack.com/api/auth.test',
    headers={'Authorization': 'Bearer ' + __import__('os').environ['SLACK_BOT_TOKEN']}
)
r = json.loads(urllib.request.urlopen(req).read())
print('Token valid for team:', r.get('team')) if r.get('ok') else print('Token invalid:', r.get('error'))
"
```

**If the token is valid**, skip to Step 3.

**If the token is missing or invalid**, continue to Step 2.

## Step 2: Create a Slack app and get a bot token

Follow these steps in your browser:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**.
2. Choose **From scratch**.
3. Name it (e.g., `Claude Code`) and select your workspace, then click **Create App**.
4. In the left sidebar, go to **OAuth & Permissions**.
5. Scroll down to **Scopes** → **Bot Token Scopes** and add:
   - `chat:write`
   - `channels:read`
6. Scroll back up and click **Install to Workspace**, then click **Allow**.
7. Copy the **Bot User OAuth Token** (starts with `xoxb-...`).
8. Open `~/.claude/settings.json` and add the token under the `env` key:
   ```json
   {
     "env": {
       "SLACK_BOT_TOKEN": "xoxb-your-token-here"
     }
   }
   ```
9. Save the file.

After updating settings.json, re-run this command (`/slack:setup`) to validate the new token.

## Step 3: (Optional) Set a fallback SLACK_CHANNEL_ID

The plugin posts to a Slack channel whose name matches your project directory (e.g., `my-project` → `#my-project`). If no matching channel exists, it falls back to `SLACK_CHANNEL_ID`.

To set a fallback channel:

1. In Slack, open the channel you want to use as the fallback.
2. Click the channel name at the top to open its details.
3. Scroll down to find the **Channel ID** (starts with `C...`).
4. Add it to `~/.claude/settings.json`:
   ```json
   {
     "env": {
       "SLACK_BOT_TOKEN": "xoxb-your-token-here",
       "SLACK_CHANNEL_ID": "C0123456789"
     }
   }
   ```

## Step 4: Create project channels and invite the bot

For each project you want notifications in:

1. Create a Slack channel matching the project directory name (e.g., `#my-project` for `/Users/you/projects/my-project`).
2. Invite the bot to the channel:
   ```
   /invite @Claude Code
   ```
   (Replace `Claude Code` with whatever you named your app.)

Repeat for each project. The plugin will automatically route notifications to the matching channel.

## Done

Once the token is valid and channels are set up, Claude Code will post `Stop` and `Notification` events to Slack automatically — no further configuration needed.
