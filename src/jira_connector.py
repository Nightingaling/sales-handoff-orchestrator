import asyncio
from jira import JIRA, JIRAError
from . import config
import logging

logger = logging.getLogger(__name__)

class JiraConnector:
    """
    Handles connection and actions with Jira.
    """

    def __init__(self):
        logger.info("JiraConnector.__init__: Initializing...")
        self._jira_client = None
        self._field_cache = {}  # Cache for custom field IDs
        logger.info("JiraConnector.__init__: Initialization complete.")

    async def _get_client(self):
        """Initializes and returns the JIRA client, if configured."""
        if self._jira_client:
            return self._jira_client

        def _connect():
            if all([config.JIRA_SERVER, config.JIRA_USERNAME, config.JIRA_API_TOKEN]):
                try:
                    return JIRA(
                        server=config.JIRA_SERVER,
                        basic_auth=(config.JIRA_USERNAME, config.JIRA_API_TOKEN),
                        timeout=20,
                        max_retries=2,
                    )
                except JIRAError as e:
                    logger.error(f"Failed to connect to Jira: {e.status_code}, {e.text}")
                    return None
            return None

        self._jira_client = await asyncio.to_thread(_connect)
        if not self._jira_client:
            logger.warning("Jira not connected. Check credentials in .env file.")
        return self._jira_client

    async def _get_custom_field_id(self, field_name: str) -> str | None:
        """Finds the custom field ID for a given field name (e.g., 'Epic Link'). Caches the result."""
        # Check cache first
        if field_name in self._field_cache:
            return self._field_cache[field_name]

        jira = await self._get_client()
        if not jira:
            return None

        def _fetch_fields():
            try:
                return jira.fields()
            except JIRAError as e:
                logger.error(f"Error fetching Jira fields: {e.text}")
                return None

        all_fields = await asyncio.to_thread(_fetch_fields)
        if not all_fields:
            return None

        for field in all_fields:
            if field['name'].lower() == field_name.lower():
                logger.info(f"Found custom field '{field_name}' with ID: {field['id']}")
                # Store in cache
                self._field_cache[field_name] = field['id']
                return field['id']

        logger.warning(f"Custom field '{field_name}' not found. Review the available fields below.")
        try:
            available_fields = [f"'{field['name']}' (ID: {field['id']})" for field in all_fields]
            logger.warning(f"Available Jira custom fields: {', '.join(available_fields)}")
        except Exception:
            # Avoid crashing the logger if a field is malformed
            logger.warning("Could not format the full list of available custom fields.")

        return None

    async def create_project_if_not_exists(self, project_key: str, project_name: str) -> dict | None:
        """Creates a Jira project if it doesn't already exist."""
        jira = await self._get_client()
        if not jira: return None

        def _create_or_get():
            try:
                project = jira.project(project_key)
                logger.info(f"Project {project_key} already exists.")
                return project
            except JIRAError as e:
                if e.status_code == 404:
                    logger.info(f"Project {project_key} not found, creating it...")
                    if not config.JIRA_LEAD_ACCOUNT_ID:
                        logger.error(
                            "JIRA_LEAD_ACCOUNT_ID is not set. "
                            "Set it to the Jira user accountId (Cloud) or username (Server) "
                            "that should own new projects."
                        )
                        return None
                    
                    payload = {
                        "key": project_key,
                        "name": project_name,
                        "leadAccountId": config.JIRA_LEAD_ACCOUNT_ID,
                        "projectTypeKey": "software",
                        "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic"
                    }
                    
                    url = jira._get_url("project")
                    
                    try:
                        jira._session.post(url, json=payload)
                        logger.info(f"Project {project_key} created successfully.")
                        return jira.project(project_key)
                    except JIRAError as e_create:
                        logger.error(f"Failed to create Jira project {project_key}: {e_create.text}")
                        return None
                else:
                    logger.error(f"Error checking for project {project_key}: {e.text}")
                    return None
        
        return await asyncio.to_thread(_create_or_get)

    async def create_issue(self, issue_dict: dict):
        """Creates a single new issue in Jira. Returns a Jira Issue object or None."""
        jira = await self._get_client()
        if not jira:
            logger.warning("Jira client unavailable; skipping issue creation.")
            return None

        def _create():
            try:
                return jira.create_issue(fields=issue_dict)
            except JIRAError as e:
                logger.error(f"Error creating Jira issue: {e.text}. Issue details: {issue_dict}")
                return None
        return await asyncio.to_thread(_create)

    async def create_onboarding_epic_and_tasks(self, project_key: str, project_name: str, opportunity_name: str, deliverables: list):
        """Creates a parent Epic and links sub-tasks for each deliverable."""
        jira = await self._get_client()
        if not jira: return None

        # 1. Ensure project exists
        project = await self.create_project_if_not_exists(project_key, project_name)
        if not project:
            logger.error(f"Aborting epic creation: project {project_key} could not be created or retrieved.")
            return None

        # 2. Create the Epic
        epic_summary = f"Onboarding Epic: {opportunity_name}"
        epic_dict = {
            'project': {'key': project_key},
            'summary': epic_summary,
            'description': f"Parent Epic for all onboarding tasks related to the opportunity: {opportunity_name}.",
            'issuetype': {'name': 'Epic'},
        }
        logger.info(f"Creating Epic: {epic_summary}")
        created_epic = await self.create_issue(epic_dict)
        if not created_epic:
            logger.error("Failed to create the parent Epic.")
            return None

        epic_key = created_epic.key
        logger.info(f"Epic '{epic_key}' created successfully.")

        # 3. Create Tasks and link to the Epic.
        if not deliverables:
            logger.info("No deliverables found to create as sub-tasks.")
            return epic_key

        issue_tasks = []
        for deliverable in list(set(deliverables)):
            task_dict = {
                'project': {'key': project_key},
                'summary': deliverable,
                'description': f"Deliverable identified for {opportunity_name}.",
                'issuetype': {'name': 'Task'},
                'parent': {'key': epic_key},
            }
            issue_tasks.append(self.create_issue(task_dict))
        
        logger.info(f"Creating {len(issue_tasks)} sub-tasks for Epic {epic_key}...")
        results = await asyncio.gather(*issue_tasks)
        
        successful_tasks = [res.key for res in results if res is not None]
        logger.info(f"Successfully created {len(successful_tasks)} sub-tasks: {successful_tasks}")
        
        return epic_key