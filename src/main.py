import json
import logging

import requests
import xmltodict

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import Response


from .orchestrator import HandoffOrchestrator

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zero-Friction B2B Handoff Orchestrator",
    description="An AI-powered orchestrator to automate the sales-to-customer-success handoff.",
    version="0.1.0",
)

@app.on_event("startup")
async def startup_event():
    """Initializes the HandoffOrchestrator instance at application startup."""
    logger.info("main.py: startup_event called")
    app.state.orchestrator = HandoffOrchestrator()
    logger.info("main.py: HandoffOrchestrator instantiated")

@app.post("/api/salesforce/webhook", tags=["Salesforce"])
async def salesforce_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handles Salesforce Outbound Message webhook for opportunity updates.
    """
    try:
        content_type = request.headers.get("Content-Type")
        if "text/xml" not in content_type:
            raise HTTPException(status_code=400, detail=f"Invalid content type: {content_type}. Must be 'text/xml'.")

        body = await request.body()
        data = xmltodict.parse(body)

        # Navigate through the SOAP envelope to get to the Opportunity details
        notification = data.get("soapenv:Envelope", {}).get("soapenv:Body", {}).get("notifications", {})
        sobject = notification.get("Notification", {}).get("sObject", {})
        
        # The namespace 'sf:' is defined in the WSDL, xmltodict will include it
        opportunity_id = sobject.get("sf:Id")

        if not opportunity_id:
            logger.error(f"Could not extract Opportunity ID from Salesforce webhook payload: {data}")
            raise HTTPException(status_code=400, detail="Could not extract Opportunity ID from payload.")

        logger.info(f"Received Salesforce webhook for Opportunity ID: {opportunity_id}")
        
        # Process the opportunity in the background
        background_tasks.add_task(app.state.orchestrator.process_opportunity, opportunity_id)

        # Salesforce requires a specific SOAP response to acknowledge receipt
        ack_response = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<notificationsResponse xmlns="http://soap.sforce.com/2005/09/outbound">
<Ack>true</Ack>
</notificationsResponse>
</soapenv:Body>
</soapenv:Envelope>
"""
        return Response(content=ack_response, media_type="text/xml")

    except Exception as e:
        logger.error(f"Error processing Salesforce webhook: {e}", exc_info=True)
        # Even on error, we need to try and send an ack=false to Salesforce if possible
        # For simplicity, we'll return a generic error here, but in production you might
        # want to craft a NACK response.
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/handoff/{opportunity_id}", tags=["Handoff"])
async def perform_handoff(opportunity_id: str):
    """
    Triggers the handoff analysis for a given Salesforce Opportunity ID and sends it for approval.
    """
    try:
        result = await app.state.orchestrator.process_opportunity(opportunity_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        return result
    except Exception as e:
        logger.error(f"Error during handoff for {opportunity_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/slack/interactive", tags=["Slack"])
async def slack_interactive_endpoint(request: Request, background_tasks: BackgroundTasks):
    """
    Handles interactive components from Slack, specifically the approval button.
    """
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")

    try:
        payload = json.loads(payload_str)

        # Handle Slack's URL verification challenge if needed
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}
            
        if payload.get("type") == "block_actions":
            action = payload["actions"][0]
            action_value = json.loads(action["value"])
            opportunity_id = action_value["opportunity_id"]
            user_name = payload["user"]["name"]
            user_id = payload["user"]["id"]
            response_url = payload["response_url"] # Extract response_url
            
            if action["action_id"] == "approve_provision":
                logger.info(f"Received 'approve_provision' action for opportunity ID: {opportunity_id} from user {user_name}")

                # Update the Slack message immediately to remove buttons
                updated_blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Handoff Approved by {user_name}.* The project is now being provisioned in Jira."
                        }
                    }
                ]
                
                # This replaces the original message so it cannot be clicked again
                requests.post(response_url, json={
                    "replace_original": "true", 
                    "blocks": updated_blocks
                })
                
                # Run the provisioning in the background
                background_tasks.add_task(app.state.orchestrator.provision_jira_project, opportunity_id)
                
                # Return a 200 OK to Slack immediately
                return {"status": "ok"}

            elif action["action_id"] == "reject_handoff":
                logger.info(f"Received 'reject_handoff' action for opportunity ID: {opportunity_id} from user {user_name}")

                # Update the Slack message immediately to remove buttons
                updated_blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🛑 *Handoff Rejected by {user_name}.* The AE has been notified in Salesforce."
                        }
                    }
                ]
                
                # This replaces the original message so it cannot be clicked again
                requests.post(response_url, json={
                    "replace_original": "true", 
                    "blocks": updated_blocks
                })

                # Trigger the Chatter post in the background
                background_tasks.add_task(app.state.orchestrator.handle_rejection, opportunity_id, user_name)

                # Return a 200 OK to Slack immediately
                return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing Slack interactive payload: {e}", exc_info=True)
        # It's important to still return a 200 to Slack to avoid retry storms
        return {"status": "error", "message": str(e)} # Return an error status to Slack, but still 200 HTTP status

    return {"status": "ok"}


@app.get("/", tags=["General"])
async def read_root():
    """Root endpoint with a welcome message."""
    return {"message": "Welcome to the Handoff Orchestrator. Use the /docs endpoint to see the API."}
