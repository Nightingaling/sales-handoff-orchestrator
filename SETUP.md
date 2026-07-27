# Complete Setup Guide for Sales Handoff Orchestrator

This guide provides step-by-step instructions to configure all required integrations: **Salesforce**, **Slack**, **IBM Watsonx**, and **Jira**.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Salesforce Setup](#salesforce-setup)
4. [Salesforce Configuration](#salesforce-configuration)
5. [Slack Setup](#slack-setup)
6. [IBM Watsonx Setup](#ibm-watsonx-setup)
7. [Jira Setup](#jira-setup)
8. [Environment Configuration](#environment-configuration)
9. [Running the Application](#running-the-application)
10. [Testing the Integration](#testing-the-integration)

---

## Prerequisites

Before starting, ensure you have:

- Python 3.8 or higher installed
- Access to a Salesforce Developer organization
- A Slack workspace where you have admin permissions
- An IBM Cloud account with watsonx.ai enabled
- A Jira Cloud or Server instance with admin access
- A publicly accessible URL for webhook callbacks (use **ngrok** for local development)

### Local Development with ngrok

If running locally, download and set up **ngrok** to expose your application to the internet:

```bash
# Download ngrok: https://ngrok.com/download
# Run ngrok to expose port 8000
ngrok http 8000
```

This will provide a public URL like `https://your-subdomain.ngrok.io` that you'll use in webhook configurations.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Nightingaling/sales-handoff-orchestrator.git
   cd sales-handoff-orchestrator
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment configuration file:**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` with your credentials (see [Environment Configuration](#environment-configuration) below)**

---

## Salesforce Setup

Important: Required Opportunity Attachments

- For the AI handoff orchestrator to work correctly, each Opportunity MUST have the relevant supporting documents attached so the system can extract distinct data points. At minimum, attach any of the following (when applicable):
  - Signed contracts
  - Statements of Work (SOWs)
  - Security and Compliance Reviews
  - Pricing Approvals
  - Transcripts (e.g., customer call transcripts)

- File format requirements: All attached documents must be in either PDF (.pdf) or plain text (.txt) format. The system will only process PDF or .txt attachments; other formats (e.g., .docx, .pptx, images) are not supported and may cause missing data in the AI analysis.

- Where to attach: Attach these files directly to the Opportunity record in Salesforce (use the Files/Notes & Attachments related list depending on your org configuration).

- Helpful tip: If you only have Office documents, export them to PDF before attaching. For audio/video transcripts, provide the transcript as a .txt file.

## Salesforce Configuration

### Step 1: Get Salesforce Username (For Salesforce Environment Variables)

1. Log in to your Salesforce Developer organization.
2. In Salesforce, go to your **User Profile** (click your avatar in top-right corner).
3. Click **Settings**.
4. Your **Username** should look like: `email.************@agentforce.com`.

### Step 2: Reset Security Token (For Salesforce Environment Variables)

1. In Salesforce, go to your **User Profile** (click your avatar in top-right corner).
2. Click **Settings**.
3. In the left sidebar, click **Reset My Security Token**.
4. You'll receive an email with your **Security Token**.

### Step 3: Get Instance URL (For Salesforce Environment Variables)

1. In Salesforce, go to **Setup** (click the gear icon in top-right corner).
2. In the Quick Find box, type `Company Information`.
3. The **Instance** field is located under **Organization Edition**.
4. Your **Instance URL** will then be https://`your-instance`.salesforce.com.

### Step 4: Configure Salesforce Outbound Messaging
Follow the detailed steps in [SALESFORCE_WEBHOOK_SETUP.md](./SALESFORCE_WEBHOOK_SETUP.md) to:
- Create an **Outbound Message** for Opportunity objects.
- Create a **Record-Triggered Flow** that triggers when Stage = "Closed Won".
- Set the webhook endpoint to: `https://your-app-domain.com/api/salesforce/webhook` or `https://your-ngrok-subdomain.ngrok.io/api/salesforce/webhook`.

### Step 5: Create Custom Fields
Create a custom field `Commission_Lock__c` on the Opportunity object.

1. Go to **Setup** → **Object Manager** → **Opportunity** → **Fields & Relationships**.
2. Click **New** and select **Checkbox**.
3. Set **Field Label** to `Commission Lock` and **Field Name** will be `Commission_Lock` (auto-generated).
4. (Optional) Write in **Description**: `Indicates if commission payout is locked due to discrepancy`.
5. Nothing to amend for **Establish field-level security** and **Add to page layouts**. Remember to **Save**.
6. Ensure the **API Name** is `Commission_Lock__c`.

### Step 6: Configure System Permissions

1. In Salesforce, go to **Setup** (click the gear icon in top-right corner).
2. In the Quick Find box, type `Permission Sets`.
3. Click **New**.
4. Set **Label** to `API Login Access` and **API Name** will be `API_Login_Access` (auto-generated).
5. **Session Activation Required** remains as deactivated.
6. Set **License** as **--None--**, then **Save**.
7. Go to **Manage Assignments** → **Add Assignment**.
8. Check the box next to your profile (ignore other profile).
9. Click **Next**, then click **Assign**, then click **Done**.
10. In the left sidebar, click **Permission Sets**.
11. Click **API Login Access**.
12. Scroll all the way down, and click **System Permissions**.
13. Click **Edit**.
14. In **System Permissions**, find this setting: **Use Any API Auth**. Check the box next to it and click **Save**.

### Step 7: Enable Salesforce API Access
To allow the application to authenticate with your Salesforce environment.

1. In Salesforce, go to **Setup** (click the gear icon in top-right corner).
2. Search for `User Interface` in the Quick Find box.
3. Check the box for **Enable SOAP API login()** and **Enable SOAP API login() to users with the Use Any API Auth user permission** and save.

> ⚠️ **DEPRECATION WARNING: SUMMER '27**
> Salesforce is retiring the SOAP API `login()` method in the Summer 2027 release. This application currently requires it for basic username/password authentication. 
> 
> *Note: If this checkbox is greyed out, or you receive an API login error, you may need to go to **Setup > Release Updates** and ensure the test run for "Platform SOAP API login() Retirement" is **Disabled**.*

### Step 8: Whitelist Your IP Address
Bypass the security token requirement.

1. In Salesforce, go to **Setup** (click the gear icon in top-right corner).
2. Search for `Network Access` in the Quick Find box.
3. Click **New**. Enter your public IP address in both the **Start IP Address** and **End IP Address** fields, then click **Save**.

> Tip: How to find your public IP address
> 1. Launch your command prompt.
> 2. Type `curl icanhazip.com`.
> 3. Copy the output from the console.

### Salesforce Environment Variables

```
SALESFORCE_USERNAME=your_salesforce_username@example.com
SALESFORCE_PASSWORD=your_salesforce_password
SALESFORCE_SECURITY_TOKEN=your_security_token
SALESFORCE_INSTANCE_URL=https://test.salesforce.com
```

---

## Slack Setup

### Step 1: Create a Slack App

1. Open the [Slack website](https://slack.com/) and click Get started, then choose to Create a new Slack Workspace.
2. Enter your email address and click Continue, or continue with Apple or Google.
3. Follow the prompts to name your workspace and invite team members (skip if there is no team members to invite).
4. Navigate to [Slack API Dashboard](https://api.slack.com/apps) and sign in.
5. Click **Create New App** and select the **From scratch option**.
6. Enter your **App Name** (e.g., "Sales Handoff Orchestrator") and select the wrokspace you created in the previous step to serve as your development environment.
7. Click **Create App**.

### Step 2: Enable Socket Mode (Optional)

For production deployments without ngrok:
1. In your app settings, go to **Socket Mode** and enable it.
2. Generate an **App-Level Token** with `connections:write` scope.

### Step 3: Configure OAuth Scopes

1. Navigate to [Slack API Dashboard](https://api.slack.com/apps) and select your app.
2. Go to **OAuth & Permissions** under **Features** in the left sidebar.
3. Scroll down to the Scopes section. Under **Bot Token Scopes**, click **Add an OAuth Scope**.Add the following scope: `chat:write` — To allow the bot to send messages (Ignore if `chat:write` scope has been added).

### Step 4: Generate Bot Token

1. Scroll back to the top of the page. Click **Install to Workspace**. Review the permissions and click **Allow**.
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`). Save this as `SLACK_BOT_TOKEN` in your `.env`.

### Step 5: Enable Interactivity

1. Go to **Interactivity & Shortcuts**.
2. Enable **Interactivity**.
3. Set the **Request URL** to: `https://your-app-domain.com/api/slack/interactive` or `https://your-ngrok-subdomain.ngrok.io/api/slack/interactive` (Only when Socket Mode is not enabled).
4. Save changes.

### Step 6: Invite Bot to Channels & Retrieve Channel ID

1. In Slack, go to your target channel's message box and type /invite @`BotName`, then press Enter. Alternatively, you can just mention the bot by typing @`BotName` in a message, and Slack will automatically ask if you want to add it to the channel.
2. Look at the URL, you can spot your channel ID at the end of the URL. For the URL `app.slack.com/client/T0ABCDEFG9H/C0AA00ZBLN1`, the **Channel ID** is `C0AA00ZBLN1`.

**Note:** The `SLACK_TECH_REVIEW_CHANNEL_ID` is used for flagging high-severity discrepancies. Use the same channel as `SLACK_CHANNEL_ID` if you don't have a separate review channel.

For example, your `.env` file should look something like this (if you choose to use separate channels):
```
# ... other environment variables ...
SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
SLACK_CHANNEL_ID="your-main-channel-id"
SLACK_TECH_REVIEW_CHANNEL_ID="your-tech-review-channel-id"
```

Or, if you decide to use one all-purpose channel:
```
# ... other environment variables ...
SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
SLACK_CHANNEL_ID="your-main-channel-id"
SLACK_TECH_REVIEW_CHANNEL_ID="your-main-channel-id" # Same ID as above
```

### Slack Environment Variables

```
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=C123456789ABCDEF
SLACK_TECH_REVIEW_CHANNEL_ID=C9876543210FEDCBA
```

---

## IBM Watsonx Setup

### Step 1: Access IBM Cloud

Go to [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com/registration/stepone?context=wx&preselect_region=true) to create an account or log in.

### Step 2: Create API Key & Get Project ID

1. Locate the **Developer access** panel.
2. Click the dropdown menu labeled **Project or deployment space**.
3. Select the sandbox project that is created automatically for you.
4. Copy the **Project ID** that is automatically retrieved for you.
5. Verify your endpoint in the watsonx.ai URL field is `https://us-south.ml.cloud.ibm.com`.
6. Click **Create API key**.
7. Enter your IBM Cloud API key **Name** field as `sales-handoff-orchestrator`.
8. **Choose what to do if this key is leaked:** **Disable the leaked key**.
9. Click **Create**.
10. Now, the API key has been successfully created! Copy the API key or click download to save it. You won’t be able to see this API key again, so you can’t retrieve it later.

### Step 3: Verify watsonx Model Availability

The system uses IBM's foundation models via watsonx.ai. Verify that your region supports the model being used in `src/watsonx_connector.py` (currently configured for `meta-llama/llama-3-3-70b-instruct`).

**Supported Regions:**
- `https://us-south.ml.cloud.ibm.com` (US South)
- `https://eu-gb.ml.cloud.ibm.com` (London)
- `https://jp-tok.ml.cloud.ibm.com` (Tokyo)

### Watsonx Environment Variables

```
WATSONX_API_KEY=your_ibm_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

---

## Jira Setup

### Step 1: Create or Access Jira Cloud Instance

1. Go to [atlassian.com](https://www.atlassian.com) and log in.
2. Access your Jira Cloud instance (or create a new one).

### Step 2: Get Your Instance URL

Your Jira instance URL will be in the format: `https://mycompany.atlassian.net`.

### Step 3: Create or Get API Token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Click **Create API token**.
3. Give it a name (e.g., "Sales Handoff Orchestrator").
4. Set your token expiration to one year, or a custom duration.
5. Copy your API token and save it somewhere safe. You can't recover the API token after you're done with this step.

### Step 4: Get Your Lead Account ID and Username

1. Open your Jira Cloud instance.
2. Click your profile picture.
3. Click **Profile**.
4. Look at the URL in your browser address bar.
5. Copy the alphanumeric string between `/people/` and `?cloudId=`. For the URL `domain.atlassian.net/jira/people/557058:f58131cb-b67d?cloudId=1as23f45-6hhj-76hh-yy13-123ert34567g`, the **Lead Account ID** is `557058:f58131cb-b67d`.
6. On the same page, note that your Jira **Username** is the email address located in the **Email** field.

### Jira Environment Variables

```
JIRA_SERVER=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_LEAD_ACCOUNT_ID=your_jira_lead_account_id
```

---

## Environment Configuration

### Step 1: Update `.env` File

Open the `.env` file and fill in all the credentials:

```dotenv
# Salesforce API Credentials
SALESFORCE_USERNAME=your_salesforce_username@example.com
SALESFORCE_PASSWORD=your_salesforce_password
SALESFORCE_SECURITY_TOKEN=your_security_token_from_email
SALESFORCE_INSTANCE_URL=https://test.salesforce.com

# Jira API Credentials
JIRA_SERVER=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_LEAD_ACCOUNT_ID=your_jira_account_id

# IBM Watsonx Configuration
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Slack Credentials
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=C123456789ABCDEF
SLACK_TECH_REVIEW_CHANNEL_ID=C9876543210FEDCBA
```

### Step 2: Validate Configuration

Run a quick validation to ensure all credentials are set:

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = [
    'SALESFORCE_USERNAME', 'SALESFORCE_PASSWORD', 'SALESFORCE_SECURITY_TOKEN',
    'SALESFORCE_INSTANCE_URL', 'JIRA_SERVER', 'JIRA_USERNAME', 'JIRA_API_TOKEN',
    'JIRA_LEAD_ACCOUNT_ID', 'WATSONX_API_KEY', 'WATSONX_PROJECT_ID',
    'SLACK_BOT_TOKEN', 'SLACK_CHANNEL_ID', 'SLACK_TECH_REVIEW_CHANNEL_ID'
]

missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'Missing environment variables: {missing}')
else:
    print('✓ All required environment variables are set!')
"
```

---

## Running the Application

### Step 1: Start the FastAPI Server

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 2: Verify API Endpoints

Visit `http://localhost:8000/docs` to see the interactive API documentation (Swagger UI).

### Step 3: Expose Locally with ngrok (for Webhooks)

In another terminal, run:
```bash
ngrok http 8000
```

You'll get a public URL like `https://your-subdomain.ngrok.io`. Use this URL in:
- Salesforce Outbound Message endpoint
- Slack Interactivity Request URL

---

## Testing the Integration

### Test 1: Verify Slack Connection

```bash
curl -X POST http://localhost:8000/api/slack/interactive \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'payload={"type":"url_verification","challenge":"test_challenge"}'
```

Expected response: `{"challenge": "test_challenge"}`

### Test 2: Test Salesforce Webhook

Create a test opportunity in Salesforce and change its stage to "Closed Won":
1. Log into Salesforce.
2. Go to **Opportunities**.
3. Create a new opportunity with required fields.
4. Set the stage to **Closed Won**.
5. Save.

Check your application logs. You should see:
```
INFO: Received Salesforce webhook for Opportunity ID: [ID]
INFO: Processing opportunity in background...
```

### Test 3: Check Slack Messages

After triggering a handoff from Salesforce:
1. Go to your Slack channel specified in `SLACK_CHANNEL_ID`.
2. You should see an approval message with:
   - Deal details (account name, amount, AE name)
   - AI-generated discrepancies (if any)
   - Drafted kickoff agenda
   - Approval buttons

### Test 4: Verify Jira Project Creation

After approving a handoff in Slack:
1. Go to your Jira instance.
2. You should see a new project created with the format: `Onboarding: [Opportunity Name]`
3. An Epic with sub-tasks for each deliverable should be created.

### Test 5: Check Application Logs

Monitor logs for errors:

```bash
# If running with logging enabled
tail -f application.log

# Or check console output during development
```

---

## Troubleshooting

### Salesforce Issues

**Error: "Salesforce authentication failed"**
- Verify `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, and `SALESFORCE_SECURITY_TOKEN`.
- Ensure the security token was recently reset; old tokens may be invalid.
- Check that your Salesforce instance URL is correct (Production vs. Sandbox).

**Error: "Webhook not receiving calls"**
- Verify the Outbound Message is activated in Salesforce.
- Ensure the Flow is activated and conditions are correct.
- Test with ngrok: `ngrok http 8000` and update Salesforce with the public URL.

### Slack Issues

**Error: "Bot is not in the channel"**
- Go to the Slack channel and manually add the bot via integrations.
- Verify `SLACK_CHANNEL_ID` matches the actual channel ID.

**Error: "Invalid token"**
- Regenerate your `SLACK_BOT_TOKEN` from api.slack.com/apps.
- Ensure the token starts with `xoxb-` (not `xoxp-` which is a user token).

### Watsonx Issues

**Error: "Rate limit hit (429)"**
- The system has built-in retry logic with exponential backoff. Retries will continue automatically.
- Check your Watsonx quota in IBM Cloud.

**Error: "Model not found"**
- Verify the model ID in `src/watsonx_connector.py` is available in your region.
- Check watsonx documentation for available models.

### Jira Issues

**Error: "Failed to authenticate with Jira"**
- Verify `JIRA_SERVER`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`.
- For Jira Cloud, use your email as username and the API token from id.atlassian.com.

**Error: "Project creation failed"**
- Ensure `JIRA_LEAD_ACCOUNT_ID` is set correctly.
- For Jira Cloud, this should be your Account ID (UUID format).
- For Jira Server, use your username.

**Error: "Custom field not found"**
- The system logs available fields. Check logs for the list.
- Ensure your Jira instance has the required custom fields or the system will skip them.

---

## Security Best Practices

1. **Never commit `.env` file to version control.** Add it to `.gitignore`.
2. **Use production Salesforce instances** for production deployments, not sandboxes.
3. **Rotate API tokens regularly** (quarterly recommended).
4. **Use environment variables** for all secrets; never hardcode credentials.
5. **Enable SSL verification** in production (disable `verify=False` in `salesforce_connector.py`).
6. **Restrict ngrok access** in local development by using ngrok authentication.
7. **Monitor logs regularly** for authentication failures or API errors.

---

## Next Steps

After completing setup:

1. Review the [README.md](./README.md) for application overview.
2. Check [SALESFORCE_WEBHOOK_SETUP.md](./SALESFORCE_WEBHOOK_SETUP.md) for detailed Salesforce configuration.
3. Test with a sample opportunity to ensure end-to-end integration works.
4. Monitor the application logs during your first handoff to catch any configuration issues.

For questions or issues, refer to the official documentation:
- [Salesforce API Documentation](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/)
- [Slack API Documentation](https://api.slack.com/docs)
- [watsonx.ai Documentation](https://cloud.ibm.com/docs/watsonx)
- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
