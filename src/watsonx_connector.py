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

Based on the provided documents, perform the following tasks and provide the output as a single JSON object:

1.  **Extract Key Information**: Identify the specific deliverables and timelines promised to the client.
            
2.  **Analyze Discrepancies**: Cross-reference the extracted deliverables against the product documentation. Identify any items that are not supported, require a higher tier, or are an unclear. Each discrepancy should have a 'reason'.

3.  **Draft Kickoff Agenda**: As an expert Sales-to-Customer-Success handoff assistant, draft a kickoff meeting agenda based ONLY on the provided CRM data and sales documents.

    CRITICAL INSTRUCTIONS FOR KICKOFF AGENDA:
    a. NO PLACEHOLDERS: Do not use generic filler like "To be discussed" or "TBD". You MUST extract the exact deliverables, quantities, and dates from the provided text.
    b. NO HALLUCINATIONS: If a specific date or deliverable is not in the text, do not invent one.
    c. SLACK FORMATTING ONLY: Do NOT use standard Markdown headers (like # or ##). Do NOT wrap your response in code blocks. 
       - Use standard text.
       - Use Slack's formatting for bolding headers: *bold text*
       - Use standard dashes (-) or bullets (•) for lists.

    Format the agenda EXACTLY like this structure:
    *Client Kickoff Meeting Agenda*
    *Objective:* [State the exact goal based on the documents]

    *1. Review of Deliverables*
    - [Specific deliverable 1 from document]
    - [Specific deliverable 2 from document]

    *2. Timeline & Key Dates*
    - [Specific date 1 from document]
    - [Specific date 2 from document]


Return only the JSON object. Example of the full JSON structure:
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
            "reason": "A brief explanation of why it's a discrepancy (e.g., 'Feature not available in Standard Tier', 'Custom feature not in documentation', 'Timeline is unrealistic').",
            "severity": 1
        }}
    ],
    "kickoff_agenda": "A string containing the Slack-formatted kickoff meeting agenda as described in the CRITICAL INSTRUCTIONS."
}}
"""

            generated_text = ""
            max_retries = 5
            backoff_factor = 1.5

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
                        "max_new_tokens": 2048, # Max tokens for the LLM response — raised from 1500 to prevent truncated JSON
                        "min_new_tokens": 1,
                        "repetition_penalty": 1.1
                    }
                }

                response = None
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Sending prompt to watsonx API (Attempt {attempt + 1}/{max_retries})...")
                        response = await asyncio.to_thread(self._session.post, generation_url, headers=headers, json=payload)
                        response.raise_for_status() # Raise an exception for bad status codes
                        # If successful, break the loop
                        logger.info("Successfully received response from watsonx API.")
                        break
                    except requests.exceptions.RequestException as e:
                        # Check for 429 status code for rate limiting
                        if e.response is not None and e.response.status_code == 429:
                            if attempt < max_retries - 1:
                                wait_time = backoff_factor * (2 ** attempt)
                                logger.warning(f"Watsonx API rate limit hit (429). Retrying in {wait_time:.2f} seconds...")
                                await asyncio.sleep(wait_time)
                            else:
                                logger.error(f"Watsonx API rate limit hit. Max retries ({max_retries}) reached.")
                                raise # Re-raise the final exception
                        else:
                            # For other HTTP errors (non-429), we re-raise immediately.
                            raise
                
                if response is None:
                    # This case should ideally not be reached if the loop always raises or breaks. It's a safeguard.
                    raise Exception("Failed to get a valid response from Watsonx API after all retries.")
                
                # Extract the generated text from the JSON response
                result = response.json()
                generated_text = result["results"][0]["generated_text"]
                logger.debug(f"Raw LLM response received (length={len(generated_text)}):\n{generated_text}")
                
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
                
                json_part = json_part.strip()
                if not json_part:
                    raise json.JSONDecodeError("Extracted JSON part is empty after stripping", generated_text, 0)

                # Now, try to parse the extracted JSON part, with a simple fix-up attempt.
                try:
                    return json.loads(json_part)
                except json.JSONDecodeError as e:
                    logger.warning(f"Initial JSON parsing failed: {e}. Attempting to fix and re-parse.")
                    # Attempt to fix common errors like trailing commas before re-parsing.
                    fixed_json = re.sub(r",\s*([\}\]])", r"\1", json_part)
                    return json.loads(fixed_json)

            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP Error communicating with watsonx API: {e}")
                if e.response is not None:
                    logger.error(f"Error details: {e.response.text}")
                raise
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

