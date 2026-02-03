"""Jira API connector for fetching and updating issues."""

from dataclasses import dataclass
from typing import Optional
from jira import JIRA
from rich.console import Console

from .config import jira_config

console = Console()


@dataclass
class PBIData:
    """Parsed PBI data structure."""
    key: str
    summary: str
    description: str
    acceptance_criteria: list[str]
    status: str
    issue_type: str
    priority: str
    labels: list[str]
    assignee: Optional[str]
    reporter: str
    url: str


class JiraConnector:
    """Handles all Jira API operations."""
    
    def __init__(self):
        """Initialize Jira connection."""
        self._client: Optional[JIRA] = None
    
    def _connect(self) -> JIRA:
        """Establish connection to Jira."""
        if not self._client:
            if not all([jira_config.server, jira_config.email, jira_config.api_token]):
                raise ValueError(
                    "Missing Jira configuration. Please set JIRA_SERVER, "
                    "JIRA_EMAIL, and JIRA_API_TOKEN in .env file.\n"
                    "Config location: ~/.agentic/.env or current directory"
                )
            self._client = JIRA(
                server=jira_config.server,
                basic_auth=(jira_config.email, jira_config.api_token)
            )
        return self._client
    
    def fetch_pbi(self, issue_key: str) -> PBIData:
        """
        Fetch PBI details from Jira.
        
        Args:
            issue_key: Jira issue key (e.g., 'PBI-123', 'PROJ-456')
            
        Returns:
            PBIData with parsed issue information
        """
        client = self._connect()
        issue = client.issue(issue_key)
        
        # Parse description for acceptance criteria
        description = issue.fields.description or ""
        acceptance_criteria = self._parse_acceptance_criteria(description)
        
        return PBIData(
            key=issue.key,
            summary=issue.fields.summary,
            description=description,
            acceptance_criteria=acceptance_criteria,
            status=str(issue.fields.status),
            issue_type=str(issue.fields.issuetype),
            priority=str(issue.fields.priority) if issue.fields.priority else "None",
            labels=list(issue.fields.labels) if issue.fields.labels else [],
            assignee=str(issue.fields.assignee) if issue.fields.assignee else None,
            reporter=str(issue.fields.reporter) if issue.fields.reporter else "Unknown",
            url=f"{jira_config.server.rstrip('/')}/browse/{issue.key}"
        )
    
    def _parse_acceptance_criteria(self, description: str) -> list[str]:
        """Extract acceptance criteria from description."""
        criteria = []
        lines = description.split('\n')
        in_ac_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if any(marker in line_lower for marker in ['acceptance criteria', 'ac:', 'criteria:']):
                in_ac_section = True
                continue
            
            if in_ac_section and line.strip() and not line.startswith((' ', '-', '*', '•', '\t')) and ':' in line:
                if not any(c.isdigit() for c in line.split(':')[0]):
                    in_ac_section = False
                    continue
            
            if in_ac_section and line.strip():
                clean_line = line.strip().lstrip('-*•').lstrip('0123456789.').strip()
                if clean_line:
                    criteria.append(clean_line)
        
        if not criteria:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(('-', '*', '•')):
                    clean_line = stripped.lstrip('-*•').strip()
                    if clean_line:
                        criteria.append(clean_line)
        
        return criteria
    
    def update_status(self, issue_key: str, target_status: str) -> bool:
        """Update Jira issue status."""
        client = self._connect()
        issue = client.issue(issue_key)
        
        transitions = client.transitions(issue)
        
        transition_id = None
        for t in transitions:
            if t['name'].lower() == target_status.lower():
                transition_id = t['id']
                break
            if t.get('to', {}).get('name', '').lower() == target_status.lower():
                transition_id = t['id']
                break
        
        if transition_id:
            client.transition_issue(issue, transition_id)
            console.print(f"[green]✓[/green] Updated {issue_key} status → {target_status}")
            return True
        else:
            available = [t['name'] for t in transitions]
            console.print(f"[yellow]![/yellow] Cannot transition to '{target_status}'. Available: {available}")
            return False
    
    def transition_to_in_progress(self, issue_key: str) -> bool:
        """Move issue to In Progress status."""
        return self.update_status(issue_key, jira_config.status_in_progress)
    
    def transition_to_in_review(self, issue_key: str) -> bool:
        """Move issue to In Review status."""
        return self.update_status(issue_key, jira_config.status_in_review)
    
    def transition_to_done(self, issue_key: str) -> bool:
        """Move issue to Done status."""
        return self.update_status(issue_key, jira_config.status_done)


jira_connector = JiraConnector()
