import asyncio
from jira import JIRA, JIRAError
from . import config
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class JiraConnector:
    """
    Handles connection and actions with Jira.
    """

    def __init__(self):
        logger.info("JiraConnector.__init__: Initializing...")
        self._jira_client = None
        logger.info("JiraConnector.__init__: Initialization complete.")

    async def _get_client(self):
        """Initializes and returns the JIRA client, if configured."""
        if self._jira_client:
            return self_jira_client

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
                    logger.error(f"Failed to connect to Jira: {e.status_code} - {e.text}")
                    return None
            return None

        self._jira_client = await asyncio.to_thread(_connect)
        if not self._jira_client:
            logger.warning("Jira not connected. Check credentials in .env file.")
        return self._jira_client

    @lru_cache(maxsize=None)
    def _get_custom_field_id(self, field_name: str) -> str | None:
        """Finds the custom field ID for a given field name (e.g., 'Epic Link'). Caches the result."""
        if not self._jira_client:
            return None
        try:
            all_fields = self._jira_client.fields()
            for field in all_fields:
                if field['name'].lower() == field_name.lower():
                    logger.info(f"Found custom field '{field_name}' with ID: {field['id']}")
                    return field['id']
            logger.warning(f"Custom field '{field_name}' not found.")
            return None
        except JIRAError as e:
            logger.error(f"Error fetching Jira fields: {e.text}")
            return None

    async def create_project_if_not_exists(self, project_key: str, project_name: str) -> dict | None:
        """Creates a Jira project if it doesn't already exist."""
        jira = await self._get_client()
        if not jira: return None

        async def _create_or_get():
            try:
                return jira.project(project_key)
            except JIRAError as e:
                if e.status_code == 404:
                    logger.info(f"Project {project_key} not found, creating it...")
                    try:
                        return jira.create_project(
                            key=project_key,
                            name=project_name,
                            template_name="Task management",
                        )
                    except JIRAError as e_create:
                        logger.error(f"Failed to create Jira project {project_key}: {e_create.text}")
                        return None
                else:
                    logger.error(f"Error checking for project {project_key}: {e.text}")
                    return None
        
        return await asyncio.to_thread(_create_or_get)

    async def create_issue(self, issue_dict: dict) -> dict | None:
        """Creates a single new issue in Jira."""
        jira = await self._get_client()
        if not jira: return {"key": "DUMMY-1"} # Return mock issue if not connected

        async def _create():
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
        await self.create_project_if_not_exists(project_key, project_name)

        # 2. Get custom field IDs for Epic
        epic_name_field = await asyncio.to_thread(self._get_custom_field_id, 'Epic Name')
        epic_link_field = await asyncio.to_thread(self._get_custom_field_id, 'Epic Link')
        if not epic_name_field or not epic_link_field:
            logger.error("Could not find 'Epic Name' or 'Epic Link' custom fields. Cannot create Epic.")
            return None

        # 3. Create the Epic
        epic_summary = f"Onboarding Epic: {opportunity_name}"
        epic_dict = {
            'project': {'key': project_key},
            'summary': epic_summary,
            'description': f"Parent Epic for all onboarding tasks related to the opportunity: {opportunity_name}.",
            'issuetype': {'name': 'Epic'},
            epic_name_field: opportunity_name,
        }
        logger.info(f"Creating Epic: {epic_summary}")
        created_epic = await self.create_issue(epic_dict)
        if not created_epic:
            logger.error("Failed to create the parent Epic.")
            return None
        
        logger.info(f"Epic '{created_epic.key}' created successfully.")

        # 4. Create Sub-tasks and link to the Epic
        if not deliverables:
            logger.info("No deliverables found to create as sub-tasks.")
            return created_epic.key

        issue_tasks = []
        for deliverable in list(set(deliverables)):
            task_dict = {
                'project': {'key': project_key},
                'summary': deliverable,
                'description': f"Deliverable identified for {opportunity_name}.",
                'issuetype': {'name': 'Task'},
                epic_link_field: created_epic.key,
            }
            issue_tasks.append(self.create_issue(task_dict))
        
        logger.info(f"Creating {len(issue_tasks)} sub-tasks for Epic {created_epic.key}...")
        results = await asyncio.gather(*issue_tasks)
        
        successful_tasks = [res.key for res in results if res]
        logger.info(f"Successfully created {len(successful_tasks)} sub-tasks: {successful_tasks}")
        
        return created_epic.key
