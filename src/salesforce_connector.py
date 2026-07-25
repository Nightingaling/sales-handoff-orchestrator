import asyncio
from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceAuthenticationFailed
from . import config
import logging

logger = logging.getLogger(__name__)

class SalesforceConnector:
    """Handles connection and data retrieval from Salesforce."""

    def __init__(self):
        logger.info("SalesforceConnector.__init__: Initializing...")
        self._sf_client = None
        logger.info("SalesforceConnector.__init__: Initialization complete.")

    async def _get_client(self):
        if self._sf_client:
            return self._sf_client

        def _connect():
            if all([config.SALESFORCE_USERNAME, config.SALESFORCE_PASSWORD, config.SALESFORCE_SECURITY_TOKEN, config.SALESFORCE_INSTANCE_URL]):
                try:
                    # WARNING: Disabling SSL verification is a security risk.
                    # This is done here to accommodate development environments that
                    # may use self-signed certificates.
                    # Do NOT use verify=False in a production environment.
                    return Salesforce(
                        username=config.SALESFORCE_USERNAME,
                        password=config.SALESFORCE_PASSWORD,
                        security_token=config.SALESFORCE_SECURITY_TOKEN,
                        instance_url=config.SALESFORCE_INSTANCE_URL
                    )
                except SalesforceAuthenticationFailed as e:
                    logger.error(f"Salesforce authentication failed. Please check your credentials in the .env file. Details: {e}", exc_info=True)
                    return None
                except Exception as e:
                    logger.error(f"Failed to connect to Salesforce: {e}", exc_info=True)
                    return None
            return None

        self._sf_client = await asyncio.to_thread(_connect)
        return self._sf_client

    async def get_closed_won_opportunity(self, opportunity_id: str) -> dict:
        """
        Retrieves details for a 'Closed Won' opportunity.

        In a real application, you would query for opportunities that have
        recently been updated to 'Closed Won'. For this example, we'll
        just fetch a specific opportunity by ID and assume it's closed.
        """
        sf = await self._get_client()
        if not sf:
            logger.warning(
                "Salesforce connection not configured. "
                "Please set SALESFORCE_USERNAME, SALESFORCE_PASSWORD, "
                "and SALESFORCE_SECURITY_TOKEN in your .env file."
            )
            # Return a mock object for demonstration purposes
            return {
                "Id": opportunity_id,
                "Name": "Demo Opportunity",
                "AccountId": "001xx000003DGb2AAG",
                "Amount": 50000,
                "StageName": "Closed Won",
                "Owner": {"Name": "Demo User"},
                # You would also fetch related documents/attachments here
                "AttachedContentDocuments": {
                    "records": [
                        {"ContentDocument": {"Title": "Final Contract", "LatestPublishedVersionId": "069xx000001D4xZ"}},
                        {"ContentDocument": {"Title": "Sales Notes", "LatestPublishedVersionId": "069xx000001D4xa"}},
                    ]
                }
            }

        def _fetch():
            try:
                # SOQL to get Opportunity and related ContentDocument links
                soql_opp = f"""
                SELECT Name, Account.Name, StageName, Amount, Owner.Name,
                    (SELECT ContentDocument.Id, ContentDocument.Title, ContentDocument.LatestPublishedVersionId
                     FROM AttachedContentDocuments)
                FROM Opportunity
                WHERE Id = '{opportunity_id}' AND StageName = 'Closed Won'
                """
                opportunity = sf.query(soql_opp)

                if opportunity["totalSize"] == 1:
                    return opportunity["records"][0]
                else:
                    return None
            except Exception as e:
                print(f"Error fetching opportunity from Salesforce: {e}")
                return None

        return await asyncio.to_thread(_fetch)


    async def get_document(self, content_version_id: str) -> bytes:
        """
        Retrieves a document from Salesforce.
        """
        sf = await self._get_client()
        if not sf:
            logger.warning(
                "Salesforce connection not configured. "
                "Please set SALESFORCE_USERNAME, SALESFORCE_PASSWORD, "
                "and SALESFORCE_SECURITY_TOKEN in your .env file."
            )
            return None

        try:
            def _get_doc():
                url = f"{sf.base_url}sobjects/ContentVersion/{content_version_id}/VersionData"
                response = sf.session.get(url, headers=sf.headers)
                response.raise_for_status()
                return response.content
            return await asyncio.to_thread(_get_doc)
        except Exception as e:
            print(f"Error fetching document from Salesforce: {e}")
            return None

    async def post_chatter_rejection(self, opportunity_id: str, ae_name: str, reason: str):
        """
        Posts a rejection message to Salesforce Chatter for a given opportunity.
        """
        sf = await self._get_client()
        if not sf:
            logger.warning("Salesforce connection not configured. Cannot post to Chatter.")
            return

        chatter_message = f"@[{ae_name}] Sales handoff rejected by CS. Reason: {reason}. Please update the Salesforce records and resubmit."
        
        def _post_chatter():
            try:
                sf.FeedItem.create({
                    'ParentId': opportunity_id, # This is crucial. It attaches the post to the Opportunity.
                    'Body': chatter_message,
                    'IsRichText': False
                })
                logger.info(f"Successfully posted to Chatter for Opp: {opportunity_id}")
            except Exception as e:
                logger.error(f"CRITICAL ERROR posting to Salesforce Chatter: {e}", exc_info=True)
                raise # Re-raise to ensure calling function is aware of the failure
        
        await asyncio.to_thread(_post_chatter)

    async def update_opportunity_stage_for_review(self, opportunity_id: str):
        """
        Updates the opportunity stage to 'Needs Review' and locks commission.
        """
        sf = await self._get_client()
        if not sf:
            logger.warning("Salesforce connection not configured. Cannot update opportunity.")
            return

        def _update_stage():
            try:
                # These field names are assumptions.
                # 'Needs Review' is a standard StageName.
                # 'Commission_Lock__c' is a custom field that needs to be created in Salesforce.
                sf.Opportunity.update(opportunity_id, {
                    'StageName': 'Needs Review',
                    # 'Commission_Lock__c' is a custom field that needs to be created in Salesforce.
                    # Ensure this field exists in your Salesforce instance with this exact API Name.
                    'Commission_Lock__c': True 
                })
                logger.info(f"Successfully updated Opportunity {opportunity_id} to 'Needs Review' and set 'Commission_Lock__c' to True.")
            except Exception as e:
                logger.error(f"CRITICAL ERROR updating opportunity stage for {opportunity_id}: {e}", exc_info=True)
                raise # Re-raise to ensure calling function is aware of the failure
        
        await asyncio.to_thread(_update_stage)
