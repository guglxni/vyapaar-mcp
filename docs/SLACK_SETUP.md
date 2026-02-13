# Slack Human-in-the-Loop Setup Guide

Vyapaar MCP uses Slack to request human approval for high-value payouts or flagged transactions. This guide walks you through creating a Slack App and obtaining the necessary credentials.

---

## 1. Create a Slack App

1.  Go to the [Slack API: Your Apps](https://api.slack.com/apps) page.
2.  Click **"Create New App"**.
3.  Choose **"From scratch"**.
4.  **App Name**: `Vyapaar MCP`
5.  **Workspace**: Select the workspace where you want the alerts to appear.
6.  Click **"Create App"**.

---

## 2. Configure Scopes & Bot Token

Slack needs specific permissions (Scopes) to send messages.

1.  In the left sidebar, go to **"OAuth & Permissions"**.
2.  Scroll down to **"Scopes"** > **"Bot Token Scopes"**.
3.  Click **"Add an OAuth Scope"** and add these three:
    *   `chat:write` (Allows sending approval requests).
    *   `chat:write.public` (Allows sending to public channels without joining).
    *   `incoming-webhook` (Optional: if you prefer the webhook approach).
4.  Scroll back up and click **"Install to Workspace"**.
5.  Click **"Allow"** to confirm.

### Copy the Token
After installation, you will see a **"Bot User OAuth Token"** (starts with `xoxb-`).
*   **SAVE THIS AS**: `SLACK_BOT_TOKEN` in your environment.

---

## 3. Obtain Team ID & Channel ID

### Get the Team ID
1.  Open Slack in your **web browser** (not the desktop app).
2.  Look at the URL in the address bar.
3.  The Team ID is the string starting with `T` immediately following `client/`.
    *   *Example URL*: `https://app.slack.com/client/T01ABCDEFGH/...`
    *   **Team ID**: `T01ABCDEFGH`
*   **SAVE THIS AS**: `SLACK_TEAM_ID`.

### Get the Channel ID
1.  Create a new channel in Slack (e.g., `#vyapaar-alerts`).
2.  Right-click the channel name in the sidebar.
3.  Select **"View channel details"**.
4.  Scroll to the bottom of the pop-up. You will see the **Channel ID** (starts with `C`).
    *   *Example*: `C01GHJKLMN`
*   **SAVE THIS AS**: `SLACK_CHANNEL_ID`.

---

## 4. Final Integration Step

To ensure the bot can post, you must invite it to the channel:
1.  Go to your alerts channel (e.g., `#vyapaar-alerts`).
2.  Type: `/invite @Vyapaar MCP`.

---

## 5. Summary of Credentials

| Variable | Source | Example |
| :--- | :--- | :--- |
| `SLACK_BOT_TOKEN` | OAuth & Permissions | `xoxb-1234-5678-abcd` |
| `SLACK_TEAM_ID` | Browser URL | `T01ABCDEFGH` |
| `SLACK_CHANNEL_ID` | Channel Details | `C01GHJKLMN` |

These keys will be used by the **Slack MCP Server** (via Archestra) to bridge the communication between Vyapaar and your human team.
