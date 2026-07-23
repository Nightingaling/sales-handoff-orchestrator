import logging
import json
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
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
            if action["action_id"] == "approve_provision":
                action_value = json.loads(action["value"])
                opportunity_id = action_value["opportunity_id"]
                
                logger.info(f"Received 'approve_provision' action for opportunity ID: {opportunity_id}")
                
                # Run the provisioning in the background
                background_tasks.add_task(app.state.orchestrator.provision_jira_project, opportunity_id)
                
                # Let the user know the process has started
                response_text = f"✅ Approved! Provisioning for opportunity `{opportunity_id}` has started."
                return {"text": response_text, "response_type": "ephemeral", "replace_original": False}

    except Exception as e:
        logger.error(f"Error processing Slack interactive payload: {e}", exc_info=True)
        # It's important to still return a 200 to Slack to avoid retry storms
    
    return {"status": "ok"}


@app.get("/", tags=["General"])
async def read_root():
    """Root endpoint with a welcome message."""
    return {"message": "Welcome to the Handoff Orchestrator. Use the /docs endpoint to see the API."}
