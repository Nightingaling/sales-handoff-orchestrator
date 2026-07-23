import json
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from . import config
import logging

logger = logging.getLogger(__name__)

class SlackConnector:
    """
    Handles communication with the Slack API.
    """

    def __init__(self):
        logger.info("SlackConnector.__init__: Initializing...")
        self.client = AsyncWebClient(token=config.SLACK_BOT_TOKEN)
        self.channel_id = config.SLACK_CHANNEL_ID
        logger.info("SlackConnector.__init__: Initialization complete.")

    def _format_discrepancies(self, discrepancies: list) -> list:
        """Formats discrepancy data into Slack blocks."""
        if not discrepancies:
            return []

        blocks = [{"type": "divider"}]
        
        for item in discrepancies:
            # Basic color-coding: Red for errors/unavailable, Orange for warnings/tier-mismatches
            if "not available" in item['reason'].lower() or "not in documentation" in item['reason'].lower():
                color = "#FF0000"  # Red
            elif "tier" in item['reason'].lower() or "unrealistic" in item['reason'].lower():
                color = "#FFA500"  # Orange
            else:
                color = "#FFFF00"  # Yellow
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""⚠️ *Discrepancy Found:*
>*Item:* {item['item']}
>*Reason:* {item['reason']}"""
                },
                "accessory": {
                    "type": "image",
                    "image_url": f"https://placehold.co/15x15/{color.lstrip('#')}/{color.lstrip('#')}.png",
                    "alt_text": f"Color code {color}"
                }
            })
        return blocks

    async def send_approval_message(self, opportunity_name: str, opportunity_id: str, handoff_assets: dict):
        """
        Sends a message to Slack for approval, including an interactive button.
        """
        kickoff_agenda = handoff_assets.get("kickoff_agenda") or "No agenda was generated."
        discrepancies = handoff_assets.get("discrepancies", [])
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚀 New Sales Handoff: {opportunity_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "An AI-powered analysis of the sales documents is complete. Please review the generated assets and approve to provision the project in Jira."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📝 Draft Kickoff Agenda"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": kickoff_agenda
                }
            }
        ]
        
        # Add discrepancy blocks
        discrepancy_blocks = self._format_discrepancies(discrepancies)
        blocks.extend(discrepancy_blocks)
        
        # Add Actions block with button
        blocks.append({
			"type": "divider"
		})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve & Provision Project",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": json.dumps({"opportunity_id": opportunity_id}),
                    "action_id": "approve_provision"
                }
            ]
        })

        try:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                blocks=blocks,
                text=f"Sales Handoff for {opportunity_name} requires approval."
            )
            logger.info(f"Successfully sent approval message to Slack for opportunity ID: {opportunity_id}")
        except SlackApiError as e:
            if e.response["error"] == "not_in_channel":
                logger.error(
                    f"Failed to send Slack message: The bot is not in the channel '{self.channel_id}'. "
                    f"Please invite the bot to this channel and try again."
                )
                raise ValueError(
                    f"The Slack bot is not in the specified channel '{self.channel_id}'. "
                    "Please invite the bot to this channel before proceeding."
                )
            else:
                logger.error(f"Failed to send Slack message due to an API error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending a Slack message: {e}", exc_info=True)
            raise

