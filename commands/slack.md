---
description: Manage Slack notification settings. Use /slack to check status, /slack -on to enable, /slack -off to disable notifications.
---

# Slack Notification Control

Manage whether this plugin posts Slack notifications for Stop and Notification events.

## Usage

- `/slack` — show current notification status
- `/slack -on` — enable notifications
- `/slack -off` — disable notifications ("slack off")

## Implementation

Parse the arguments the user provided after `/slack`, then run the appropriate shell command below.

### If the argument is `-off`

Run this bash to create the marker file that mutes notifications:

```bash
python3 -c "
import os
from pathlib import Path
plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
if not plugin_root:
    print('Error: CLAUDE_PLUGIN_ROOT is not set. Is the plugin installed correctly?')
else:
    marker = Path(plugin_root, '.slack-notify-disabled')
    marker.touch()
    print('Slack notifications disabled. Time to slack off.')
"
```

Then tell the user: notifications are now **disabled**. Run `/slack -on` to re-enable. If the error is printed, advise the user to check their plugin installation or run `/slack:setup`.

### If the argument is `-on`

Run this bash to remove the marker file:

```bash
python3 -c "
import os
from pathlib import Path
plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
if not plugin_root:
    print('Error: CLAUDE_PLUGIN_ROOT is not set. Is the plugin installed correctly?')
else:
    marker = Path(plugin_root, '.slack-notify-disabled')
    if marker.exists():
        marker.unlink()
        print('Slack notifications enabled.')
    else:
        print('Slack notifications were already enabled.')
"
```

Then tell the user: notifications are now **enabled**. If the error is printed, advise the user to check their plugin installation or run `/slack:setup`.

### If no argument (bare `/slack`)

Run this bash to check status:

```bash
python3 -c "
import os
from pathlib import Path

plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
token = os.environ.get('SLACK_BOT_TOKEN', '')
cwd = os.getcwd()
project_name = Path(cwd).name

if plugin_root:
    marker = Path(plugin_root, '.slack-notify-disabled')
    disabled = marker.exists()
    root_display = plugin_root
    status = 'DISABLED' if disabled else 'ENABLED'
else:
    root_display = '(CLAUDE_PLUGIN_ROOT not set)'
    status = 'UNKNOWN (CLAUDE_PLUGIN_ROOT not set)'
token_status = 'set' if token else 'NOT SET'
print(f'Notifications: {status}')
print(f'SLACK_BOT_TOKEN: {token_status}')
print(f'Project channel: #{project_name}')
print(f'Plugin root: {root_display}')
"
```

Report the output to the user in a readable format:
- Whether notifications are enabled or disabled
- Whether `SLACK_BOT_TOKEN` is configured
- Which Slack channel the current project would post to (the `#<directory-name>` channel)

If `CLAUDE_PLUGIN_ROOT` is not set, mention that it is not configured and the plugin may have trouble locating the marker file.
