import os
from dotenv import load_dotenv

load_dotenv()

# Salesforce Configuration
SALESFORCE_USERNAME = os.getenv("SALESFORCE_USERNAME")
SALESFORCE_PASSWORD = os.getenv("SALESFORCE_PASSWORD")
SALESFORCE_SECURITY_TOKEN = os.getenv("SALESFORCE_SECURITY_TOKEN")
SALESFORCE_INSTANCE_URL = os.getenv("SALESFORCE_INSTANCE_URL", "https://test.salesforce.com")

# Jira Configuration
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# IBM Watsonx Configuration
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID")
WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

# Slack Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# Product Capabilities (as a simple list for now, to be replaced by dynamic documentation)
# In a real application, this might come from a database or a dedicated service.
PRODUCT_CAPABILITIES = []
