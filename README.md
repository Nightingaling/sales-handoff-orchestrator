# Zero-Friction B2B Handoff Orchestrator

This project is an AI-powered orchestrator to streamline the handoff process between sales and customer success teams in a B2B context.

## The Problem

The transition of a new customer from a closed deal to the onboarding phase is often manual and inefficient. Sales teams typically provide notes, contracts, and other documents in a semi-structured way, leaving the customer success team to manually parse this information, create project plans, and initiate the client relationship. This can lead to delays, miscommunication, and a poor initial customer experience.

## The Solution

This orchestrator automates the entire handoff process. When a deal is marked as "Closed Won" in a CRM system (like Salesforce), the orchestrator:

1.  **Ingests Key Documents:** It automatically retrieves the final contract, sales transcripts, and CRM notes associated with the deal.
2.  **Extracts Critical Information:** Using AI, it parses these documents to identify the precise deliverables, timelines, and key stakeholders.
3.  **Identifies Discrepancies:** It cross-references the promised deliverables with a knowledge base of the company's actual product capabilities, flagging any potential conflicts or unrealistic promises.
4.  **Provisions Project Boards:** It connects to a project management tool (like Jira or Linear) and automatically creates a new project board for the customer, populated with the specific implementation tasks derived from the deliverables.
5.  **Drafts Kickoff Agendas:** It generates a personalized kickoff agenda for the customer success manager to review and send to the new client, ensuring a smooth and professional start to the relationship.

This solution is designed to be a "zero-friction" tool that operates in the background, bridging the gap between teams and eliminating a significant workflow bottleneck.

## Getting Started

1.  **Installation:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configuration:**
    - Create a `.env` file by copying the `.env.example` file: `cp .env.example .env`
    - Edit the `.env` file and fill in the necessary API keys and credentials for Salesforce, Jira, IBM Watsonx, and Slack.
3.  **Running the application:**
    ```bash
    python src/main.py
    ```
