import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from slack_sdk.errors import SlackApiError
from src.orchestrator import HandoffOrchestrator

# A helper to run async tests
def async_test(f):
    def wrapper(*args, **kwargs):
        asyncio.run(f(*args, **kwargs))
    return wrapper

class TestHandoffOrchestrator(unittest.TestCase):

    @patch('src.orchestrator.SalesforceConnector')
    @patch('src.orchestrator.JiraConnector')
    @patch('src.orchestrator.WatsonxConnector')
    @patch('src.orchestrator.SlackConnector')
    @async_test
    async def test_process_opportunity_success(self, MockSlackConnector, MockWatsonxConnector, MockJiraConnector, MockSalesforceConnector):
        # Arrange
        # Mock Salesforce
        mock_sf_connector = MockSalesforceConnector.return_value
        mock_sf_connector.get_closed_won_opportunity = AsyncMock(return_value={
            "Id": "006xx0000012345",
            "Name": "Test Corp Deal",
            "StageName": "Closed Won",
            "AttachedContentDocuments": {
                "records": [
                    {"ContentDocument": {"Title": "contract.txt", "FileType": "txt", "LatestPublishedVersionId": "v1"}},
                ]
            }
        })

        # Mock Watsonx Connector
        mock_watsonx_connector = MockWatsonxConnector.return_value
        mock_watsonx_connector.generate_handoff_assets = AsyncMock(return_value={
            "deliverables": ["Feature A", "Premium Support"],
            "timelines": ["within two weeks"],
            "discrepancies": [],
            "kickoff_agenda": "## Kickoff Agenda"
        })

        # Mock Slack
        mock_slack_connector = MockSlackConnector.return_value
        mock_slack_connector.send_approval_message = AsyncMock()
        
        # Mock Jira - Not used in this path
        mock_jira_connector = MockJiraConnector.return_value

        # Act
        orchestrator = HandoffOrchestrator()
        result = await orchestrator.process_opportunity("006xx0000012345")

        # Assert
        self.assertEqual(result["status"], "pending_approval")
        self.assertIn("Test Corp Deal", result["message"])

        mock_sf_connector.get_closed_won_opportunity.assert_called_once_with("006xx0000012345")
        mock_watsonx_connector.generate_handoff_assets.assert_called_once()
        mock_slack_connector.send_approval_message.assert_called_once()

    @patch('src.orchestrator.SalesforceConnector')
    @patch('src.orchestrator.JiraConnector')
    @patch('src.orchestrator.WatsonxConnector')
    @patch('src.orchestrator.SlackConnector')
    @async_test
    async def test_process_opportunity_slack_error(self, MockSlackConnector, MockWatsonxConnector, MockJiraConnector, MockSalesforceConnector):
        # Arrange
        # Mock Salesforce
        mock_sf_connector = MockSalesforceConnector.return_value
        mock_sf_connector.get_closed_won_opportunity = AsyncMock(return_value={
            "Id": "006xx0000012345",
            "Name": "Test Corp Deal",
            "StageName": "Closed Won",
            "AttachedContentDocuments": {
                "records": [
                    {"ContentDocument": {"Title": "contract.txt", "FileType": "txt", "LatestPublishedVersionId": "v1"}},
                ]
            }
        })

        # Mock Watsonx Connector
        mock_watsonx_connector = MockWatsonxConnector.return_value
        mock_watsonx_connector.generate_handoff_assets = AsyncMock(return_value={
            "deliverables": ["Feature A"],
            "timelines": [],
            "discrepancies": [],
            "kickoff_agenda": "## Agenda"
        })

        # Mock Slack to raise a "not_in_channel" error
        mock_slack_connector = MockSlackConnector.return_value
        mock_response_data = {"ok": False, "error": "not_in_channel"}
        mock_response = MagicMock()
        mock_response.__getitem__.side_effect = mock_response_data.__getitem__
        mock_response.status_code = 200
        mock_response.data = mock_response_data
        slack_api_error = SlackApiError("The request to the Slack API failed.", mock_response)
        mock_slack_connector.send_approval_message = AsyncMock(side_effect=slack_api_error)

        # Mock Jira
        mock_jira_connector = MockJiraConnector.return_value

        # Act & Assert
        orchestrator = HandoffOrchestrator()
        with self.assertRaises(SlackApiError) as context:
            await orchestrator.process_opportunity("006xx0000012345")
        
        self.assertEqual(context.exception.response["error"], "not_in_channel")

if __name__ == '__main__':
    unittest.main()
