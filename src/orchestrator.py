import asyncio
import aiofiles
import shutil
import json
from . import config
from .document_parser import DocumentParser
from .salesforce_connector import SalesforceConnector
from .jira_connector import JiraConnector
from .watsonx_connector import WatsonxConnector
from .slack_connector import SlackConnector
import os
import logging

logger = logging.getLogger(__name__)

TEMP_STATE_DIR = "temp_state"

class HandoffOrchestrator:
    """
    Orchestrates the entire sales handoff process, including a Slack approval step.
    """

    def __init__(self):
        logger.info("Orchestrator.__init__: Initializing...")
        self.document_parser = DocumentParser()
        self.salesforce_connector = SalesforceConnector()
        self.jira_connector = JiraConnector()
        self.vllm_connector = WatsonxConnector()
        self.slack_connector = SlackConnector()
        
        os.makedirs(TEMP_STATE_DIR, exist_ok=True)
        
        logger.info("Orchestrator.__init__: Initialization complete.")

    async def process_opportunity(self, opportunity_id: str) -> dict:
        """
        Processes an opportunity, generates handoff assets, and sends them to Slack for approval.
        """
        logger.info(f"process_opportunity started for opportunity_id: {opportunity_id}")
        try:
            # 1. Get Opportunity Details
            opportunity = await self.salesforce_connector.get_closed_won_opportunity(opportunity_id)
            if not opportunity or opportunity.get("StageName") != "Closed Won":
                logger.warning("Opportunity not found or not 'Closed Won'.")
                return {"status": "error", "message": "Opportunity not found or not 'Closed Won'."}
            
            # 2. Parse Documents
            all_text = await self._parse_opportunity_documents(opportunity)

            # 3. Load Product Docs (on-the-fly)
            try:
                dir_path = os.path.dirname(os.path.realpath(__file__))
                doc_path = os.path.join(dir_path, 'product_documentation.md')
                async with aiofiles.open(doc_path, 'r', encoding='utf-8') as f:
                    product_documentation = await f.read()
            except FileNotFoundError:
                logger.error("product_documentation.md not found.")
                product_documentation = "Product documentation not available."
            except Exception as e:
                logger.error(f"Error loading product documentation: {e}")
                product_documentation = "Error loading product documentation."
            
            # 4. Generate Handoff Assets via LLM
            logger.info("Calling Watsonx to generate handoff assets...")
            handoff_assets = await self.vllm_connector.generate_handoff_assets(all_text, product_documentation)
            logger.info("Watsonx processing complete.")

            # 5. Save State for Slack Approval
            state_to_save = {
                "opportunity": opportunity,
                "handoff_assets": handoff_assets
            }
            state_file_path = os.path.join(TEMP_STATE_DIR, f"{opportunity_id}.json")
            async with aiofiles.open(state_file_path, "w") as f:
                await f.write(json.dumps(state_to_save, indent=2))
            logger.info(f"Intermediate state saved to {state_file_path}")

            # 5. Send for Approval to Slack
            await self.slack_connector.send_approval_message(
                opportunity_name=opportunity["Name"],
                opportunity_id=opportunity_id,
                handoff_assets=handoff_assets
            )

            return {
                "status": "pending_approval",
                "message": f"Handoff analysis for {opportunity['Name']} is complete. Awaiting approval in Slack."
            }
        except Exception as e:
            logger.error(f"An error occurred in process_opportunity: {e}", exc_info=True)
            raise

    async def provision_jira_project(self, opportunity_id: str):
        """
        Provisions the Jira project after Slack approval.
        """
        logger.info(f"provision_jira_project started for opportunity_id: {opportunity_id}")
        state_file_path = os.path.join(TEMP_STATE_DIR, f"{opportunity_id}.json")
        
        try:
            # 1. Load State
            async with aiofiles.open(state_file_path, "r") as f:
                state = json.loads(await f.read())
            
            opportunity = state["opportunity"]
            handoff_assets = state["handoff_assets"]
            all_deliverables = handoff_assets.get("deliverables", [])
            project_name = f"Onboarding: {opportunity['Name']}"
            project_key = "".join(filter(str.isalnum, opportunity['Name']))[:5].upper()

            # 2. Create Jira Epic and Sub-tasks
            logger.info(f"Creating Jira Epic and tasks for {project_key}...")
            epic_key = await self.jira_connector.create_onboarding_epic_and_tasks(
                project_key=project_key,
                project_name=project_name,
                opportunity_name=opportunity['Name'],
                deliverables=all_deliverables
            )
            
            if not epic_key:
                logger.error(f"Failed to create Jira epic for {project_key}")
                # Optionally, send a failure notification to Slack
                return

            logger.info(f"Successfully provisioned Jira project. Epic: {epic_key}")

            # 3. Clean up state file
            os.remove(state_file_path)
            logger.info(f"Cleaned up state file: {state_file_path}")

        except FileNotFoundError:
            logger.error(f"State file not found for opportunity_id: {opportunity_id}. The process may have already completed or failed.")
            raise
        except Exception as e:
            logger.error(f"An error occurred in provision_jira_project: {e}", exc_info=True)
            # Optionally, send a failure notification to Slack
            raise

    async def _parse_opportunity_documents(self, opportunity: dict) -> str:
        """Helper to ingest and parse all documents for an opportunity."""
        logger.info("Ingesting and parsing documents...")
        all_text = ""
        temp_dir = "temp_docs"
        os.makedirs(temp_dir, exist_ok=True)

        if "AttachedContentDocuments" in opportunity and opportunity["AttachedContentDocuments"] and opportunity["AttachedContentDocuments"]["records"]:
            parse_tasks = []
            for doc_record in opportunity["AttachedContentDocuments"]["records"]:
                doc_info = doc_record["ContentDocument"]
                title = doc_info["Title"]
                file_type = doc_info.get("FileType", "").lower()
                version_id = doc_info["LatestPublishedVersionId"]

                file_extension = f".{file_type}" if file_type in ['pdf', 'docx', 'txt'] else '.txt'
                file_path = os.path.join(temp_dir, f"{version_id}_{title}{file_extension}")

                mock_content = f"Document: {title}\n"
                if "contract" in title.lower():
                    mock_content += "Deliverables: AI-Powered Insights, SSO Integration, and on-premise deployment. Timeline: Project start within one week."
                elif "notes" in title.lower():
                    mock_content += "No special notes."
                
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(mock_content)

                parse_tasks.append(self.document_parser.parse_document(file_path))

            parsed_results = await asyncio.gather(*parse_tasks)
            all_text = "\n\n".join(filter(None, parsed_results))
        
        shutil.rmtree(temp_dir)
        
        if not all_text.strip():
            logger.warning("No text could be extracted from the documents.")
            return "No documents found or text could not be extracted."
            
        logger.info("Document parsing complete.")
        return all_text
