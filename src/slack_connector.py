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
            severity = item.get("severity", 1) # Default to 1 if not present
            try:
                # Severity can be a string from the LLM, so cast to int
                severity = int(severity)
            except (ValueError, TypeError):
                severity = 1

            # Color-coding based on severity
            if severity == 3:
                color = "#FF0000"  # Red for Major issue
            elif severity == 2:
                color = "#FFA500"  # Orange for Moderate issue
            else:
                color = "#FFFF00"  # Yellow for Minor issue

            severity_text = {1: "Minor", 2: "Moderate", 3: "Major"}.get(severity, "Unknown")
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""⚠️ *Discrepancy Found:*
>*Item:* {item['item']}
>*Reason:* {item['reason']}
>*Severity:* {severity_text} ({severity})"""
                },
                "accessory": {
                    "type": "image",
                    "image_url": f"https://placehold.co/15x15/{color.lstrip('#')}/{color.lstrip('#')}.png",
                    "alt_text": f"Color code {color}"
                }
            })
        return blocks

    async def send_tech_review_notification(self, opportunity_name: str, discrepancies: list):
        """
        Sends a message to the tech review channel for high-severity discrepancies.
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔬 Technical Review Required: {opportunity_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"The sales handoff for *{opportunity_name}* includes high-severity discrepancies that require technical review. Please assess the feasibility and impact of the following items."
                }
            }
        ]
        
        discrepancy_blocks = self._format_discrepancies(discrepancies)
        blocks.extend(discrepancy_blocks)
        
        try:
            await self.client.chat_postMessage(
                channel=config.SLACK_TECH_REVIEW_CHANNEL_ID,
                blocks=blocks,
                text=f"Technical Review Required for {opportunity_name}"
            )
            logger.info(f"Successfully sent technical review notification for opportunity: {opportunity_name}")
        except SlackApiError as e:
            logger.error(f"Failed to send technical review notification due to an API error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending a technical review notification: {e}", exc_info=True)


    async def send_rejection_notification(self, opportunity_name: str, discrepancies: list, rejected_by: str):
        """
        Sends a message to the channel notifying the sales rep of the rejection.
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ Handoff Rejected: {opportunity_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"The sales handoff for *{opportunity_name}* was rejected by *{rejected_by}*. The following discrepancies must be addressed before the project can proceed."
                }
            }
        ]
        
        discrepancy_blocks = self._format_discrepancies(discrepancies)
        blocks.extend(discrepancy_blocks)
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Please review the feedback, update the sales documents in Salesforce, and re-initiate the handoff process once the issues are resolved."
            }
        })

        try:
            # For now, this notifies the main channel. A future improvement would be to route this to the specific sales rep.
            await self.client.chat_postMessage(
                channel=self.channel_id,
                blocks=blocks,
                text=f"Handoff Rejected for {opportunity_name}"
            )
            logger.info(f"Successfully sent rejection notification for opportunity: {opportunity_name}")
        except SlackApiError as e:
            logger.error(f"Failed to send rejection notification due to an API error: {e}", exc_info=True)
            # Depending on the desired behavior, you might want to re-raise here
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending a rejection notification: {e}", exc_info=True)

    async def send_rejection_confirmation(self, opportunity_name: str, user_id: str):
        """
        Sends an ephemeral message to the user who rejected the handoff.
        """
        try:
            await self.client.chat_postEphemeral(
                channel=self.channel_id,
                user=user_id,
                text=f"❌ You have rejected the handoff for *{opportunity_name}*. The sales representative has been notified to review the discrepancies."
            )
            logger.info(f"Sent rejection confirmation to user {user_id} for opportunity {opportunity_name}")
        except SlackApiError as e:
            logger.error(f"Failed to send rejection confirmation due to an API error: {e}", exc_info=True)
            # This is a non-critical message, so we don't re-raise
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending a rejection confirmation: {e}", exc_info=True)
            # This is a non-critical message, so we don't re-raise

    async def send_slack_approval_message(self, deal_data: dict):
        """
        Sends an interactive Slack approval message built from the exact Block Kit
        structure required by the sales-handoff spec.

        Expected keys in ``deal_data``:
            - account_name     (str)  e.g. "Acme Corp"
            - amount           (str)  e.g. "$150,000"
            - ae_name          (str)  e.g. "Sarah Jenkins"
            - opportunity_id   (str)  e.g. "0068c00000abc123"
            - discrepancy_text (str)  pre-formatted mrkdwn alert block body
            - kickoff_agenda   (str)  plain-text agenda body
        """
        account_name     = deal_data.get("account_name", "Unknown Account")
        amount           = deal_data.get("amount", "N/A")
        ae_name          = deal_data.get("ae_name", "N/A")
        opportunity_id   = deal_data.get("opportunity_id", "N/A")
        discrepancy_text = deal_data.get("discrepancy_text", "No discrepancies detected.")
        kickoff_agenda   = deal_data.get("kickoff_agenda", "No agenda generated.")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 New Deal Handoff: {account_name}",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Value:* {amount}  |  "
                            f"*AE:* {ae_name}  |  "
                            f"*Opportunity ID:* {opportunity_id}"
                        )
                    }
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *AI Discrepancy Alerts*\n\n{discrepancy_text}"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✉️ *Drafted Kickoff Agenda*\n{kickoff_agenda}"
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve & Provision Jira",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": json.dumps({"opportunity_id": opportunity_id}),
                        "action_id": "approve_provision"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Flag for AE Review",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": json.dumps({"opportunity_id": opportunity_id}),
                        "action_id": "reject_handoff"
                    }
                ]
            }
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                blocks=blocks,
                text=f"🚨 New Deal Handoff for {account_name} requires approval."
            )
            logger.info(
                f"send_slack_approval_message: sent approval message for "
                f"opportunity {opportunity_id} to channel {self.channel_id}"
            )
        except SlackApiError as e:
            logger.error(
                f"send_slack_approval_message: Slack API error for "
                f"opportunity {opportunity_id}: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"send_slack_approval_message: unexpected error for "
                f"opportunity {opportunity_id}: {e}",
                exc_info=True
            )
            raise


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
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Reject",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": json.dumps({"opportunity_id": opportunity_id}),
                    "action_id": "reject_handoff"
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

