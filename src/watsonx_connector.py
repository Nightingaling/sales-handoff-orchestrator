import os
import requests
import json
import re
from . import config
import logging
import asyncio

logger = logging.getLogger(__name__)

class WatsonxConnector:
    """
    Handles communication with the IBM Watsonx API using direct REST API calls.
    """

    def __init__(self):
        logger.info("WatsonxConnector.__init__: Initializing...")
        # No client object to store for direct API calls, but we keep _client for structural consistency
        self._client = self
        self._semaphore = asyncio.Semaphore(1)
        self._session = requests.Session()
        logger.info("WatsonxConnector.__init__: Initialization complete.")

    def _get_client(self):
        """
        Returns the instance itself, as there's no external client object to manage.
        """
        return self._client

    async def _get_iam_token(self) -> str:
        """
        Exchanges the IBM Cloud API Key for a temporary IAM Bearer token.
        """
        token_url = "https://iam.cloud.ibm.com/identity/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        data = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": config.WATSONX_API_KEY
        }
        
        try:
            logger.info("Authenticating with IBM Cloud...")
            response = await asyncio.to_thread(self._session.post, token_url, headers=headers, data=data)
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Error obtaining IAM token: {e}")
            if e.response is not None:
                logger.error(f"Error details: {e.response.text}")
            raise # Re-raise to be caught by generate_handoff_assets

    async def generate_handoff_assets(self, document_text: str, product_documentation: str) -> dict:
        """
        Uses Watsonx to act as an orchestrator:
        1. Extracts deliverables and timelines from sales documents.
        2. Compares them against product documentation to find discrepancies.
        3. Drafts a kickoff agenda.
        """
        async with self._semaphore:
            prompt = f"""
            You are an AI assistant for a sales handoff process. Your task is to analyze sales documents, compare them to the official product documentation, and generate a set of assets for the post-sales team.

            Here is the official product documentation for what is possible:
            ---
            <product_documentation>
            {product_documentation}
            </product_documentation>
            ---

            Here is the combined text from all sales documents (contracts, transcripts, etc.):
            ---
            <sales_documents>
            {document_text}
            </sales_documents>
            ---

            Based on the provided documents, perform the following tasks:

            1.  **Extract Key Information**: Identify the specific deliverables and timelines promised to the client.
            
            2.  **Analyze Discrepancies**: Cross-reference the extracted deliverables against the product documentation. Identify any items that are not supported, require a higher tier, or are an unclear. Each discrepancy should have a 'reason'.

            3.  **Draft Kickoff Agenda**: Create a client-facing kickoff agenda based on the confirmed deliverables and timelines.

            Please provide the output as a single JSON object with the following structure:
            {{
                "deliverables": [
                    "List of strings representing each deliverable promised."
                ],
                "timelines": [
                    "List of strings representing key dates or timeframes."
                ],
                "discrepancies": [
                    {{
                        "item": "The deliverable or promise that has an issue.",
                        "reason": "A brief explanation of why it's a discrepancy (e.g., 'Feature not available in Standard Tier', 'Custom feature not in documentation', 'Timeline is unrealistic')."
                    }}
                ],
                "kickoff_agenda": "A markdown-formatted string for the client kickoff meeting agenda."
            }}

            Return only the JSON object.
            """

            generated_text = ""
            try:
                access_token = await self._get_iam_token()
                
                # watsonx.ai Generation API endpoint (must include the version date parameter)
                generation_url = f"{config.WATSONX_URL}/ml/v1/text/generation?version=2023-05-29"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                # Configure the model and parameters
                # Note: The model_id specified here MUST be available in your IBM Cloud region.
                # If you encounter a "model_not_found" error, please check the IBM Cloud Catalog
                # to find a suitable model for your region and update the 'model_id' accordingly.
                payload = {
                    "model_id": "meta-llama/llama-3-3-70b-instruct",
                    "project_id": config.WATSONX_PROJECT_ID,
                    "input": prompt,
                    "parameters": {
                        "decoding_method": "greedy",
                        "max_new_tokens": 1500, # Max tokens for the LLM response
                        "min_new_tokens": 1,
                        "repetition_penalty": 1.1
                    }
                }
                
                logger.info("Sending prompt to watsonx API...")
                response = await asyncio.to_thread(self._session.post, generation_url, headers=headers, json=payload)
                response.raise_for_status() # Raise an exception for bad status codes
                
                # Extract the generated text from the JSON response
                result = response.json()
                generated_text = result["results"][0]["generated_text"]
                
                # Clean the response to get only the JSON part.
                # The model often returns explanatory text and multiple JSON blocks.
                # We'll find all JSON blocks wrapped in ```json ... ``` and use the last one.
                json_part = ""
                json_matches = re.findall(r"```json\s*([\s\S]+?)\s*```", generated_text)
                
                if json_matches:
                    # Use the content of the last JSON block found
                    json_part = json_matches[-1]
                else:
                    # If no markdown block is found, it's likely the response contains raw JSON
                    # possibly with leading/trailing text. The 'Extra data' error happens when
                    # there's text *after* the JSON.
                    # A robust way to handle this is to find the last complete JSON object.
                    last_brace = generated_text.rfind('}')
                    if last_brace == -1:
                        # If there's no '}', we can't find a JSON object.
                        raise json.JSONDecodeError("No JSON object found in response", generated_text, 0)

                    # Scan backwards from the last '}' to find its matching '{'.
                    # This correctly isolates the last JSON object from any surrounding text.
                    balance = 0
                    for i in range(last_brace, -1, -1):
                        if generated_text[i] == '}':
                            balance += 1
                        elif generated_text[i] == '{':
                            balance -= 1
                            if balance == 0:
                                json_part = generated_text[i:last_brace + 1]
                                break
                    else:
                        # This 'else' belongs to the 'for' loop, executed if 'break' is not hit.
                        raise json.JSONDecodeError("Could not find a complete JSON object.", generated_text, 0)
                
                if not json_part:
                    raise json.JSONDecodeError("No valid JSON found in response", generated_text, 0)

                # Now, try to parse the extracted JSON part, with a simple fix-up attempt.
                try:
                    # Strip whitespace which can cause parsing errors
                    return json.loads(json_part.strip())
                except json.JSONDecodeError as e:
                    logger.warning(f"Initial JSON parsing failed: {e}. Attempting to fix and re-parse.")
                    # Attempt to fix common errors like trailing commas before re-parsing.
                    fixed_json = re.sub(r",\s*([\}\]])", r"\1", json_part.strip())
                    return json.loads(fixed_json)

            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP Error communicating with watsonx API: {e}")
                if e.response is not None:
                    logger.error(f"Error details: {e.response.text}")
                return {
                    "deliverables": [],
                    "timelines": [],
                    "discrepancies": [{"item": "Processing Error", "reason": f"Failed to communicate with Watsonx API: {e}"}],
                    "kickoff_agenda": "Could not be generated due to API communication error."
                }
            except (json.JSONDecodeError, IndexError) as e:
                logger.error(f"Failed to parse JSON from Watsonx response: {e}", exc_info=True)
                logger.error(f"Raw response from Watsonx: {generated_text}")
                # Return a default error structure
                return {
                    "deliverables": [],
                    "timelines": [],
                    "discrepancies": [{"item": "Processing Error", "reason": "Failed to parse LLM response."}],
                    "kickoff_agenda": "Could not be generated due to a processing error."
                }
            except Exception as e:
                logger.error(f"An unexpected error occurred during handoff asset generation: {e}", exc_info=True)
                return {
                    "deliverables": [],
                    "timelines": [],
                    "discrepancies": [{"item": "Processing Error", "reason": "An unexpected error occurred."}],
                    "kickoff_agenda": "Could not be generated due to an unexpected error."
                }

