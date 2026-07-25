import asyncio
import aiofiles
import shutil
import json
import requests
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

            # Abort if no text was found, to prevent useless LLM calls.
            if all_text == "No documents found or text could not be extracted.":
                logger.warning("Aborting handoff: No text could be extracted from documents.")
                return {
                    "status": "error",
                    "message": "Handoff aborted because no text could be extracted from the sales documents."
                }

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
            try:
                handoff_assets = await self.vllm_connector.generate_handoff_assets(all_text, product_documentation)
            except requests.exceptions.RequestException as e:
                logger.error(f"Watsonx API request failed: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to generate handoff assets due to a Watsonx API error: {e}"}
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
            deal_data = self._build_deal_data(opportunity, opportunity_id, handoff_assets)
            await self.slack_connector.send_slack_approval_message(deal_data)

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

    async def handle_rejection(self, opportunity_id: str, rejected_by_name: str):
        """
        Handles the rejection of a handoff, notifies the sales rep, and cleans up.
        """
        logger.info(f"handle_rejection started for opportunity_id: {opportunity_id}")
        state_file_path = os.path.join(TEMP_STATE_DIR, f"{opportunity_id}.json")

        try:
            # 1. Load State to get context for the notification
            async with aiofiles.open(state_file_path, "r") as f:
                state = json.loads(await f.read())
            
            opportunity = state["opportunity"]
            handoff_assets = state["handoff_assets"]
            discrepancies = handoff_assets.get("discrepancies", [])

            # 2. Notify Sales Team of Rejection
            await self.slack_connector.send_rejection_notification(
                opportunity_name=opportunity['Name'],
                discrepancies=discrepancies,
                rejected_by=rejected_by_name
            )

            # 3. Clean up state file to prevent provisioning
            os.remove(state_file_path)
            logger.info(f"Cleaned up state file after rejection: {state_file_path}")

        except FileNotFoundError:
            logger.warning(f"State file for opportunity_id: {opportunity_id} not found during rejection. It might have already been processed or deleted.")
            # No need to re-raise, as the end state (no file) is what we want.
        except Exception as e:
            logger.error(f"An error occurred in handle_rejection: {e}", exc_info=True)
            # Re-raise to indicate a failure in the rejection process itself
            raise

    def _build_deal_data(self, opportunity: dict, opportunity_id: str, handoff_assets: dict) -> dict:
        """
        Transforms the raw Salesforce opportunity and Watsonx handoff_assets into
        the flat ``deal_data`` dict expected by ``send_slack_approval_message``.
        """
        # Salesforce returns Amount as a float; format it as currency string.
        raw_amount = opportunity.get("Amount")
        if raw_amount is not None:
            try:
                amount = f"${float(raw_amount):,.0f}"
            except (ValueError, TypeError):
                amount = str(raw_amount)
        else:
            amount = "N/A"

        # AE name: try the real Salesforce Owner field first, fall back gracefully.
        ae_name = (
            (opportunity.get("Owner") or {}).get("Name")
            or opportunity.get("OwnerName")
            or "N/A"
        )

        # Convert the discrepancies list into a single mrkdwn-formatted string.
        discrepancy_lines = []
        for item in handoff_assets.get("discrepancies", []):
            severity = item.get("severity", 1)
            try:
                severity = int(severity)
            except (ValueError, TypeError):
                severity = 1

            if severity >= 3:
                icon = "🔴 *High Risk:*"
            elif severity == 2:
                icon = "🟡 *Medium Risk:*"
            else:
                icon = "🔵 *Low Risk:*"

            discrepancy_lines.append(
                f"{icon} {item.get('item', 'Unknown')} — {item.get('reason', '')}"
            )

        discrepancy_text = (
            "\n".join(discrepancy_lines)
            if discrepancy_lines
            else "No discrepancies detected."
        )

        # Strip markdown headings from the kickoff agenda so it renders cleanly
        # inside the Slack triple-fence code block (# headers look like plain text there).
        kickoff_agenda = handoff_assets.get("kickoff_agenda", "No agenda generated.")

        return {
            "account_name":     opportunity.get("Name", "Unknown Account"),
            "amount":           amount,
            "ae_name":          ae_name,
            "opportunity_id":   opportunity_id,
            "discrepancy_text": discrepancy_text,
            "kickoff_agenda":   kickoff_agenda,
        }

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

                base_name, current_ext = os.path.splitext(title)
                current_ext = current_ext.lower().strip('.')

                logger.info(f"Processing document '{title}'. FileType from Salesforce: '{file_type}', Ext from title: '{current_ext}'")
                
                # Heuristic to guess file type based on title if other methods fail
                guessed_ext = ''
                title_lower = title.lower()
                if 'note' in title_lower:
                    guessed_ext = '.txt'
                elif 'agreement' in title_lower or 'contract' in title_lower or 'sow' in title_lower:
                    guessed_ext = '.pdf'

                if current_ext in ['pdf', 'docx', 'txt']:
                    file_path = os.path.join(temp_dir, f"{version_id}_{title}")
                elif file_type in ['pdf', 'docx', 'txt']:
                    file_path = os.path.join(temp_dir, f"{version_id}_{title}.{file_type}")
                elif guessed_ext:
                    file_path = os.path.join(temp_dir, f"{version_id}_{title}{guessed_ext}")
                else:
                    logger.warning(f"Unsupported or unknown file type for document '{title}'. Could not guess extension. Skipping.")
                    continue

                # Get document content from Salesforce
                doc_content = await self.salesforce_connector.get_document(version_id)

                if doc_content:
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(doc_content)
                    
                    parse_tasks.append(self.document_parser.parse_document(file_path))
                else:
                    logger.warning(f"Could not retrieve document content for {title} (Version ID: {version_id})")

            if parse_tasks:
                parsed_results = await asyncio.gather(*parse_tasks)
                all_text = "\n\n".join(filter(None, parsed_results))
        
        shutil.rmtree(temp_dir)
        
        if not all_text.strip():
            logger.warning("No text could be extracted from the documents.")
            return "No documents found or text could not be extracted."
            
        logger.info("Document parsing complete.")
        return all_text
