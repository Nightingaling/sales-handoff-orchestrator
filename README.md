# Sales Handoff Orchestrator
<img width="2800" height="799" alt="Background Image" src="https://github.com/user-attachments/assets/fe3bd603-407f-4c3b-bdd6-b622b691929a" />

## Problem Statement

The transition between a closed enterprise sales deal and customer onboarding is historically messy. Sales drops a signed contract and some messy Salesforce notes into a Slack channel, and the Customer Success/Implementation teams have to manually decipher the promises made, set up project boards, and draft kickoff emails. This manual process is time-consuming, error-prone, and leads to a poor customer experience.

## Solution Description

This project implements an AI-powered orchestrator that automates the sales-to-customer-success handoff process. When a deal is marked "Closed Won" in Salesforce, the orchestrator automatically:

1.  **Ingests and analyzes all relevant documents:** It retrieves the final contract, sales transcripts, and CRM notes attached to the Salesforce opportunity.
2.  **Extracts key information:** Using an AI model, it extracts the exact deliverables, timelines, and customer commitments from the documents.
3.  **Flags discrepancies:** It compares the promised deliverables against the company's official product documentation to identify any features or timelines that were promised but are not standard. This allows for proactive management of customer expectations.
4.  **Automates project setup:** It provisions a tailored Jira project board with all the necessary implementation tasks, creating an epic and sub-tasks based on the extracted deliverables.
5.  **Drafts communication:** It generates a personalized client kickoff agenda for the Customer Success Manager to review and send, ensuring a smooth and professional start to the customer relationship.
6.  **Keeps humans in the loop:** The entire process is managed through Slack, with a final approval step before any external actions (like creating Jira projects) are taken. This ensures that the Customer Success team has full visibility and control.

## AI Approach and Architecture

The core of the solution is an AI-powered orchestration pipeline built with Python.

### 1. **Orchestration Layer (`orchestrator.py`)**

-   This is the central nervous system of the application.
-   It's triggered by a webhook when a Salesforce opportunity is "Closed Won."
-   It coordinates the flow of data between Salesforce, the document parser, the AI model, Jira, and Slack.

### 2. **Document Parsing (`document_parser.py`)**

-   Before the AI can do its work, all unstructured data must be converted to plain text.
-   The `DocumentParser` class handles multiple file formats, including PDF (`pdfplumber`), DOCX (`python-docx`), and TXT.
-   It reliably extracts text from contracts, statements of work, and meeting notes.

### 3. **AI Core (`watsonx_connector.py`)**

-   This component is responsible for the "intelligent" part of the workflow.
-   It uses the **IBM Watsonx API** with the `meta-llama/llama-3-3-70b-instruct` model.
-   It constructs a detailed, multi-part prompt that instructs the Large Language Model (LLM) to act as a sales handoff assistant. The prompt includes:
    -   The full text of the `product_documentation.md` to serve as the "ground truth" for what the company can deliver.
    -   The combined text from all sales documents.
-   The LLM is asked to return a structured JSON object containing:
    -   `deliverables`: A list of all promised items.
    -   `timelines`: Key dates and deadlines.
    -   `discrepancies`: A list of any promises that deviate from the official product documentation, including a severity score.
    -   `kickoff_agenda`: A pre-formatted, client-ready agenda for the first meeting.

### 4. **System Connectors (`salesforce_connector.py`, `jira_connector.py`, `slack_connector.py`)**

-   These modules handle the API integrations with the various external systems.
-   **Salesforce:** Fetches opportunity data and attached documents.
-   **Jira:** Creates the onboarding epic and sub-tasks.
-   **Slack:** Sends messages for approval, notifications of discrepancies, and confirmations.

## Selected Challenge Theme

**Wildcard Challenge - Build Intelligent Systems for the Future of Work.**

This solution directly addresses this theme by creating an intelligent system that automates a critical, yet often-overlooked, business process. It doesn't just automate tasks; it adds a layer of intelligence by analyzing unstructured data, identifying risks (discrepancies), and streamlining collaboration between different teams. It represents the future of work where AI assistants handle the tedious, administrative work, allowing humans to focus on high-value activities like building customer relationships.

## How IBM Bob was used

It was used by the developer to navigate the codebase, diagnose complex errors, apply automated fixes, and build new features. Here is a detailed breakdown of how it was utilized:

1. Root Cause Analysis & Debugging:    
The user initially tasked IBM Bob with investigating a "Failed to parse LLM response" error occurring in a Slack bot application. Bob autonomously explored the codebase (specifically `watsonx_connector.py`) and successfully diagnosed four distinct bugs:

    * **Bug 1:** Identified that the LLM's `max_new_tokens` limit (1500) was too low, causing truncated JSON responses.
    * **Bug 2:** Found a discrepancy in the JSON schema where the prompt asked for `severity` as a score but described it as a string, sometimes causing inconsistent output that was harder to parse.
    * **Bug 3:** Spotted a subtle flaw in the JSON extraction `else` clause that compounded the truncation issue.
    * **Bug 4:** Noted the absence of a `DEBUG` log for the raw LLM response on the "happy path," making diagnosis difficult.

2. Autonomous Code Patching ("Agent Mode"):    
Instead of just suggesting fixes, IBM Bob was used to actively write and verify the corrections:

    * It proposed specific changes, such as bumping the token limit to 2048 and rewriting the prompt instructions to enforce integer severity.
    * When the user clicked "Apply these fixes to the code," Bob switched to **agent mode**. 
    * It automatically applied the diffs to `src/watsonx_connector.py`. 
    * It then verified the final state by reading the patched file and ran a search to ensure no stale descriptions were left behind.

3. Feature Implementation & Adaptation:    
Beyond fixing bugs, IBM Bob was used to implement net-new requirements based on a provided specification:

    * **Creating Methods:** It drafted a new `send_slack_approval_message(deal_data)` method for the `SlackConnector` class, correctly mapping dictionary keys to a Slack Block Kit UI layout.
    * **Dynamic Problem Solving:** During the endpoint implementation, Bob's initial `search_and_replace` diff tool failed due to hidden characters in the file. It intelligently adapted to this failure and decided to write the `src/main.py` file directly to bypass the error.
