# Salesforce Webhook Setup for Automated Handoff

This guide explains how to configure Salesforce to automatically trigger the Sales Handoff Orchestrator when an Opportunity's stage is changed to "Closed Won".

## Prerequisites

1.  **Publicly Accessible URL**: The Handoff Orchestrator application must be running and accessible from the public internet. Salesforce needs to be able to send a POST request to your application. If you are running this locally for testing, you can use a tool like [ngrok](https://ngrok.com/) to expose your local server.

2.  **Application is Running**: Make sure the FastAPI application (`src/main.py`) is running.

## Step-by-Step Configuration

### Step 1: Create an Outbound Message

First, we'll define the message that Salesforce will send.

1.  In Salesforce, navigate to **Setup**.
2.  Use the Quick Find box to search for **"Outbound Messages"** and select it.
3.  Click **"New Outbound Message"**.
4.  Select the **"Opportunity"** object from the dropdown and click **"Next"**.
5.  Fill in the details for the Outbound Message:
    *   **Name (Label)**: `Trigger Handoff Orchestrator`
    *   **Unique Name (API Name)**: `Trigger_Handoff_Orchestrator` (this will auto-fill)
    *   **Endpoint URL**: This is the public URL of your application followed by `/api/salesforce/webhook`. For example: `https://your-app-domain.com/api/salesforce/webhook` or `https://<your-ngrok-subdomain>.ngrok.io/api/salesforce/webhook`.
    *   **User to send as**: Select a user with sufficient permissions. This user will be the context user for the outbound message.
    *   **Send Session ID**: Leave this **unchecked**. Our endpoint does not require it.
    *   **Opportunity Fields to Send**: Select the **`Id`** field. This is the only field our application needs.
6.  Click **"Save"**.

### Step 2: Create a Record-Triggered Flow

Now, we'll create a Flow that triggers the Outbound Message. Workflow Rules are being deprecated, so using Flow Builder is the recommended approach.

1.  In **Setup**, use the Quick Find box to search for **"Flows"** and select it.
2.  Click **"New Flow"**.
3.  Select **"Record-Triggered Flow"** and click **"Create"**.
4.  Configure the Flow Trigger:
    *   **Object**: Select **"Opportunity"**.
    *   **Trigger the Flow When**: Select **"A record is updated"**.
    *   **Entry Conditions**:
        *   **Condition Requirements**: Select **"All Conditions Are Met (AND)"**.
        *   Add a condition:
            *   **Field**: `StageName`
            *   **Operator**: `Equals`
            *   **Value**: `Closed Won`
        *   Add another condition:
            *   **Field**: `ISCHANGED(StageName)` (You might need to use a formula resource for `ISCHANGED` if it's not directly available)
            *   **Operator**: `Equals`
            *   **Value**: `True`
    *   **Optimize the Flow for**: Select **"Actions and Related Records"**.
5.  Click **"Done"**.

### Step 3: Add an Action to the Flow

Now, add the Outbound Message as an action in your Flow.

1.  On the Flow canvas, click the **"+"** icon to add an element.
2.  Select **"Action"**.
3.  In the "Action" search box, type the **Unique Name (API Name)** of your Outbound Message, which is `Trigger_Handoff_Orchestrator`. You should see it appear under the "Outbound Message" category.
    *   **Label**: `Trigger Handoff Orchestrator` (This is the Label you gave your Outbound Message)
    *   **API Name**: `Trigger_Handoff_Orchestrator` (This is the Unique Name you gave your Outbound Message)
4.  Select the **"Trigger Handoff Orchestrator"** outbound message.
5.  Set the Input Values:
    *   **Record ID**: Set this to `{!$Record.Id}`. This passes the ID of the Opportunity that triggered the Flow to the Outbound Message.
6.  Click **"Done"**.

### Step 4: Save and Activate the Flow

Finally, save and activate your Flow.

1.  Click **"Save"** in the top right corner.
2.  Enter a **Flow Label**: `Opportunity Closed Won Handoff`
3.  Enter a **Flow API Name**: `Opportunity_Closed_Won_Handoff` (this will auto-fill)
4.  Click **"Save"**.
5.  Click **"Activate"** in the top right corner to make your Flow active.

## Testing

Your setup is now complete. To test it:

1.  Go to any Opportunity record in Salesforce.
2.  Change the **Stage** of the Opportunity to **"Closed Won"**.
3.  Save the record.

This will trigger the Flow, which will send the outbound message to your running application. You should see log messages in your application's console indicating that it has received a webhook from Salesforce and has started processing the opportunity.
